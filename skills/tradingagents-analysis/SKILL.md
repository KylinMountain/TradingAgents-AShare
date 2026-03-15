---
name: tradingagents-analysis
description: 专业 A 股多智能体投研工具。15 名 AI 分析师五阶段协作，深度分析技术面、基本面、市场情绪与资金流向，提供结构化交易建议。Professional multi-agent investment research for A-Share & US stocks — market, fundamentals, sentiment, smart money.
homepage: https://app.510168.xyz
repository: https://github.com/KylinMountain/TradingAgents-AShare
tags:
  - A股
  - 股票分析
  - 量化投研
  - A-share
  - stock-analysis
  - China
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

# tradingagents-analysis

Use the TradingAgents API to perform deep multi-agent stock analysis and get structured trading recommendations.

## 🔒 Privacy & Security

- **Data Transmission**: This skill sends the **stock symbol** and analysis parameters to the configured backend.
- **Sensitive Data**: The skill only accesses the symbol provided by you. It does not read local files or other private data.
- **Backend Ownership**: The default API (`https://api.510168.xyz`) is provided by the TradingAgents project.
- **Self-Hosting**: For maximum privacy, you can host your own backend using the source code from our [GitHub Repository](https://github.com/KylinMountain/TradingAgents-AShare).

## Setup

1. Login at https://app.510168.xyz
2. Go to **Settings** → **API Tokens** to create a token.
3. Configure your environment:
```bash
export TRADINGAGENTS_TOKEN="ta-sk-your_key_here"
# Optional: export TRADINGAGENTS_API_URL="http://your-local-ip:8000"
```

## API Basics

All requests use the `$TRADINGAGENTS_TOKEN` as a Bearer token.
The primary endpoint is `POST /v1/analyze`.

## Common Operations

**1. Submit Analysis Job:**
Submit a stock symbol for deep multi-agent investigation.
```bash
curl -X POST "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/analyze" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519.SH"}'
```

**2. Poll Job Status:**
Check if the agents are still working.
```bash
curl "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/jobs/{job_id}" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN"
```

**3. Retrieve Final Result:**
Once the job is `completed`, fetch the full multi-agent report and the final verdict.
```bash
curl "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/jobs/{job_id}/result" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN"
```

## Job Workflow

Deep analysis takes **1 to 5 minutes**.
1. **Extract**: Get the symbol from user query (e.g. "Moutai" or "600519").
2. **Submit**: Call `POST /v1/analyze`.
3. **Inform**: Tell the user that research has started.
4. **Wait**: Poll status every 30s.
5. **Summarize**: When `completed`, fetch result and provide a high-level summary (Decision, Direction, Target Price, Risk).

## Supported Symbols
- **A-Share**: Names (e.g. "茅台") or Codes (`600519.SH`, `300274.SZ`).
- **US Stocks**: `AAPL`, `TSLA`, `NVDA`.

## Notes
- **Polling Rate**: Do not exceed 1 request per 15 seconds.
- **Data Robustness**: If some data sources fail, the system provides inferential logic based on macro/industry trends.
