# TradingAgents/graph/signal_processing.py

import re
import json

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

    def parse_verdict_direction(raw_text: str) -> str | None:
        match = re.search(r"<!--\s*VERDICT:\s*(\{.*?\})\s*-->", raw_text, re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(1))
        except Exception:
            return None
        direction = str(payload.get("direction", "")).strip().upper()
        direction_map = {
            "看多": "BUY",
            "BULLISH": "BUY",
            "BUY": "BUY",
            "看空": "SELL",
            "BEARISH": "SELL",
            "SELL": "SELL",
            "中性": "HOLD",
            "NEUTRAL": "HOLD",
            "HOLD": "HOLD",
            "谨慎": "HOLD",
            "CAUTIOUS": "HOLD",
        }
        return direction_map.get(direction)

    def classify(snippet: str) -> str | None:
        snippet_upper = snippet.upper()
        sell_keywords = [
            "SELL",
            "卖出",
            "减持",
            "清仓",
            "空仓",
            "回避",
            "看空",
        ]
        buy_keywords = [
            "BUY",
            "买入",
            "增持",
            "做多",
            "看多",
            "谨慎看多",
            "有条件建仓",
            "条件建仓",
            "建仓",
        ]
        hold_keywords = [
            "HOLD",
            "观望",
            "持有",
            "中性",
        ]

        if any(k in snippet_upper for k in buy_keywords):
            return "BUY"
        if any(k in snippet_upper for k in sell_keywords):
            return "SELL"
        if any(k in snippet_upper for k in hold_keywords):
            return "HOLD"
        return None

    verdict_decision = parse_verdict_direction(text)
    if verdict_decision:
        return verdict_decision

    explicit_patterns = [
        r"最终裁决[:：]\s*([^\n*]+)",
        r"风控委员会最终裁决[:：]\s*([^\n*]+)",
        r"最终建议[:：]\s*([^\n*]+)",
        r"方向[:：]\s*([^\n*]+)",
        r"核心定性[:：]\s*([^\n*]+)",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            decision = classify(match.group(1).strip())
            if decision:
                return decision

    headline = "\n".join(text.splitlines()[:20])
    decision = classify(headline)
    if decision:
        return decision

    decision = classify(upper)
    if decision:
        return decision

    return "UNKNOWN"
