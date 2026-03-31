# TradingAgents-AShare：A股智能投研多智能体系统

本项目是基于多智能体协作的 A 股深度分析系统，模拟顶级投研机构的决策闭环，通过 14 名专业 Agent 的多空辩论与风控博弈，为投资者提供结构化的交易建议。

[在线体验](https://app.510168.xyz) | [Releases](https://github.com/KylinMountain/TradingAgents-AShare/releases) | [OpenClaw 技能](https://clawhub.ai/kylinmountain/tradingagents-analysis)

<div align="center">
  <img src="assets/web/analysis.png" width="100%" alt="智能分析"/>
  <p><em>14 名智能体实时协作，左侧对话驱动，右侧可视化全流程</em></p>
</div>

> TradingAgents-AShare 已正式上线 OpenClaw！您只需通过 `tradingagents-analysis` 技能，即可让您的 AI助手具备专业的 A 股深度投研能力。

## 功能特性

### 辩论对战可视化

点击 Agent 卡片即可打开辩论 Drawer，实时观看多空对抗与风控三方辩论。垂直时间线按 Round 分组，Token 级流式呈现每位 Agent 的发言，裁决卡片独立高亮展示。

<div align="center">
  <img src="assets/web/debate_drawer.png" width="80%" alt="辩论对战可视化"/>
</div>

### 意图驱动的自然语言交互

直接输入"调研茅台短线"即可自动识别标的、解析投资周期，支持短线与中线双周期分析，无需填写表单。

### 自选股与定时分析

数据库持久化自选列表，支持批量加入股票、自定义周期与触发时间，并可在前端批量更新、删除或手动测试定时任务。定时分析会自动复用持仓上下文，连续失败自动停用，无需人工干预。

<div align="center">
  <img src="assets/web/timer_analysis.png" width="80%" alt="定时分析"/>
</div>

### QMT 持仓同步与跟踪看板

支持接入 QMT / xtquant 持仓，自动同步账户持仓、成本价与仓位占比，并可一键将持仓标的补齐到定时分析列表。控制台会展示跟踪看板摘要，完整看板页支持查看实时价格、当日区间、持仓盈亏与上一交易日报告区间，方便盘中快速跟踪。

### 结构化研报管理

分析结果结构化存储，支持按标的、日期检索历史研报，决策卡片一目了然地展示方向、置信度、目标价与止损价。

<div align="center">
  <table style="width: 100%">
    <tr>
      <td width="50%"><img src="assets/web/reports.png" alt="历史报告"/><br><em>研报历史</em></td>
      <td width="50%"><img src="assets/web/detail.png" alt="研报详情"/><br><em>深度详情</em></td>
    </tr>
  </table>
</div>

### 多模型厂商支持

OpenAI、Anthropic、Google Gemini、DeepSeek、Moonshot、智谱、硅基流动等，用户可在前端自由切换模型厂商与具体模型；保存配置后会自动执行模型 warmup，也可以在设置页手动发送“你好”查看模型原始返回，便于排查接入问题。

<div align="center">
  <img src="assets/web/settings.png" width="80%" alt="定时分析"/>
</div>

## 核心架构

TradingAgents 模拟真实交易机构的部门协作，将复杂任务拆解为专业的智能体角色：

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

*图中仅展示核心节点，完整流程包含 14 名智能体。

### 分析师团队
基本面、情绪、新闻、技术、宏观、主力资金 6 大维度同步作业，对市场数据进行深度提取与初步评估。

<p align="center">
  <img src="assets/analyst.png" width="90%">
</p>

### 研究员团队
多头与空头研究员针对分析师结论开展 Claim 驱动的结构化辩论（红蓝对抗），研究总监综合裁决形成投资计划。

<p align="center">
  <img src="assets/researcher.png" width="80%">
</p>

### 决策与风控
交易员将研究结论转化为可执行方案，激进/稳健/中性三方风控辩论审查，组合经理最终裁决。

<p align="center">
  <img src="assets/risk.png" width="80%">
</p>

## 快速上手

### Docker 一键部署 (推荐)

```bash
docker pull ghcr.io/kylinmountain/tradingagents-ashare:latest

mkdir -p $(pwd)/data
export TA_APP_SECRET_KEY=$(openssl rand -base64 32)

docker run -d -p 8000:8000 \
  --name tradingagents \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL="sqlite:///./data/tradingagents.db" \
  -e TA_APP_SECRET_KEY="${TA_APP_SECRET_KEY}" \
  ghcr.io/kylinmountain/tradingagents-ashare:latest
```

访问 `http://localhost:8000` 即可使用。

> **`TA_APP_SECRET_KEY`**：用于加密用户 LLM API Key 和签发登录 JWT。不设置时使用内置默认密钥（仅适合本地开发）。生产环境务必设置，且不可更改。

> **LLM 配置**：启动后在前端"设置"页面配置模型厂商、API Key 和模型名称即可，无需环境变量预设。

### 源码安装

```bash
git clone https://github.com/KylinMountain/TradingAgents-AShare.git
cd TradingAgents-AShare

# 后端（Python 3.10+）
uv sync

# 前端（Node.js 18+）
cd frontend
npm install
npm run build
cd ..
```

复制 `.env.example` 到 `.env` 并按需修改，然后：

```bash
# 启动后端
uv run python -m uvicorn api.main:app --port 8000
```

访问 `http://localhost:8000` 即可开始 AI 投研之旅。

## API 集成

系统提供标准 REST API，方便集成到自定义脚本、交易机器人或第三方看板：

| 操作 | 接口 |
|------|------|
| 触发分析 | `POST /v1/analyze` → 返回 `job_id` |
| 状态追踪 | `GET /v1/jobs/{job_id}` |
| 获取结果 | `GET /v1/jobs/{job_id}/result` |
| 历史检索 | `GET /v1/reports` |
| 批量获取最新报告 | `POST /v1/reports/latest-by-symbols` |
| QMT 持仓同步 | `GET/POST/DELETE /v1/portfolio/imports/qmt` |
| 跟踪看板摘要/明细 | `GET /v1/dashboard/tracking-board` |
| 批量定时任务操作 | `PATCH /v1/scheduled/batch`、`POST /v1/scheduled/batch/delete`、`POST /v1/scheduled/batch/trigger` |
| 模型 warmup | `POST /v1/config/warmup` |

认证：Web 端登录后在"设置 / API Token"生成密钥，通过 `Authorization: Bearer <TOKEN>` 传入。

```bash
curl -X POST 'https://app.510168.xyz/v1/analyze' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
  -d '{"symbol": "分析一下600519.SH短期趋势", "trade_date": "2026-03-28"}'
```

## 集成 OpenClaw

1. 在本站生成 API Key
2. 在 OpenClaw 中安装技能 `tradingagents-analysis`

示例任务："分析 002594.SZ 今天是否适合介入，给我结论、置信度、目标价、止损价和核心风险。"

## 特别鸣谢

本项目核心架构灵感与部分基础逻辑源自 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)。感谢原作者及团队在多智能体交易领域做出的卓越探索与开源贡献。

## 许可说明
- 本项目基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache 2.0) 二次开发。
- 新增模块 (`api/`, `frontend/`) 及对核心逻辑的深度修改采用 `PolyForm Noncommercial 1.0.0` 协议。
- 详情请参阅根目录下的 [LICENSE](./LICENSE) 文件。

## 重要声明
- **仅供学习研究**：本项目仅用于学术研究、技术演示及学习交流目的，不构成任何形式的投资建议。
- **实盘风险**：证券市场有风险，投资需谨慎。基于本系统生成的任何观点、建议或计划，仅代表算法博弈结果，不对实际投资损益负责。
- **数据延迟**：分析所依赖的数据源可能存在延迟或偏差，请以交易所实时公告为准。

<div align="center">
<a href="https://www.star-history.com/#KylinMountain/TradingAgents-AShare&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=KylinMountain/TradingAgents-AShare&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=KylinMountain/TradingAgents-AShare&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=KylinMountain/TradingAgents-AShare&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>
