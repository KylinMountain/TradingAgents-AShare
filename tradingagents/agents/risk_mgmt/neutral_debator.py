import time
import json
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.agents.utils.agent_states import current_tracker_var
from tradingagents.agents.utils.debate_utils import (
    format_claim_subset_for_prompt,
    format_claims_for_prompt,
    strip_tagged_json,
    update_debate_state_with_payload,
)


def create_neutral_debator(llm):
    async def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        claims = risk_debate_state.get("claims", [])
        focus_claim_ids = risk_debate_state.get("focus_claim_ids", [])
        unresolved_claim_ids = risk_debate_state.get("unresolved_claim_ids", [])
        round_summary = risk_debate_state.get("round_summary", "")
        round_goal = risk_debate_state.get("round_goal", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = get_prompt("neutral_prompt", config=get_config()).format(
            trader_decision=trader_decision,
            market_research_report=market_research_report,
            sentiment_report=sentiment_report,
            news_report=news_report,
            fundamentals_report=fundamentals_report,
            history=history,
            current_aggressive_response=current_aggressive_response,
            current_conservative_response=current_conservative_response,
            focus_claims_text=format_claim_subset_for_prompt(claims, focus_claim_ids),
            unresolved_claims_text=format_claim_subset_for_prompt(claims, unresolved_claim_ids),
            claims_text=format_claims_for_prompt(claims, empty_message="当前没有已登记风险 claim，本轮请先识别最关键的执行矛盾。"),
            round_summary=round_summary or "暂无风险轮次摘要，请先识别真正有信息增量的风险分歧。",
            round_goal=round_goal,
        )

        # ── 流式输出 ──
        tracker = current_tracker_var.get()
        try:
            debate_round = int(risk_debate_state.get("count", 0) or 0) // 3 + 1
        except (ValueError, TypeError):
            debate_round = 1
        full_content = ""
        async for chunk in llm.astream(prompt):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_content += content
            if tracker:
                tracker.emit_debate_token(
                    debate="risk", agent="Neutral Analyst",
                    round_num=debate_round, token=content,
                )

        clean_response = strip_tagged_json(full_content, "RISK_STATE")
        new_risk_debate_state = update_debate_state_with_payload(
            state=risk_debate_state,
            raw_response=full_content,
            speaker_label="Neutral Analyst",
            speaker_key="Neutral",
            stance="neutral",
            history_key="neutral_history",
            marker="RISK_STATE",
            claim_prefix="RISK",
            domain="risk",
            speaker_field="latest_speaker",
            store_current_response=False,
        )
        if tracker:
            tracker.emit_debate_message(
                debate="risk", agent="Neutral Analyst",
                round_num=debate_round, content=clean_response,
            )

        new_risk_debate_state["current_aggressive_response"] = risk_debate_state.get(
            "current_aggressive_response", ""
        )
        new_risk_debate_state["current_conservative_response"] = risk_debate_state.get(
            "current_conservative_response", ""
        )
        new_risk_debate_state["current_neutral_response"] = f"Neutral Analyst: {clean_response}"

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
