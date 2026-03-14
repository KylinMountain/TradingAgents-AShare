---
name: tradingagents-analysis
description: Professional multi-agent investment research tool for A-Share. Analyzes market, technicals, fundamentals, sentiment, and smart money using a 12-agent debate system.
homepage: https://app.510168.xyz
repository: https://github.com/KylinMountain/TradingAgents-AShare
env:
  TRADINGAGENTS_API_URL:
    description: "TradingAgents API base URL"
    default: "https://api.510168.xyz"
  TRADINGAGENTS_TOKEN:
    description: "Bearer token — generate at Settings → API Tokens"
    required: true
primary_credential: TRADINGAGENTS_TOKEN
metadata: {"clawdbot":{"emoji":"📈"}}
---

# tradingagents-analysis

Use the TradingAgents API to perform deep multi-agent stock analysis and get structured trading recommendations for A-Share stocks.

## 🔒 Privacy & Security

- **Data Transmission**: This skill sends the **target symbol** (or name) to the configured backend. It does NOT access your local files or sensitive personal data.
- **Backend Ownership**: The default API (`https://api.510168.xyz`) is the official project endpoint. 
- **Self-Hosting**: You can fully control your data by hosting the backend yourself. See our [Docker Deployment Guide](https://github.com/KylinMountain/TradingAgents-AShare#4-docker-一键部署-推荐) for more info.

## Setup

1. Login at https://app.510168.xyz
2. Go to **Settings** → **API Tokens**
3. Configure your environment:
```bash
export TRADINGAGENTS_TOKEN="ta-sk-your_key_here"
```

## API Basics

The primary endpoint is `POST /v1/analyze`. It automatically resolves stock names to codes using natural language processing.

## Common Operations

**Submit Analysis Job:**
Submit a stock by its **Natural Language Name** or **Standard Code**.
```bash
# Example 1: Using name (e.g. "帮我分析一下贵州茅台")
curl -X POST "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/analyze" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "帮我分析一下贵州茅台"}'

# Example 2: Using code (e.g. "Analyze 300274.SZ")
curl -X POST "${TRADINGAGENTS_API_URL:-https://api.510168.xyz}/v1/analyze" \
  -H "Authorization: Bearer $TRADINGAGENTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "Please analyze 300274.SZ"}'
```

**Check Job Status / Retrieve Result:**
- Status: `GET /v1/jobs/{job_id}`
- Result: `GET /v1/jobs/{job_id}/result`

## Job Workflow

Analysis is a compute-heavy process involving a 12-agent debate and takes **1 to 5 minutes**. 

1. **Extract**: Identify the stock from user query (e.g. "帮我看看宁德时代" -> "宁德时代").
2. **Submit**: Call `POST /v1/analyze` with the target name/code.
3. **Wait**: Inform the user: "Starting multi-agent research. This typically takes 2-3 minutes. I'll monitor the agents for you."
4. **Poll**: Check `/v1/jobs/{job_id}` every 30s until status is `completed`.
5. **Summary**: Retrieve results and present the **Decision** (BUY/SELL/HOLD), **Market Direction**, and **Target Price**.

## Supported Inputs

- **Chinese Stock Names**: "阳光电源", "比亚迪", "中际旭创".
- **Standard Codes**: `002594.SZ`, `601012.SH`.

## Notes
- **Polling Rate**: Do not poll faster than every 15 seconds.
- **Robustness**: If certain data is missing, agents will provide logical inferences based on macro trends.
