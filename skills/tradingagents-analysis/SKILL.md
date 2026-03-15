---
name: tradingagents-analysis
description: 专业 A 股多智能体投研分析工具。集成 15 名 AI 分析师进行 5 阶段深度协作，深度解析技术面、基本面、市场情绪与聪明钱流向，为投资者提供结构化、风控严密的交易建议。Professional multi-agent investment research tool for A-Share stocks using a 15-agent pipeline system.
homepage: https://app.510168.xyz
repository: https://github.com/KylinMountain/TradingAgents-AShare
env:
  TRADINGAGENTS_API_URL:
    description: "后端 API 地址 (TradingAgents API base URL)"
    default: "https://api.510168.xyz"
  TRADINGAGENTS_TOKEN:
    description: "API 访问令牌 (Bearer token starts with ta-sk-)"
    required: true
primary_credential: TRADINGAGENTS_TOKEN
metadata: {"clawdbot":{"emoji":"📈"}}
---

# tradingagents-analysis (A 股多智能体分析)

使用 TradingAgents API 对 A 股进行深度多维度分析，获取基于 **15 名智能体**（5 阶段：分析、博弈、辩论、执行、风控）博弈后的结构化投资建议。

## 🔒 隐私与安全 (Privacy & Security)

- **数据传输**：本技能仅将您提供的**股票标的**发送至配置的后端进行意图识别与分析。
- **自托管方案**：为保障极致隐私，建议参考 [Docker 部署文档](https://github.com/KylinMountain/TradingAgents-AShare#4-docker-一键部署-推荐) 自行托管后端。

## ⚙️ 设置 (Setup)

1. 登录 https://app.510168.xyz
2. 进入 **Settings** → **API Tokens** 创建令牌。
3. 配置环境变量：
```bash
export TRADINGAGENTS_TOKEN="ta-sk-your_key_here"
```

## 🚀 常用操作 (Common Operations)

**1. 提交分析任务 (Submit Analysis Job)**
支持通过**中文名称**或**标准代码**查询。
```bash
# 示例：分析一下贵州茅台 (Analyze Moutai)
curl -X POST "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/analyze" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "贵州茅台"}'
```

**2. 轮询状态与获取结果 (Poll & Retrieve)**
- 状态查询: `GET /v1/jobs/{job_id}`
- 获取结果: `GET /v1/jobs/{job_id}/result`

## 🔄 任务执行流程 (Execution Workflow)

深度分析涉及 **15 名专业智能体** 的多轮博弈，通常耗时 **1 至 5 分钟**：

1. **意图识别**：自动从对话上下文中锁定分析目标标的。
2. **任务提交**：向分析引擎异步提交 `POST /v1/analyze` 任务。
3. **状态同步**：向用户反馈任务已受理，并提供预期的分析耗时。
4. **智能监测**：后台持续轮询任务进度（建议每 30 秒），直至任务完成。
5. **研报萃取**：提取并展示 **决策 (BUY/SELL/HOLD)**、**市场方向**、**目标价**及**风险约束**。

## 📌 支持范围 (Supported Inputs)

- **中文名称 (Chinese Names)**：如 "阳光电源", "三花智控", "比亚迪"。
- **标准代码 (Standard Codes)**：如 `002594.SZ`, `601012.SH`。

## 💡 注意事项 (Notes)
- **数据健壮性**：若个股新闻等数据源缺失，系统将基于宏观与行业逻辑进行外溢效应分析。
- **轮询频率**：请勿高于每 15 秒一次。
