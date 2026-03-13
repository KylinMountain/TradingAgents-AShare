---
name: tradingagents-analysis
description: Use when the user asks to analyze a stock, research market trends, or has any investment-related questions for TradingAgents. Supports natural language queries.
env:
  TRADINGAGENTS_API_URL: "TradingAgents API base URL (default: https://api.510168.xyz)"
  TRADINGAGENTS_TOKEN: "Bearer token — login at https://app.510168.xyz → Settings → create an API Token"
---

# TradingAgents Analysis Skill (Natural Language)

Ask questions like "How is CATL doing?", "Analyze 600519.SH", or "Is it a good time to buy semiconductors?".

## ⚠️ Performance Expectation
- **Duration**: Deep analysis takes **1 to 5 minutes**.
- **User Feedback**: Always inform the user that a multi-agent investigation has started.

## API Reference

### 1. Intent Detection & Quick Chat (POST /v1/chat/completions)
Send the user's message directly to the TradingAgents backend. The backend will automatically detect the symbol and start an analysis job if needed.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "帮我看看阳光电源目前的表现，适合买入吗？"}
  ],
  "stream": false
}
```

**Response (Intent Detected):**
If the backend detects an analysis intent, it returns a message like `[Analysis Started: 300274.SZ @ 2026-03-13] job_id: <id>`.

### 2. Job Lifecycle (for Analysis Jobs)
- **Status**: `GET /v1/jobs/{job_id}`
- **Result**: `GET /v1/jobs/{job_id}/result`

## AI Implementation Strategy
1. **Chat First**: Instead of trying to extract the symbol yourself, send the user's full query to `/v1/chat/completions`.
2. **Handle Job ID**: Look for a `job_id` in the chat response. If found, start the polling loop.
3. **Wait & Poll**: Use a 30s interval to poll `/v1/jobs/{id}` until status is `completed`.
4. **Final Summary**: Retrieve the full report from `/v1/jobs/{id}/result` and provide a high-level expert summary.

## Common Symbols
- Supports Chinese names (e.g., 贵州茅台)
- Supports 6-digit codes (e.g., 000001)
- Prefers suffixes for accuracy (.SH / .SZ)
