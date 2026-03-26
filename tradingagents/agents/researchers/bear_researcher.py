from langchain_core.messages import AIMessage
import time
import json
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context
from tradingagents.agents.utils.agent_states import current_tracker_var
from tradingagents.agents.utils.debate_utils import (
    format_claim_subset_for_prompt,
    format_claims_for_prompt,
    update_debate_state_with_payload,
)


def create_bear_researcher(llm, memory):
    async def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        claims = investment_debate_state.get("claims", [])
        focus_claim_ids = investment_debate_state.get("focus_claim_ids", [])
        unresolved_claim_ids = investment_debate_state.get("unresolved_claim_ids", [])
        round_summary = investment_debate_state.get("round_summary", "")
        round_goal = investment_debate_state.get("round_goal", "")

        horizon = state.get("horizon", "medium")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, agent_type="bear")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = horizon_ctx + get_prompt("bear_prompt", config=get_config()).format(
            market_research_report=market_research_report,
            sentiment_report=sentiment_report,
            news_report=news_report,
            fundamentals_report=fundamentals_report,
            history=history,
            current_response=current_response,
            past_memory_str=past_memory_str,
            focus_claims_text=format_claim_subset_for_prompt(claims, focus_claim_ids),
            unresolved_claims_text=format_claim_subset_for_prompt(claims, unresolved_claim_ids),
            claims_text=format_claims_for_prompt(claims),
            round_summary=round_summary or "暂无轮次摘要，请先攻击最核心的多头 claim。",
            round_goal=round_goal,
        )

        # ── 实现 Token 级流式输出 ──────────────────
        tracker = current_tracker_var.get()
        full_content = ""
        async for chunk in llm.astream(prompt):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_content += content
            if tracker:
                tracker._emit_token("Bear Researcher", "investment_debate_state", content)

        # ── 推送辩论消息 ──
        debate_round = int(investment_debate_state.get("count", 0) or 0) + 1
        if tracker:
            tracker.emit_debate_message(
                debate="research", agent="Bear Researcher",
                round_num=debate_round, content=full_content,
            )

        new_investment_debate_state = update_debate_state_with_payload(
            state=investment_debate_state,
            raw_response=full_content,
            speaker_label="Bear Analyst",
            speaker_key="Bear",
            stance="bearish",
            history_key="bear_history",
            marker="DEBATE_STATE",
            claim_prefix="INV",
            domain="investment",
            speaker_field="current_speaker",
        )

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
