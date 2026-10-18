# Docker 部署（Wyatt323/subconverter）

镜像：`wyatt323/subconverter:latest`，基于本仓库源码编译，不是上游镜像重新打标签。

```bash
mkdir -p subconverter && cd subconverter
curl -fLO https://raw.githubusercontent.com/Wyatt323/subconverter/master/docker-compose.yml
docker compose up -d
curl -f http://127.0.0.1:25500/version
```

默认对外监听 `25500`，这是订阅转换后端，不带 Web UI。防火墙需要允许该端口。可在 `.env` 设置 `PORT=25500`、`BIND_ADDRESS=127.0.0.1`；默认 `BIND_ADDRESS=0.0.0.0`。

## 持久化

Compose 将 `./data` 绑定到容器 `/base`，整个工作目录均保留，包括：

- `pref.toml` / `pref.yml` / `pref.ini` 主配置。
- `rules/`、`config/`、`profiles/`、`snippets/`、`scripts/` 以及各客户端模板目录。
- `cache/` 仍映射到宿主机，但订阅转换请求结束后会自动清空其内容（包括隐藏文件和子目录），保留目录本身。配置、规则和模板不受影响。

`/sub`、`/sub2clashr`、`/surge2clash`、`/getprofile` 的处理成功或失败均触发清理；并发请求期间延迟到所有正在执行的 HTTP handler 完成后再清理，防止删除其他请求使用中的缓存。`/version` 健康检查本身不会触发清理。清理发生在转换结果生成后、交由 HTTP 层发送前，不等待客户端接收完成。请求持续重叠时会延迟清理，进程被强制终止也可能留下缓存。

此策略不禁止处理请求期间写入缓存，但后续独立请求不能复用已清除的磁盘缓存，可能增加远程下载次数。

首次启动向空数据目录复制镜像内的默认文件。后续启动只补充缺失文件，不覆盖已有文件；镜像升级不会强制更新已经持久化的默认规则和模板，需要自行合并更新。不要删除仍需保留的数据目录。备份时停止容器后归档整个 `data/` 和 Compose 文件。

新安装自动生成 `pref.toml`，启用 `api_mode = true`，并生成随机 `api_access_token`；已有配置保持不变。管理令牌在主配置中查看，请勿公开或使用默认 `password`。API 模式禁止使用转换接口读取本地订阅文件，不影响 `rules/`、客户端模板和由管理员配置的 profiles。

日志由 Docker 收集（`docker compose logs -f`），每份最大 10 MB，保留 3 份；普通重启/容器重建不影响 `data/`，但日志不属于该目录，长期日志归档需另接日志系统。

## 更新

```bash
docker compose pull
docker compose up -d
```

需要固定版本时，将 Compose 中的 `latest` 改为已发布的 `sha-<commit前12位>` 标签或镜像摘要。

## 本地构建

```bash
docker build -t wyatt323/subconverter:latest --build-arg VCS_REF="$(git rev-parse HEAD)" .
```

默认 Dockerfile 使用 Debian 多阶段源码编译，并固定 QuickJS、libcron 和 toml11 版本，不在构建时下载动态远程规则。`base/` 中的规则随源码一起打包。旧 `Dockerfile.local` 为历史构建方式；当前部署请使用根目录 `Dockerfile`。
