import asyncio
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context
from tradingagents.agents.utils.agent_states import current_tracker_var, extract_verdict

# List of technical indicators to retrieve
MARKET_INDICATORS = [
    "close_50_sma",
    "close_200_sma",
    "close_10_ema",
    "rsi",
    "macd",
    "boll",
    "boll_ub",
    "boll_lb",
    "atr",
    "vwma",
]


def create_market_analyst(llm, data_collector=None):
    async def market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = "short"  # 技术面固定短期视角
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])
        
        config = get_config()
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, agent_type="market")
        system_message = get_prompt("market_system_message", config=config)

        if data_collector is not None:
            pool = data_collector.get(ticker, current_date)
            if pool is not None:
                windowed = data_collector.get_window(pool, horizon, current_date)
                stock_data = windowed.get("stock_data", "无数据")
                indicators = windowed.get("indicators", {})
                data_window = windowed.get("_data_window", "14天")
            else:
                stock_data, indicators, data_window = await _fetch_direct(ticker, current_date, horizon)
        else:
            stock_data, indicators, data_window = await _fetch_direct(ticker, current_date, horizon)

        indicator_blocks = [
            f"【{ind}】\n{indicators.get(ind, '无数据')}"
            for ind in MARKET_INDICATORS
        ]

        messages = [
            SystemMessage(content=system_message + "\n\n请全程使用中文。"),
            HumanMessage(content=(
                horizon_ctx + "\n"
                f"以下是 {ticker} 在 {current_date} 的 K 线数据与指标（数据窗口：{data_window}）。\n\n"
                f"【get_stock_data】\n{stock_data}\n\n"
                + "\n\n".join(indicator_blocks)
            )),
        ]

        # ── 实现 Token 级流式输出 ──────────────────
        tracker = current_tracker_var.get()
        full_content = ""
        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_content += content
            if tracker:
                tracker._emit_token("Market Analyst", "market_report", content)
        
        verdict, confidence = extract_verdict(full_content)

        return {
            "market_report": full_content,
            "analyst_traces": [{
                "agent": "market_analyst",
                "horizon": horizon,
                "data_window": data_window,
                "key_finding": f"市场技术面结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return market_analyst_node


async def _fetch_direct(ticker, current_date, horizon):
    from tradingagents.agents.utils.agent_utils import get_stock_data, get_indicators

    async def _safe(tool, payload):
        try:
            return await asyncio.to_thread(tool.invoke, payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    days = 14 if horizon == "short" else 90
    end_dt = datetime.strptime(current_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=days)
    
    # Run stock data fetch and all indicator fetches in parallel
    tasks = {
        "stock_data": _safe(get_stock_data, {
            "symbol": ticker, "start_date": start_dt.strftime("%Y-%m-%d"), "end_date": current_date,
        })
    }
    for ind in MARKET_INDICATORS:
        tasks[ind] = _safe(get_indicators, {
            "symbol": ticker, "indicator": ind, "curr_date": current_date, "look_back_days": days,
        })
    
    keys = list(tasks.keys())
    results = await asyncio.gather(*[tasks[k] for k in keys])
    res_map = dict(zip(keys, results))
    
    stock_data = res_map.pop("stock_data")
    return stock_data, res_map, f"{days}天"
