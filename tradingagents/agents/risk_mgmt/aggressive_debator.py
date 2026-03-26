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


def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")
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

        prompt = get_prompt("aggressive_prompt", config=get_config()).format(
            trader_decision=trader_decision,
            market_research_report=market_research_report,
            sentiment_report=sentiment_report,
            news_report=news_report,
            fundamentals_report=fundamentals_report,
            history=history,
            current_conservative_response=current_conservative_response,
            current_neutral_response=current_neutral_response,
            focus_claims_text=format_claim_subset_for_prompt(claims, focus_claim_ids),
            unresolved_claims_text=format_claim_subset_for_prompt(claims, unresolved_claim_ids),
            claims_text=format_claims_for_prompt(claims, empty_message="当前没有已登记风险 claim，本轮请先提出最关键的执行风险。"),
            round_summary=round_summary or "暂无风险轮次摘要，请先建立核心风险 claim。",
            round_goal=round_goal,
        )

        response = llm.invoke(prompt)

        clean_response = strip_tagged_json(response.content, "RISK_STATE")
        new_risk_debate_state = update_debate_state_with_payload(
            state=risk_debate_state,
            raw_response=response.content,
            speaker_label="Aggressive Analyst",
            speaker_key="Aggressive",
            stance="aggressive",
            history_key="aggressive_history",
            marker="RISK_STATE",
            claim_prefix="RISK",
            domain="risk",
            speaker_field="latest_speaker",
            store_current_response=False,
        )
        # ── 推送辩论消息 ──
        tracker = current_tracker_var.get()
        if tracker:
            try:
                debate_round = int(risk_debate_state.get("count", 0) or 0) + 1
            except (ValueError, TypeError):
                debate_round = 1
            tracker.emit_debate_message(
                debate="risk", agent="Aggressive Analyst",
                round_num=debate_round, content=clean_response,
            )

        new_risk_debate_state["current_aggressive_response"] = f"Aggressive Analyst: {clean_response}"
        new_risk_debate_state["current_conservative_response"] = risk_debate_state.get("current_conservative_response", "")
        new_risk_debate_state["current_neutral_response"] = risk_debate_state.get("current_neutral_response", "")

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
