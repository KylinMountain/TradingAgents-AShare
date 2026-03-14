# TradingAgents-AShare：A股智能投研多智能体系统

这是一个基于 12 个 AI Agent 协作的深度股票分析与决策系统，专为 A 股场景打造。系统已接入 A 股行情、新闻、情绪、基本面与技术面等多维数据，模拟专业交易机构的协作模式，对单只股票或股票池进行自动化推演，并通过结构化辩论收敛出最终的交易建议。

> 让 OpenClaw 不只会聊天，也能真正调用 A 股数据和多智能体投研流程，替你盯盘、选股、分析和回收结论。

## ✨ 现代化 Web 交互

系统已由传统的 CLI 界面全面升级为现代化的 Web 交互界面，支持实时任务进度追踪、响应式布局与结构化研报管理。
[在线 Demo](https://app.510168.xyz)

<div align="center">
  <img src="assets/web/analysis.png" width="100%" alt="智能分析"/><br><em>Agent 协作分析</em>
  <table style="width: 100%">
    <tr>
      <td width="50%"><img src="assets/web/reports.png" alt="历史报告"/><br><em>研报历史管理</em></td>
      <td width="50%"><img src="assets/web/detail.png" alt="研报详情"/><br><em>深度分析详情</em></td>
    </tr>
    <tr>
      <td width="50%"><img src="assets/web/dashboard.png" alt="控制台"/><br><em>数据控制台</em></td>
      <td width="50%"><img src="assets/web/settings.png" alt="系统设置"/><br><em>系统设置</em></td>
    </tr>
  </table>
</div>


## 🤖 核心架构与团队

TradingAgents 模拟了真实交易机构的部门协作，将复杂任务拆解为专业的智能体角色：

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

### 1. 分析师团队 (Analyst Team)
基本面、情绪、新闻、技术四大维度分析师同步作业，对市场数据进行深度提取与初步评估。
<p align="center">
  <img src="assets/analyst.png" width="90%">
</p>

### 2. 研究员团队 (Researcher Team)
由多头与空头研究员组成，针对分析师结论开展结构化辩论（红蓝对抗），在冲突中挖掘潜在收益并识别关键风险。
<p align="center">
  <img src="assets/researcher.png" width="60%">
</p>

### 3. 决策与风控 (Trader & Risk Management)
交易员根据辩论结果生成初始方案，风控团队进行流动性与波动率审查，最终由组合经理批准执行。
<p align="center">
  <img src="assets/risk.png" width="60%">
</p>



## 🚀 快速上手

### 1. 环境准备
克隆项目：
```bash
git clone https://github.com/KylinMountain/TradingAgents-AShare.git
cd TradingAgents-AShare
```

安装后端（Python 3.10+，推荐使用 [uv](https://github.com/astral-sh/uv)）：
```bash
uv sync
```

安装前端（Node.js 18+）：
```bash
cd frontend && npm install
```

### 2. 精简配置
复制 `.env.example` 到 `.env` 并填写核心模型接入信息：
```env
# 核心模型接入 (建议使用 DeepSeek 或 GPT-4o 等强模型)
TA_API_KEY=你的密钥
TA_BASE_URL=https://api.openai.com/v1
TA_LLM_QUICK=gpt-4o-mini
TA_LLM_DEEP=gpt-4o

# 数据库 (默认使用本地 SQLite)
DATABASE_URL=sqlite:///./tradingagents.db
```

### 3. 启动运行
**启动后端 API**：
```bash
uv run python -m uvicorn api.main:app --port 8000
```

**启动前端界面**：
```bash
cd frontend && npm run dev
```
访问 `http://localhost:5173` 即可开始您的 AI 投研之旅。

### 4. Docker 一键部署 (推荐)
如果您想快速运行完整服务（前后端合一），可以直接使用我们提供的 Docker 镜像：

```bash
docker pull ghcr.io/kylinmountain/tradingagents-ashare:latest
docker run -d -p 8000:8000 \
  --name tradingagents \
  -v $(pwd)/tradingagents.db:/app/tradingagents.db \
  -e TA_API_KEY="你的密钥" \
  -e TA_BASE_URL="https://api.openai.com/v1" \
  ghcr.io/kylinmountain/tradingagents-ashare:latest
```
访问 `http://localhost:8000` 即可使用。


## 🛠 API 集成

系统提供标准的 REST API，方便集成到自定义脚本、交易机器人或第三方看板：

1. **触发分析**：`POST /v1/analyze` -> 立即返回 `job_id`
2. **状态追踪**：`GET /v1/jobs/{job_id}` -> 轮询 `status`
3. **获取结果**：`GET /v1/jobs/{job_id}/result` -> 拿到结构化研报
4. **历史检索**：`GET /v1/reports` -> 拉取过往所有分析记录

生产环境 Base URL：

- `https://api.510168.xyz`

认证方式：

- 在 Web 端登录后，进入“设置 / API Token”生成专属 API Key
- 调用接口时通过 `Authorization: Bearer <YOUR_API_TOKEN>` 传入

示例：触发一次股票分析

```bash
curl -X POST 'https://app.510168.xyz/v1/analyze' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
  -d '{
    "symbol": "600519.SH",
    "trade_date": "2026-03-11",
    "selected_analysts": ["market", "social", "news", "fundamentals"]
  }'
```

拿到 `job_id` 后继续查询：

```bash
curl -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
  'https://app.510168.xyz/v1/jobs/<JOB_ID>'

curl -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
  'https://app.510168.xyz/v1/jobs/<JOB_ID>/result'
```

## 🔌 集成 OpenClaw

可以把 TradingAgents-AShare 作为 OpenClaw 的外部分析能力来调用，让 OpenClaw 负责“接收任务 -> 指定股票 -> 发起分析 -> 回收结果 -> 继续编排后续动作”。

推荐接法：

1. 在本站生成 API Key
2. 在 OpenClaw 中配置一个 HTTP 工作流或自定义工具
3. 让 OpenClaw 按下面流程调用：
   - `POST https://app.510168.xyz/v1/analyze`
   - `GET https://app.510168.xyz/v1/jobs/{job_id}`
   - `GET https://app.510168.xyz/v1/jobs/{job_id}/result`

一个典型任务可以是：

- “分析 002594.SZ 今天是否适合介入，给我结论、置信度、目标价、止损价和核心风险。”

OpenClaw 拿到结果后，可以继续做这些事情：

- 汇总成一段更适合业务人员阅读的结论
- 把多只股票的结果做横向对比
- 结合你自己的策略规则，自动筛选出候选标的
- 接到定时任务后，自动跑每日股票池分析

如果你希望 OpenClaw 直接从自然语言驱动，也可以让它先把用户输入解析成股票代码和交易日期，再按上述 API 流程调用 TradingAgents。



## 许可与引用

- 本项目基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 二次开发。
- 新增组件（前端、API层）采用 `PolyForm Noncommercial 1.0.0` 协议，仅限非商业用途。




<div align="center">
<a href="https://www.star-history.com/#KylinMountain/TradingAgents-AShare&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=KylinMountain/TradingAgents-AShare&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=KylinMountain/TradingAgents-AShare&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=KylinMountain/TradingAgents-AShare&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>
