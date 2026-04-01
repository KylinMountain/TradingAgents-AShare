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


def create_market_impact_analyst(llm, data_collector=None):
    async def _safe(tool, payload):
        try:
            return await asyncio.to_thread(tool.invoke, payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    async def market_impact_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        print(f"[Market Impact Analyst] START {ticker} {current_date}")
        horizon = "short"  # geopolitical events primarily affect short-term
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("market_impact_system_message", config=config) or ""
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, agent_type="market_impact")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            data_window = pool.get("_data_window", "14天" if horizon == "short" else "90天")
            global_news = pool.get("global_news", "无数据")
            stock_news = pool.get("news", "无数据")
            geopolitical_news = pool.get("geopolitical_news", "")
        else:
            from datetime import datetime, timedelta
            from tradingagents.agents.utils.agent_utils import get_global_news, get_news
            days = 14
            end_dt = datetime.strptime(current_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days)

            results = await asyncio.gather(
                _safe(get_global_news, {
                    "curr_date": current_date, "look_back_days": days, "limit": 20,
                }),
                _safe(get_news, {
                    "ticker": ticker, "start_date": start_dt.strftime("%Y-%m-%d"), "end_date": current_date,
                }),
            )
            global_news, stock_news = results
            data_window = f"{days}天"

            # Fallback: fetch geopolitical data directly
            geopolitical_news = ""
            try:
                from tradingagents.dataflows.geopolitical_fetcher import fetch_geopolitical_news
                geo_data = await asyncio.to_thread(fetch_geopolitical_news, 15)
                geopolitical_news = geo_data.get("formatted", "")
            except Exception:
                pass

        # Build prompt with all data sources
        data_sections = [
            horizon_ctx,
            f"\n以下是截至 {current_date} 的全球重大事件与地缘政治资料（{data_window}），"
            f"以及 {ticker} 的相关新闻。\n",
        ]

        if geopolitical_news:
            data_sections.append(
                f"【实时地缘政治数据 — Trump Truth Social / 国际通讯社 / 中文财经快讯】\n{geopolitical_news}\n"
            )

        data_sections.append(f"【get_global_news — 全球新闻（akshare）】\n{global_news}\n")
        data_sections.append(f"【get_news — 个股相关新闻】\n{stock_news}\n")

        messages = [
            SystemMessage(content=(
                system_message
                + "\n\n请严格基于提供的新闻资料输出报告，全程使用中文。"
            )),
            HumanMessage(content="\n".join(data_sections)),
        ]

        # Token-level streaming
        tracker = current_tracker_var.get()
        full_content = ""
        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_content += content
            if tracker:
                tracker._emit_token("Market Impact Analyst", "market_impact_report", content)

        print(f"[Market Impact Analyst] DONE {ticker}, report length={len(full_content)}")
        verdict, confidence = _extract_verdict(full_content)
        return {
            "market_impact_report": full_content,
            "analyst_traces": [{
                "agent": "market_impact_analyst",
                "horizon": horizon,
                "data_window": data_window,
                "key_finding": f"地缘冲击分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return market_impact_analyst_node
