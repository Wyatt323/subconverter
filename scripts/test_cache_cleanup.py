#!/usr/bin/env python3
"""Isolated integration check: python3 scripts/test_cache_cleanup.py BINARY."""
import base64
import concurrent.futures
import hashlib
import http.server
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

binary = pathlib.Path(sys.argv[1]).resolve()
root = pathlib.Path(__file__).resolve().parents[1]
node = 'ss://' + base64.urlsafe_b64encode(b'aes-128-gcm:fixture-password').decode().rstrip('=') + '@192.0.2.1:8388#Cache-Test'
slow_started, release_slow = threading.Event(), threading.Event()
class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/slow':
            slow_started.set()
            assert release_slow.wait(20)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(base64.b64encode((node + '\n').encode()))
    def log_message(self, format, *args):
        pass
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
threading.Thread(target=server.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory(prefix='cache-cleanup-', dir=str(root.parent)) as tmp:
    data = pathlib.Path(tmp)
    shutil.copytree(root / 'base', data, dirs_exist_ok=True)
    pref = (data / 'pref.example.toml').read_text().replace('enable_cache = false', 'enable_cache = true').replace('port = 25500', 'port = 25502')
    (data / 'pref.toml').write_text(pref)
    baseline = hashlib.sha256((data / 'pref.toml').read_bytes()).hexdigest()
    cache = data / 'cache'
    cache.mkdir(exist_ok=True)
    outside = data / 'keep.txt'
    outside.write_text('keep')
    def seed():
        (cache / 'nested').mkdir(exist_ok=True)
        (cache / 'nested/file').write_text('cache')
        (cache / '.hidden').write_text('cache')
        (cache / 'link').symlink_to(outside)
    def empty():
        for _ in range(100):
            if not list(cache.iterdir()): return
            time.sleep(.02)
        raise AssertionError('cache not emptied')
    def request(path='/sub', **params):
        url = 'http://127.0.0.1:25502' + path + '?' + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=25) as r: return r.status, r.read().decode()
        except urllib.error.HTTPError as e: return e.code, e.read().decode()
    with (data / 'runtime.log').open('w') as log:
        proc = subprocess.Popen([str(binary), '-f', str(data / 'pref.toml')], cwd=data, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(60):
                try:
                    if request('/version')[0] == 200: break
                except OSError: pass
                time.sleep(.2)
            else:
                log.flush()
                print((data / 'runtime.log').read_text())
                raise AssertionError('startup failed')
            seed()
            status, body = request(target='clash', url='http://127.0.0.1:%s/fast' % server.server_port, list='true')
            assert status == 200 and 'Cache-Test' in body, (status, body)
            empty()
            print('PASS success, remote fetch, nested and hidden cleanup')
            seed()
            status, _ = request(target='invalid', url=node)
            assert status >= 400
            empty()
            print('PASS failure cleanup')
            seed()
            assert request('/version')[0] == 200
            assert list(cache.iterdir()), 'health probes must not clean cache'
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(request, target='clash', url='http://127.0.0.1:%s/slow' % server.server_port, list='true')
                assert slow_started.wait(10)
                status, body = request(target='clash', url=node, list='true')
                assert status == 200 and 'Cache-Test' in body
                assert list(cache.iterdir()), 'cleanup raced active request'
                release_slow.set()
                status, body = future.result()
                assert status == 200 and 'Cache-Test' in body
            empty()
            assert outside.read_text() == 'keep'
            assert hashlib.sha256((data / 'pref.toml').read_bytes()).hexdigest() == baseline
            print('PASS concurrent barrier, symlink target and configuration preserved')
        finally:
            release_slow.set()
            proc.terminate()
            proc.wait(timeout=20)
            if sys.exc_info()[0]:
                print((data / 'runtime.log').read_text())
server.shutdown()
