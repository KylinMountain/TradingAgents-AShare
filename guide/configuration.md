# 环境变量配置参考

本文档列出 TradingAgents-AShare 支持的全部环境变量，以代码实际读取为准（比 `.env.example` 更全）。按主题分组，标注默认值与何时需要修改。

约定：

- **加粗**的变量是大多数部署必须关注的；其余保持默认即可。
- 除特别说明外，布尔类变量以 `1/true/yes/on`（大小写不限）为真。
- 修改环境变量时，请同步更新本文档（维护约定）。

## 核心 LLM 接入

模型也可以在网页「设置」中按用户配置；以下服务端变量作为全局默认与兜底。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TA_API_KEY` | （空） | 主 LLM 的 API Key。用户未在页面配置时，由 `ALLOW_SERVER_LLM_FALLBACK` 决定是否用它兜底 |
| `TA_BASE_URL` | `https://api.openai.com/v1` | 主 LLM 的 Base URL，可指向任何 OpenAI 兼容服务 |
| `TA_LLM_PROVIDER` | `openai` | 服务商：`openai` / `xai` / `openrouter` / `ollama` / `deepseek`。为 xai/openrouter/deepseek 时 Base URL 自动切换，无需手填 |
| `TA_LLM_QUICK` | `gpt-4o-mini` | 快速模型（信息整理、快报等高频调用） |
| `TA_LLM_DEEP` | `gpt-4o` | 深度模型（研究员辩论、最终决策） |
| `DEEPSEEK_API_KEY` | （空） | provider 为 `deepseek` 时读取 |
| `XAI_API_KEY` | （空） | provider 为 `xai` 时读取 |
| `OPENROUTER_API_KEY` | （空） | provider 为 `openrouter` 时读取 |
| `ALLOW_SERVER_LLM_FALLBACK` | `1` | 用户未配置自己的模型 Key 时，是否允许使用服务端 `TA_API_KEY`。多用户部署建议设为 `0`，避免被盗刷 |

> provider 为 `ollama` 时固定使用 `http://localhost:11434/v1`，Key 为占位符 `ollama`，无需配置。

## 安全

| 变量 | 默认值 | 说明 |
|------|--------|------|
| **`TA_APP_SECRET_KEY`** | （空，不安全） | 加密用户 LLM API Key、签发登录 JWT 的主密钥。**生产环境必须设置**，生成：`openssl rand -base64 32`。首次设置会自动把已有数据从默认密钥迁移到新密钥；设置后不可更改 |

## 分析行为

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TA_LANGUAGE` | `zh` | 提示词语言：`auto` / `zh` / `en` |
| `TA_MAX_DEBATE` | `2` | 研究员辩论轮数（1-5） |
| `TA_MAX_RISK` | `1` | 风险讨论轮数（1-5） |
| `TA_TRACE` | `1` | 运行日志追踪：`1` 开启 / `0` 关闭 |

## 任务生命周期（超时）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TA_JOB_TIMEOUT` | `1800` | **软期限**（秒）。到期仅发出 `job.overtime` 提醒，任务继续运行。`0` 禁用提醒 |
| `TA_JOB_HARD_TIMEOUT` | `7200` | **硬上限**（秒）。到期取消任务并标记失败，释放调度资源。`0` 禁用。若小于等于软期限，则不发提醒直接按硬上限处理 |
| `JOB_STATE_TTL` | `86400` | Redis 任务状态哈希的 TTL（秒），仅配置 `REDIS_URL` 时生效 |
| `INMEMORY_JOB_TTL` | `600` | 内存 job store 中已完成任务的保留时间（秒） |
| `JOB_EVENT_QUEUE_MAXSIZE` | `2000` | SSE 事件队列上限 |

## 调度器

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SCHEDULER_CONCURRENCY` | `3` | 定时分析并发数（scheduler 进程内的信号量） |

## 容器角色（Docker 入口）

公共镜像默认在同一容器内同时启动 API 与调度器，详见 [deployment.md](deployment.md)。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TA_DISABLE_API` | （空） | 设为真时本容器不启动 API（调度器容器使用） |
| `TA_DISABLE_SCHEDULER` | （空） | 设为真时本容器不启动调度器（API 容器使用）。两者同设视为误配置，入口直接退出 |

## 状态与存储

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./tradingagents.db` | SQLAlchemy 数据库地址。Docker 部署建议 `sqlite:///./data/tradingagents.db` 并挂载 `/app/data` |
| `REDIS_URL` | （空） | 如 `redis://host:6379/0`。设置后任务状态/SSE 事件走 Redis（多进程共享）；不设置为进程内内存态 |
| `UPLOAD_DIR` | 项目根 `uploads/`（容器内 `/app/uploads`） | 上传文件（头像等）目录。注意不在挂载的 `/app/data` 下，容器重建后头像会丢失；需要持久化时设为 `/app/data/uploads` |
| `TA_RESULTS_DIR` | `./results` | 分析中间产物目录 |

## 邮件服务（SMTP）

用于邮箱验证码登录与分析报告邮件推送。不配置 `MAIL_HOST` 则邮件功能整体关闭：登录验证码打印到后端日志，非生产环境（`APP_ENV≠production`）下还会直接返回给前端展示。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MAIL_HOST` | （空） | SMTP 服务器。别名：`MAIL_SERVER`、`SMTP_HOST` |
| `MAIL_PORT` | `587` | SMTP 端口。别名：`SMTP_PORT` |
| `MAIL_USER` | （空） | SMTP 账号。别名：`MAIL_USERNAME`、`SMTP_USER` |
| `MAIL_PASS` | （空） | SMTP 授权码/密码。别名：`MAIL_PASSWORD`、`SMTP_PASSWORD` |
| `MAIL_FROM` | 同 `MAIL_USER`（为空则 `noreply@example.com`） | 发件人地址/名称。别名：`SMTP_FROM` |
| `MAIL_STARTTLS` | `1` | 使用 STARTTLS（587 端口常用）。别名：`SMTP_TLS`。注意为反向解析：仅 `0/false/off/no` 为关 |
| `MAIL_SSL` | `0` | 使用 SSL/TLS 直连（465 端口常用，与 STARTTLS 二选一）。别名：`MAIL_SSL_TLS` |

## VLM 截图识别（持仓截图）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TA_VLM_API_KEY` | （空） | 视觉模型 API Key，不配置则截图识别不可用 |
| `TA_VLM_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | 视觉模型 Base URL（OpenAI 兼容） |
| `TA_VLM_MODEL` | `glm-4.6v-flash` | 视觉模型名（默认智谱免费模型） |
| `TA_VLM_PROVIDER` | `openai` | `openai` / `anthropic` |
| `TA_VLM_RAW_BASE64` | `1` | `1/true/yes` 发送裸 base64；其他值发送 `data:` URI 前缀（按服务商要求切换；注意此变量不认 `on`） |

## 数据源

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `XQ_A_TOKEN` | （空） | 雪球 token，提升 A 股行情/财务数据稳定性 |
| `INVESTODAY_API_KEY` | （空） | Investoday 数据服务 key |
| `INVESTODAY_BASE_URL` | `https://data-api.investoday.net/data` | Investoday 服务地址 |
| `ALPHA_VANTAGE_API_KEY` | （空） | Alpha Vantage（美股数据） |

## 网络与前端

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FRONTEND_URL` | （空） | 前端地址，用于拼接邮件中的报告链接等 |
| `CORS_ALLOW_ORIGINS` | （空） | 额外允许的跨域来源，逗号分隔 |
| `CORS_ALLOW_ORIGIN_REGEX` | （空） | 跨域来源正则（如允许某域名全部子域） |
| `TA_SOCKET_DEFAULT_TIMEOUT` | `60` | 全局 socket 默认超时（秒），防止数据源库僵死占满线程池 |
| `TA_DATA_FETCH_TIMEOUT` | `300` | 单次数据抓取超时（秒） |

## 高级调优（普通用户无需修改）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ANYIO_THREAD_LIMIT` | `120` | AnyIO 同步端点线程上限 |
| `ASYNCIO_DEFAULT_EXECUTOR_WORKERS` | `64` | `asyncio.to_thread` 默认线程池大小；scheduler 进程为 `max(64, 并发数×16)` |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `TA_MAX_WORKERS` | `2` | API 进程内预留的小型线程池（当前代码基本未使用），无需调整 |
| `ENV` | （空） | 设为 `prod` 时关闭 `/docs`、`/redoc`、`/openapi.json` |
| `APP_ENV` | `development` | 设为 `production` 时，未配置 SMTP 的登录验证码不再返回给前端展示（仍会打印到后端日志） |
| `APP_VERSION` | 镜像构建注入 | 版本号，一般由 CI 通过 `--build-arg VERSION=` 设置 |
