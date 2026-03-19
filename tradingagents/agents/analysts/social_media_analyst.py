from langchain_core.messages import HumanMessage, SystemMessage
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context


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


def create_social_media_analyst(llm, data_collector=None):
    import asyncio

    async def _safe(tool, payload):
        try:
            return await asyncio.to_thread(tool.invoke, payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    async def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "short")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("social_system_message", config=config)
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "social")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            news_text = pool.get("news", "无数据")
            zt_data = pool.get("zt_pool", "无数据")
            hot_stocks = pool.get("hot_stocks", "无数据")
        else:
            from datetime import datetime, timedelta
            from tradingagents.agents.utils.agent_utils import get_news, get_zt_pool, get_hot_stocks_xq
            days = 7
            end_dt = datetime.strptime(current_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days)
            
            # Parallelize fallback fetches
            results = await asyncio.gather(
                _safe(get_news, {
                    "ticker": ticker, "start_date": start_dt.strftime("%Y-%m-%d"), "end_date": current_date,
                }),
                _safe(get_zt_pool, {"date": current_date}),
                _safe(get_hot_stocks_xq, {})
            )
            news_text, zt_data, hot_stocks = results

        messages = [
            SystemMessage(content=(
                horizon_ctx + system_message
                + "\n\n请严格基于提供的舆情数据输出报告，全程使用中文。"
            )),
            HumanMessage(content=(
                f"以下是 {ticker} 在 {current_date} 的舆情近似资料。\n\n"
                f"【get_news】\n{news_text}\n\n"
                f"【涨停池数据】\n{zt_data}\n\n"
                f"【雪球热门股票】\n{hot_stocks}\n"
            )),
        ]

        result = await llm.ainvoke(messages)
        verdict, confidence = _extract_verdict(result.content)
        return {
            "sentiment_report": result.content,
            "analyst_traces": [{
                "agent": "social_media_analyst",
                "horizon": horizon,
                "data_window": "7天",
                "key_finding": f"舆情分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return social_media_analyst_node
