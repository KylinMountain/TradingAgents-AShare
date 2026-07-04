# TradingAgents/graph/signal_processing.py

import json
import logging
import re

from langchain_openai import ChatOpenAI
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt

logger = logging.getLogger(__name__)


class SignalProcessor:
    """Processes trading signals to extract actionable decisions."""

    def __init__(self, quick_thinking_llm: ChatOpenAI, confidence_threshold: int = 40):
        """Initialize with an LLM for processing.

        Args:
            quick_thinking_llm: LLM instance for signal extraction fallback.
            confidence_threshold: minimum confidence (0-100) to accept non-HOLD
                signals. Signals below this threshold are forced to HOLD.
        """
        self.quick_thinking_llm = quick_thinking_llm
        self.confidence_threshold = confidence_threshold

    @staticmethod
    def _extract_confidence(text: str) -> int:
        """Extract confidence value from VERDICT JSON block in text.

        Returns 0-100 int if found, 0 if unparseable (treats as no-confidence).
        """
        m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', text or "", re.DOTALL)
        if not m:
            return 0
        try:
            d = json.loads(m.group(1))
            raw = d.get("confidence")
            if raw is None:
                return 50  # missing field → assume medium confidence
            v = float(raw)
            if v > 1.0:
                return int(v)
            return int(v * 100)
        except Exception:
            return 0

    def process_signal(self, full_signal: str) -> str:
        """Process a trading signal to extract decision, filtering low confidence.

        Returns BUY, SELL, or HOLD. Signals with confidence below threshold
        are forced to HOLD regardless of the stated direction.
        """
        if not full_signal:
            return "HOLD"

        decision = _extract_decision_keyword(full_signal)
        if not decision:
            messages = [
                ("system", get_prompt("signal_extractor_system", config=get_config())),
                ("human", full_signal),
            ]
            response = str(self.quick_thinking_llm.invoke(messages).content).strip().upper()
            decision = response if response in {"BUY", "SELL", "HOLD"} else "HOLD"

        # ── 置信度过滤 ──
        if decision != "HOLD":
            confidence = self._extract_confidence(full_signal)
            if confidence < self.confidence_threshold:
                logger.info(
                    "置信度过滤：信号=%s, 置信度=%d < 阈值=%d, 强制退守HOLD",
                    decision, confidence, self.confidence_threshold,
                )
                return "HOLD"

        return decision


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
            "偏多": "BUY",
            "BULLISH": "BUY",
            "BUY": "BUY",
            "看空": "SELL",
            "偏空": "SELL",
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
            "偏空",
        ]
        buy_keywords = [
            "BUY",
            "买入",
            "增持",
            "做多",
            "看多",
            "偏多",
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
