#!/bin/sh
set -eu
mkdir -p /base
# Seed missing files only. Existing preferences, rules and templates always win.
cp -rn /usr/share/subconverter/defaults/. /base/
cd /base
# Use API mode for an internet-facing conversion backend. The upstream false
# value enables local-file reads. Keep the management token private and random.
if [ ! -e pref.toml ] && [ ! -e pref.yml ] && [ ! -e pref.ini ]; then
    token="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
    sed -e 's/^api_mode = false/api_mode = true/' \
        -e "s/^api_access_token = .*/api_access_token = \"${token}\"/" \
        pref.example.toml > pref.toml
fi
exec "$@"
