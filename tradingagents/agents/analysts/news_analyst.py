import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context
from tradingagents.agents.utils.agent_states import current_tracker_var


def _extract_verdict(text):
    import re, json
    m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            return d.get("direction", "中性"), "中"
        except Exception:
            pass
    return "中性", "低"


def create_news_analyst(llm, data_collector=None):
    async def _safe(tool, payload):
        try:
            return await asyncio.to_thread(tool.invoke, payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    async def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = "short"  # 新闻面固定短期视角
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("news_system_message", config=config)
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, agent_type="news")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            data_window = pool.get("_data_window", "14天" if horizon == "short" else "90天")
            stock_news = pool.get("news", "无数据")
            global_news = pool.get("global_news", "无数据")
        else:
            from datetime import datetime, timedelta
            from tradingagents.agents.utils.agent_utils import get_news, get_global_news
            days = 14 if horizon == "short" else 30
            end_dt = datetime.strptime(current_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days)
            
            # Parallelize fallback fetches
            results = await asyncio.gather(
                _safe(get_news, {
                    "ticker": ticker, "start_date": start_dt.strftime("%Y-%m-%d"), "end_date": current_date,
                }),
                _safe(get_global_news, {
                    "curr_date": current_date, "look_back_days": days, "limit": 10,
                })
            )
            stock_news, global_news = results
            data_window = f"{days}天"

        messages = [
            SystemMessage(content=(
                system_message
                + "\n\n请严格基于提供的新闻资料输出报告，全程使用中文。"
            )),
            HumanMessage(content=(
                horizon_ctx + "\n"
                f"以下是 {ticker} 在 {current_date} 的新闻资料（{data_window}）。\n\n"
                f"【get_news】\n{stock_news}\n\n"
                f"【get_global_news】\n{global_news}\n"
            )),
        ]

        # ── 实现 Token 级流式输出 ──────────────────
        tracker = current_tracker_var.get()
        full_content = ""
        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_content += content
            if tracker:
                tracker._emit_token("News Analyst", "news_report", content)

        verdict, confidence = _extract_verdict(full_content)
        return {
            "news_report": full_content,
            "analyst_traces": [{
                "agent": "news_analyst",
                "horizon": horizon,
                "data_window": data_window,
                "key_finding": f"新闻分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return news_analyst_node
