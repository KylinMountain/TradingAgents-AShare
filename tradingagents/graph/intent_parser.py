"""IntentParser: parse natural language query into structured trading intent."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.prompts import get_prompt
from tradingagents.dataflows.config import get_config

_HORIZON_LABELS = {
    "short": "短线（1-2周，技术面主导）",
    "medium": "中线（1-3月，基本面主导）",
}

# (horizon, agent_type) -> weight hint appended to context block
_WEIGHT_HINTS: Dict[tuple, str] = {
    ("short", "fundamentals"): "本维度为次要参考，简要输出核心风险即可，无需完整基本面分析。",
    ("short", "macro"): "本维度为次要参考，仅关注近期政策冲击信号，简要输出即可。",
    ("medium", "smart_money"): "本维度为次要参考，仅判断大资金方向，简要输出即可。",
    ("medium", "social"): "本维度为次要参考，情绪仅作辅助参考，简要输出即可。",
    ("medium", "game_theory"): "本维度为次要参考，简要输出即可。",
}


def parse_intent(
    query: str,
    llm,
    fallback_ticker: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse natural language query into structured intent dict.

    Returns dict with keys: ticker, horizons, focus_areas, specific_questions, raw_query.
    Falls back gracefully to defaults if LLM output is unparseable.
    """
    config = get_config()
    system_msg = get_prompt("intent_parser_system", config=config)

    try:
        result = llm.invoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=query),
        ])
        raw = result.content.strip()
        # Clean markdown code fences and handle potential trailing commas or minor issues
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        
        # Simple cleanup for common LLM JSON errors (like trailing commas before closing braces)
        raw = re.sub(r",\s*([\]}])", r"\1", raw)
        
        parsed = json.loads(raw)
        return {
            "raw_query": query,
            "ticker": parsed.get("ticker") or fallback_ticker or "",
            "horizons": parsed.get("horizons") or ["short", "medium"],
            "focus_areas": parsed.get("focus_areas") or [],
            "specific_questions": parsed.get("specific_questions") or [],
        }
    except Exception:
        return {
            "raw_query": query,
            "ticker": fallback_ticker or "",
            "horizons": ["short", "medium"],
            "focus_areas": [],
            "specific_questions": [],
        }


def build_horizon_context(
    horizon: str,
    focus_areas: List[str],
    specific_questions: List[str],
    agent_type: Optional[str] = None,
) -> str:
    """Build the horizon context block to prepend to any agent's system prompt."""
    config = get_config()
    template = get_prompt("horizon_context_block", config=config)

    horizon_label = _HORIZON_LABELS.get(horizon, horizon)
    focus_str = "、".join(focus_areas) if focus_areas else "无特殊关注"
    questions_str = "；".join(specific_questions) if specific_questions else "无"
    weight_hint = _WEIGHT_HINTS.get((horizon, agent_type), "") if agent_type else ""

    return template.format(
        horizon_label=horizon_label,
        focus_areas_str=focus_str,
        specific_questions_str=questions_str,
        weight_hint=weight_hint,
    )
