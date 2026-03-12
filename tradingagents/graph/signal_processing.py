# TradingAgents/graph/signal_processing.py

from langchain_openai import ChatOpenAI
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt


class SignalProcessor:
    """Processes trading signals to extract actionable decisions."""

    def __init__(self, quick_thinking_llm: ChatOpenAI):
        """Initialize with an LLM for processing."""
        self.quick_thinking_llm = quick_thinking_llm

    def process_signal(self, full_signal: str) -> str:
        """
        Process a full trading signal to extract the core decision.

        Args:
            full_signal: Complete trading signal text

        Returns:
            Extracted decision (BUY, SELL, or HOLD)
        """
        if not full_signal:
            return "HOLD"

        decision = _extract_decision_keyword(full_signal)
        if decision:
            return decision

        messages = [
            (
                "system",
                get_prompt("signal_extractor_system", config=get_config()),
            ),
            ("human", full_signal),
        ]

        response = str(self.quick_thinking_llm.invoke(messages).content).strip().upper()
        if response in {"BUY", "SELL", "HOLD"}:
            return response
        return "HOLD"


def _extract_decision_keyword(text: str) -> str | None:
    """Rule-based decision extraction to keep UI consistent with final decision text."""
    upper = text.upper()

    sell_keywords = [
        "SELL",
        "卖出",
        "减持",
        "清仓",
        "空仓",
        "回避",
    ]
    buy_keywords = [
        "BUY",
        "买入",
        "增持",
        "做多",
    ]
    hold_keywords = [
        "HOLD",
        "观望",
        "持有",
    ]

    if any(k in upper for k in sell_keywords):
        return "SELL"
    if any(k in upper for k in buy_keywords):
        return "BUY"
    if any(k in upper for k in hold_keywords):
        return "HOLD"
    return None
