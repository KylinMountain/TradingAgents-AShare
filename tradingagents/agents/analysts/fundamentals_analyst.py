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


def create_fundamentals_analyst(llm, data_collector=None):
    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "medium")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("fundamentals_system_message", config=config)
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "fundamentals")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            outputs = {k: pool.get(k, "无数据") for k in
                       ["fundamentals", "balance_sheet", "cashflow", "income_statement"]}
        else:
            from tradingagents.agents.utils.agent_utils import (
                get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement,
            )
            outputs = {
                "fundamentals": _safe(get_fundamentals, {"ticker": ticker, "curr_date": current_date}),
                "balance_sheet": _safe(get_balance_sheet, {"ticker": ticker, "freq": "quarterly", "curr_date": current_date}),
                "cashflow": _safe(get_cashflow, {"ticker": ticker, "freq": "quarterly", "curr_date": current_date}),
                "income_statement": _safe(get_income_statement, {"ticker": ticker, "freq": "quarterly", "curr_date": current_date}),
            }

        messages = [
            SystemMessage(content=horizon_ctx + system_message + "\n\n请全程使用中文。"),
            HumanMessage(content=(
                f"以下是 {ticker} 在 {current_date} 的基本面资料。\n\n"
                f"【get_fundamentals】\n{outputs['fundamentals']}\n\n"
                f"【get_balance_sheet】\n{outputs['balance_sheet']}\n\n"
                f"【get_cashflow】\n{outputs['cashflow']}\n\n"
                f"【get_income_statement】\n{outputs['income_statement']}\n"
            )),
        ]

        result = llm.invoke(messages)
        verdict, confidence = _extract_verdict(result.content)
        return {
            "fundamentals_report": result.content,
            "analyst_traces": [{
                "agent": "fundamentals_analyst",
                "horizon": horizon,
                "data_window": "财报周期",
                "key_finding": f"基本面分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return fundamentals_analyst_node
