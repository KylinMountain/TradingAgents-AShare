# TradingAgents/graph/propagation.py

from typing import Dict, Any, List, Optional, Mapping
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.agents.utils.context_utils import (
    build_market_context,
    infer_instrument_context,
    normalize_user_context,
    summarize_instrument_context,
    summarize_market_context,
    summarize_user_context,
)


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit

    def create_initial_state(
        self,
        company_name: str,
        trade_date: str,
        user_context: Optional[Mapping[str, Any]] = None,
        selected_analysts: Optional[List[str]] = None,
        request_source: str = "api",
        user_intent: Optional[Dict[str, Any]] = None,
        horizon: str = "short",
    ) -> Dict[str, Any]:
        """Create the initial state for the agent graph."""
        instrument_context = infer_instrument_context(company_name)
        market_context = build_market_context(company_name, str(trade_date))
        normalized_user_context = normalize_user_context(user_context)
        user_context_summary = summarize_user_context(normalized_user_context)
        user_prompt_context = (
            f"{summarize_instrument_context(instrument_context)}\n"
            f"{summarize_market_context(market_context)}\n"
            f"{user_context_summary}"
        )
        state: Dict[str, Any] = {
            "messages": [("human", user_prompt_context)],
            "company_of_interest": company_name,
            "trade_date": str(trade_date),
            "instrument_context": instrument_context,
            "market_context": market_context,
            "user_context": normalized_user_context,
            "workflow_context": {
                "context_version": "v1",
                "request_source": request_source,
                "selected_analysts": selected_analysts or [],
            },
            "investment_debate_state": InvestDebateState(
                {
                    "history": "",
                    "bull_history": "",
                    "bear_history": "",
                    "current_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "risk_debate_state": RiskDebateState(
                {
                    "history": "",
                    "aggressive_history": "",
                    "conservative_history": "",
                    "neutral_history": "",
                    "latest_speaker": "",
                    "current_aggressive_response": "",
                    "current_conservative_response": "",
                    "current_neutral_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "market_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "news_report": "",
            "macro_report": "",
            "smart_money_report": "",
            "game_theory_report": "",
            "investment_plan": "",
            "trader_investment_plan": "",
            "final_trade_decision": "",
            "sender": "",
            "metadata": {},
            "analyst_traces": [],
            "horizon": horizon,
            "short_term_result": None,
            "medium_term_result": None,
        }
        if user_intent is not None:
            state["user_intent"] = user_intent
        return state

    def get_graph_args(self, callbacks: Optional[List] = None) -> Dict[str, Any]:
        """Get arguments for the graph invocation.

        Args:
            callbacks: Optional list of callback handlers for tool execution tracking.
                       Note: LLM callbacks are handled separately via LLM constructor.
        """
        config = {"recursion_limit": self.max_recur_limit}
        if callbacks:
            config["callbacks"] = callbacks
        return {
            "stream_mode": "values",
            "config": config,
        }
