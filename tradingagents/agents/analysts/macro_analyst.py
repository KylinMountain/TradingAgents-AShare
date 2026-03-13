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


def create_macro_analyst(llm, data_collector=None):
    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    def macro_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        print(f"[Macro Analyst] START {ticker} {current_date}")
        horizon = state.get("horizon", "medium")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("macro_system_message", config=config) or ""
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "macro")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            board_flow = pool.get("fund_flow_board", "无数据")
            recent_news = pool.get("news", "无数据")
        else:
            from datetime import datetime, timedelta
            from tradingagents.agents.utils.agent_utils import get_board_fund_flow, get_news
            days = 7
            end_dt = datetime.strptime(current_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days)
            board_flow = _safe(get_board_fund_flow, {})
            recent_news = _safe(get_news, {
                "ticker": ticker, "start_date": start_dt.strftime("%Y-%m-%d"), "end_date": current_date,
            })

        messages = [
            SystemMessage(content=(
                horizon_ctx + system_message
                + "\n\n请严格基于提供的数据输出报告，全程使用中文。"
            )),
            HumanMessage(content=(
                f"请分析 {ticker} 在 {current_date} 的宏观与板块环境。\n\n"
                f"【今日行业板块资金流向】\n{board_flow}\n\n"
                f"【近期相关新闻】\n{recent_news}"
            )),
        ]

        result = llm.invoke(messages)
        print(f"[Macro Analyst] DONE {ticker}, report length={len(result.content)}")
        verdict, confidence = _extract_verdict(result.content)
        return {
            "macro_report": result.content,
            "analyst_traces": [{
                "agent": "macro_analyst",
                "horizon": horizon,
                "data_window": "板块数据",
                "key_finding": f"宏观板块分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return macro_analyst_node
