---
name: tradingagents-analysis
description: 专业 A 股多智能体投研工具。15 名 AI 分析师五阶段协作，深度分析技术面、基本面、市场情绪与资金流向，提供结构化交易建议。Professional multi-agent investment research for A-Share & US stocks — market, fundamentals, sentiment, smart money.
homepage: https://app.510168.xyz
repository: https://github.com/KylinMountain/TradingAgents-AShare
tags:
  - A股
  - 股票分析
  - 量化投研
  - 多智能体
  - TradingAgent
  - A-share
  - stock-analysis
  - China
  - Multi-Agent
env:
  TRADINGAGENTS_API_URL:
    description: "后端 API 地址 (TradingAgents API base URL)"
    default: "https://api.510168.xyz"
  TRADINGAGENTS_TOKEN:
    description: "API 访问令牌，以 ta-sk- 开头 (Bearer token starts with ta-sk-)"
    required: true
primary_credential: TRADINGAGENTS_TOKEN
metadata: {"clawdbot":{"emoji":"📈"}}
---

# TradingAgents 多智能体 A 股投研分析

使用 TradingAgents API，让 **15 名专业 AI 分析师**对 A 股进行五阶段深度协作研判，输出结构化投资建议。

## 🤖 系统架构：五阶段 15 智能体

| 阶段 | 智能体 | 职责 |
|------|--------|------|
| 1. 分析团队 | 市场/新闻/情绪/基本面/宏观/聪明钱 | 多维度原始数据解读 |
| 2. 博弈裁判 | 博弈论管理者 | 主力与散户预期差分析 |
| 3. 多空辩论 | 多头/空头研究员 + 裁判 | 对立观点激烈博弈 |
| 4. 执行决策 | 交易员 | 综合研判生成操作建议 |
| 5. 风险管控 | 激进/中性/保守分析师 + 组合经理 | 多维度风控审核 |

---

# TradingAgents Multi-Agent Investment Research

Use the TradingAgents API to let **15 specialized AI analysts** conduct deep, five-stage collaborative research on A-Share and US stocks, delivering structured trading recommendations.

## 🤖 System Architecture: 5 Stages · 15 Agents

| Stage | Agents | Role |
|-------|--------|------|
| 1. Analyst Team | Market / News / Sentiment / Fundamentals / Macro / Smart Money | Multi-dimensional raw data analysis |
| 2. Game Theory | Game Theory Manager | Main-force vs. retail expectation gap |
| 3. Bull/Bear Debate | Bull & Bear Researchers + Judge | Adversarial viewpoint debate |
| 4. Trade Execution | Trader | Synthesize research into actionable decision |
| 5. Risk Control | Aggressive / Neutral / Conservative + Portfolio Manager | Multi-layer risk review |

## 🔒 隐私与安全

- **数据传输**：本技能仅向后端发送股票代码和分析参数，不读取本地文件或隐私数据。
- **自托管**：如需最大隐私保障，可参考 [GitHub 文档](https://github.com/KylinMountain/TradingAgents-AShare) 自行部署后端。

## ⚙️ 快速配置

1. 登录 [https://app.510168.xyz](https://app.510168.xyz)
2. 进入 **Settings → API Tokens** 创建令牌
3. 配置环境变量：
```bash
export TRADINGAGENTS_TOKEN="ta-sk-your_key_here"
# 可选，自托管时使用：
# export TRADINGAGENTS_API_URL="http://your-server:8000"
```

## 🚀 常用操作

所有请求使用 `$TRADINGAGENTS_TOKEN` 作为 Bearer 令牌。

**1. 提交分析任务**（支持中文名称、6 位代码或标准代码）
```bash
# 中文名称
curl -X POST "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/analyze" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "贵州茅台"}'

# 标准代码
curl -X POST "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/analyze" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519.SH"}'
```

**2. 查询任务状态**
```bash
curl "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/jobs/{job_id}" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN"
```

**3. 获取完整分析结果**（任务完成后）
```bash
curl "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/jobs/{job_id}/result" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN"
```

## 📊 示例输出

```json
{
  "decision": "BUY",
  "direction": "看多",
  "confidence": 78,
  "target_price": 1850.0,
  "stop_loss_price": 1680.0,
  "risk_items": [
    {"name": "估值偏高", "level": "medium", "description": "当前 PE 处于历史 75 分位"},
    {"name": "外资流出", "level": "low",    "description": "近 5 日北向资金小幅净流出"}
  ],
  "key_metrics": [
    {"name": "PE",   "value": "32.5x",  "status": "neutral"},
    {"name": "ROE",  "value": "31.2%",  "status": "good"},
    {"name": "毛利率", "value": "91.5%", "status": "good"}
  ],
  "final_trade_decision": "综合技术面突破与基本面支撑，建议逢低分批建仓..."
}
```

## 🔄 任务执行流程

深度分析通常耗时 **1 至 5 分钟**：

1. **识别标的**：从对话中提取股票名称或代码
2. **提交任务**：调用 `POST /v1/analyze`
3. **告知用户**：反馈任务已受理，预计耗时
4. **轮询进度**：每 30 秒查询一次状态
5. **汇总结论**：任务完成后提取并展示决策、方向、目标价、风险点

## 📌 支持标的范围

- **A 股**：中文名称（如 "比亚迪"、"宁德时代"）或代码（`002594.SZ`、`601012.SH`）
- **美股**：`AAPL`、`TSLA`、`NVDA` 等标准 Ticker

## 💡 注意事项

- **轮询频率**：每次轮询间隔不低于 15 秒
- **数据健壮性**：若部分数据源缺失，系统将基于宏观与行业逻辑进行外溢分析
- **短线模式**：输入"分析 XX 短线"时，系统自动切换为 14 天技术面分析，跳过财报数据，速度更快
