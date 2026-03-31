from langchain_core.messages import AIMessage
import functools
import time
import json
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.agents.utils.agent_states import current_tracker_var
from tradingagents.agents.utils.context_utils import build_agent_context_view
from tradingagents.agents.utils.debate_utils import (
    build_empty_risk_debate_state,
    summarize_risk_feedback,
)


def create_trader(llm, memory):
    async def trader_node(state, name):
        company_name = state["company_of_interest"]
        investment_plan = state["investment_plan"]
        previous_trader_plan = state.get("trader_investment_plan", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        risk_feedback_state = state.get("risk_feedback_state", {})

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        config = get_config()
        context_view = build_agent_context_view(state, "trader")
        risk_feedback_summary = summarize_risk_feedback(risk_feedback_state)

        messages = [
            {
                "role": "system",
                "content": get_prompt("trader_system_prompt", config=config),
            },
            {
                "role": "user",
                "content": get_prompt("trader_user_prompt", config=config).format(
                    company_name=company_name,
                    investment_plan=investment_plan,
                    previous_trader_plan=previous_trader_plan or "无",
                    instrument_context_summary=context_view["instrument_context_summary"],
                    market_context_summary=context_view["market_context_summary"],
                    user_context_summary=context_view["user_context_summary"],
                    risk_feedback_summary=risk_feedback_summary,
                    past_memory_str=past_memory_str,
                ),
            },
        ]

        # ── 实现 Token 级流式输出 ──────────────────
        tracker = current_tracker_var.get()
        full_content = ""
        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_content += content
            if tracker:
                tracker._emit_token("Trader", "trader_investment_plan", content)

        result = AIMessage(content=full_content)
        updated_feedback_state = dict(risk_feedback_state)
        if updated_feedback_state.get("revision_required"):
            updated_feedback_state["revision_required"] = False

        response_state = {
            "messages": [result],
            "trader_investment_plan": full_content,
            "sender": name,
        }
        if risk_feedback_state.get("latest_risk_verdict") == "revise":
            response_state["risk_debate_state"] = build_empty_risk_debate_state()
            response_state["risk_feedback_state"] = updated_feedback_state

        return response_state

    return functools.partial(trader_node, name="Trader")
