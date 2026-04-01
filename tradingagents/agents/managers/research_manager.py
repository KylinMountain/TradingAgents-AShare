from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.agents.utils.agent_states import current_tracker_var
from tradingagents.agents.utils.debate_utils import (
    format_claim_subset_for_prompt,
    format_claims_for_prompt,
)


def create_research_manager(llm, memory):
    async def research_manager_node(state) -> dict:
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        smart_money_report = state.get("smart_money_report", "")
        market_impact_report = state.get("market_impact_report", "")
        volume_price_report = state.get("volume_price_report", "")

        investment_debate_state = state["investment_debate_state"]
        claims = investment_debate_state.get("claims", [])
        unresolved_claim_ids = investment_debate_state.get("unresolved_claim_ids", [])
        round_summary = investment_debate_state.get("round_summary", "")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}\n\n{market_impact_report}\n\n{volume_price_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = get_prompt("research_manager_prompt", config=get_config()).format(
            past_memory_str=past_memory_str,
            history=history,
            smart_money_report=smart_money_report,
            volume_price_report=volume_price_report,
            sentiment_report=sentiment_report,
            market_impact_report=market_impact_report,
            claims_text=format_claims_for_prompt(claims),
            unresolved_claims_text=format_claim_subset_for_prompt(claims, unresolved_claim_ids),
            round_summary=round_summary or "暂无轮次摘要。",
        )
        
        # ── 实现 Token 级流式输出 ──────────────────
        tracker = current_tracker_var.get()
        full_content = ""
        async for chunk in llm.astream(prompt):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_content += content
            if tracker:
                tracker._emit_token("Research Manager", "investment_plan", content)
                tracker.emit_debate_token(
                    debate="research", agent="Research Manager",
                    round_num=-1, token=content,
                )

        # ── 推送辩论裁决（标记流式结束）──
        if tracker:
            tracker.emit_debate_message(
                debate="research", agent="Research Manager",
                round_num=-1, content=full_content, is_verdict=True,
            )

        new_investment_debate_state = {
            "judge_decision": full_content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_speaker": investment_debate_state.get("current_speaker", ""),
            "current_response": full_content,
            "count": investment_debate_state["count"],
            "claims": claims,
            "focus_claim_ids": investment_debate_state.get("focus_claim_ids", []),
            "open_claim_ids": investment_debate_state.get("open_claim_ids", []),
            "resolved_claim_ids": investment_debate_state.get("resolved_claim_ids", []),
            "unresolved_claim_ids": unresolved_claim_ids,
            "round_summary": round_summary,
            "round_goal": investment_debate_state.get("round_goal", ""),
            "claim_counter": investment_debate_state.get("claim_counter", 0),
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": full_content,
        }

    return research_manager_node
