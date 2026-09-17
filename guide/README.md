# 配置与部署指南

面向使用公共镜像或源码部署 TradingAgents-AShare 的用户。

| 文档 | 内容 |
|------|------|
| [deployment.md](deployment.md) | 部署拓扑：单容器（默认）与分开部署（API/调度器/Redis）的角色配置、旧版镜像升级迁移、常用运维操作 |
| [configuration.md](configuration.md) | 全部环境变量参考：核心 LLM、安全、任务超时、调度器、容器角色、存储、邮件、VLM、数据源、高级调优 |

快速上手：

- 只想跑起来 → 按 [deployment.md](deployment.md) 的「拓扑 A」一条 `docker compose up -d` 即可，定时任务开箱即用；
- 生产部署 → 务必设置 `TA_APP_SECRET_KEY`（见 [configuration.md](configuration.md#安全)）；
- 已分开部署的旧镜像用户升级 → 先读 [deployment.md](deployment.md#从旧版镜像升级)。
