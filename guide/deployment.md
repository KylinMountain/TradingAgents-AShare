# 部署指南

本文介绍公共镜像的两种部署拓扑，以及从旧版镜像升级时的注意事项。所有环境变量的详细说明见 [configuration.md](configuration.md)。

## 拓扑 A：单容器（默认，推荐个人使用）

镜像默认在同一容器内同时启动 **API 服务**与**定时任务调度器**：配置的定时分析会按触发时间自动执行，无需 Redis 等额外组件（任务状态在进程内维护，报告落库到 SQLite）。

**Docker Compose（推荐）**：仓库根目录的 `docker-compose.yml` 一条命令即可启动：

```bash
export TA_APP_SECRET_KEY=$(openssl rand -base64 32)
docker compose up -d
```

也可以不克隆仓库，只下载 compose 文件：`curl -O https://raw.githubusercontent.com/KylinMountain/TradingAgents-AShare/main/docker-compose.yml`

**docker run（备选）**：

```bash
docker pull ghcr.io/kylinmountain/tradingagents-ashare:latest

mkdir -p $(pwd)/data
export TA_APP_SECRET_KEY=$(openssl rand -base64 32)

docker run -d -p 8000:8000 \
  --name tradingagents \
  --restart always \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL="sqlite:///./data/tradingagents.db" \
  -e TA_APP_SECRET_KEY="${TA_APP_SECRET_KEY}" \
  ghcr.io/kylinmountain/tradingagents-ashare:latest
```

访问 `http://localhost:8000` 即可使用。容器入口的行为：

- 任一进程退出时停止另一进程并以其退出码结束，配合 `--restart always` 整体自愈；
- `SIGTERM`/`SIGINT` 会转发给两个进程，优雅停机；
- 如需只跑单进程，可覆盖容器命令，如 `... <镜像> uv run --no-sync tradingagents-api`。

## 拓扑 B：分开部署（API 与调度器各跑一个容器）

适合需要独立伸缩或由外部系统管理进程的场景。用环境变量为每个容器选择角色：

| 容器 | 环境变量 | 容器内进程 |
|------|----------|-----------|
| API 容器 | `TA_DISABLE_SCHEDULER=1` | 只启动 API |
| 调度器容器 | `TA_DISABLE_API=1` | 只启动调度器 |

**Docker Compose（推荐）**：仓库根目录的 `docker-compose.split.yml` 一条命令启动 API、调度器与 Redis 三个容器：

```bash
export TA_APP_SECRET_KEY=$(openssl rand -base64 32)
docker compose -f docker-compose.split.yml up -d
```

**docker run（备选，手动起两个容器）**：

```bash
# API 容器
docker run -d -p 8000:8000 \
  --name tradingagents-api \
  --restart always \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL="sqlite:///./data/tradingagents.db" \
  -e TA_APP_SECRET_KEY="${TA_APP_SECRET_KEY}" \
  -e TA_DISABLE_SCHEDULER=1 \
  ghcr.io/kylinmountain/tradingagents-ashare:latest

# 调度器容器（无需暴露端口）
docker run -d \
  --name tradingagents-scheduler \
  --restart always \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL="sqlite:///./data/tradingagents.db" \
  -e TA_APP_SECRET_KEY="${TA_APP_SECRET_KEY}" \
  -e TA_DISABLE_API=1 \
  ghcr.io/kylinmountain/tradingagents-ashare:latest
```

注意事项：

- **同一数据库不要同时运行多个调度器实例**，否则定时任务可能重复触发（两个开关同设会被视为误配置，容器入口直接报错退出）。
- 两个容器必须挂载**同一个数据目录**并使用**相同的数据库与密钥配置**。
- 如希望 API 与调度器共享任务状态（调度任务的 SSE 实时进度能在 API 侧看到），在所有容器上配置相同的 `REDIS_URL`（`docker-compose.split.yml` 已预置 `redis://redis:6379/0`）；不配置则各容器使用进程内状态，报告仍通过共享数据库落库，不影响最终结果。
- 调度器并发数由 `SCHEDULER_CONCURRENCY`（默认 3）控制；长任务的软/硬超时见 `TA_JOB_TIMEOUT` / `TA_JOB_HARD_TIMEOUT`。

## 从旧版镜像升级

旧版镜像只启动 API，调度器需要自行单独运行。升级到新版镜像后：

- **单容器用户**：无需任何改动，定时任务自动开始工作。
- **已经分开部署的用户**：API 容器必须加上 `TA_DISABLE_SCHEDULER=1` 再升级，否则 API 容器会拉起第二个调度器，与原有调度器并存导致定时任务重复触发。

## 常用运维操作

```bash
# Compose 部署：查看服务状态与日志
docker compose ps
docker compose logs -f

# 查看容器内进程（确认角色是否符合预期）
docker exec tradingagents ps aux

# 查看日志
docker logs -f tradingagents

# 升级镜像（Compose）
docker compose pull && docker compose up -d

# 升级镜像（docker run）
docker pull ghcr.io/kylinmountain/tradingagents-ashare:latest
docker stop tradingagents && docker rm tradingagents
# 按上面的命令重新 docker run（数据在挂载目录中，不受影响）
```

> **分开部署注意**：以上所有 compose 命令默认读写 `docker-compose.yml`（单体）。按拓扑 B 部署的用户必须给每条命令加 `-f docker-compose.split.yml`（如 `docker compose -f docker-compose.split.yml pull && docker compose -f docker-compose.split.yml up -d`），否则会在同一数据目录上额外拉起一个带调度器的单体容器，导致定时任务重复触发。
