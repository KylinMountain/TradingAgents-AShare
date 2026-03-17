from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context
from tradingagents.agents.utils.agent_utils import get_seat_history


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


def create_smart_money_analyst(llm, data_collector=None):
    llm_with_tools = llm.bind_tools([get_seat_history])

    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    def smart_money_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "short")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("smart_money_system_message", config=config) or ""
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "smart_money")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            fund_flow = pool.get("fund_flow_individual", "无数据")
            lhb = pool.get("lhb", "无数据")
            volume = pool.get("indicators", {}).get("vwma", "无数据")
        else:
            from tradingagents.agents.utils.agent_utils import (
                get_individual_fund_flow, get_lhb_detail, get_indicators,
            )
            fund_flow = _safe(get_individual_fund_flow, {"symbol": ticker})
            lhb = _safe(get_lhb_detail, {"symbol": ticker, "date": current_date})
            volume = _safe(get_indicators, {
                "symbol": ticker, "indicator": "volume",
                "curr_date": current_date, "look_back_days": 20,
            })

        # Base context messages
        base_messages = [
            SystemMessage(content=(
                horizon_ctx + system_message
                + "\n\n请严格基于提供的量化数据输出分析，全程使用中文。"
            )),
            HumanMessage(content=(
                f"请分析 {ticker} 在 {current_date} 的主力资金行为。\n\n"
                f"【近5日主力资金净流向】\n{fund_flow}\n\n"
                f"【龙虎榜数据】\n{lhb}\n\n"
                f"【成交量指标(vwma)】\n{volume}"
            )),
        ]

        # Extract previous ReAct messages for this specific node
        react_messages = []
        for msg in state.get("messages", []):
            if isinstance(msg, AIMessage) and msg.name == "Smart Money Analyst":
                react_messages.append(msg)
            elif isinstance(msg, ToolMessage) and msg.name == "get_seat_history":
                react_messages.append(msg)

        # Combine
        messages_to_invoke = base_messages + react_messages

        print(f"[Smart Money Analyst] Invoking LLM (history: {len(react_messages)} msgs)...")
        result = llm_with_tools.invoke(messages_to_invoke)
        result.name = "Smart Money Analyst"

        if result.tool_calls:
            print(f"[Smart Money Analyst] Tool call requested: {result.tool_calls}")
            # If there are tool calls, we return them in messages to trigger the ToolNode
            return {"messages": [result]}
        else:
            print(f"[Smart Money Analyst] DONE {ticker}, report length={len(result.content)}")
            verdict, confidence = _extract_verdict(result.content)
            # Final output, don't return messages to avoid polluting global state, just return reports
            return {
                "smart_money_report": result.content,
                "analyst_traces": [{
                    "agent": "smart_money_analyst",
                    "horizon": horizon,
                    "data_window": "近期可用",
                    "key_finding": f"主力资金分析结论：{verdict}",
                    "verdict": verdict,
                    "confidence": confidence,
                }],
            }

    return smart_money_analyst_node
