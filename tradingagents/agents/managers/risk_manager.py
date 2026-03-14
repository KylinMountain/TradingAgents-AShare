import time
import json
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.agents.utils.context_utils import build_agent_context_view
from tradingagents.agents.utils.debate_utils import (
    format_claim_subset_for_prompt,
    format_claims_for_prompt,
)


def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:

        company_name = state["company_of_interest"]

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        context_view = build_agent_context_view(state, "risk")
        claims = risk_debate_state.get("claims", [])
        unresolved_claim_ids = risk_debate_state.get("unresolved_claim_ids", [])
        prompt = get_prompt("risk_manager_prompt", config=get_config()).format(
            trader_plan=trader_plan,
            past_memory_str=past_memory_str,
            history=history,
            market_context_summary=context_view["market_context_summary"],
            user_context_summary=context_view["user_context_summary"],
            claims_text=format_claims_for_prompt(claims, empty_message="当前没有已登记风控 claim。"),
            unresolved_claims_text=format_claim_subset_for_prompt(claims, unresolved_claim_ids),
            round_summary=risk_debate_state.get("round_summary", "暂无风险轮次摘要。"),
        )

        response = llm.invoke(prompt)

        new_risk_debate_state = {
            "judge_decision": response.content,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
            "claims": claims,
            "focus_claim_ids": risk_debate_state.get("focus_claim_ids", []),
            "open_claim_ids": risk_debate_state.get("open_claim_ids", []),
            "resolved_claim_ids": risk_debate_state.get("resolved_claim_ids", []),
            "unresolved_claim_ids": unresolved_claim_ids,
            "round_summary": risk_debate_state.get("round_summary", ""),
            "round_goal": risk_debate_state.get("round_goal", ""),
            "claim_counter": risk_debate_state.get("claim_counter", 0),
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response.content,
        }

    return risk_manager_node
