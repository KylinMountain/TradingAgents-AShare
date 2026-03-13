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
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
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


_SHORT_KEYWORDS = [
    "短线", "短期", "近期", "未来几天", "几天", "本周", "下周", "明天", "今天",
    "日线", "短炒", "T+", "波段短", "近几日",
]
_MEDIUM_KEYWORDS = [
    "中线", "中期", "几个月", "季度", "半年", "中长", "波段", "趋势",
]
_FOCUS_MAP = {
    "量价": ["量价关系", "成交量"],
    "技术": ["技术面", "K线", "均线", "MACD", "RSI"],
    "基本面": ["基本面", "财报", "业绩"],
    "资金": ["主力资金", "龙虎榜", "资金流向"],
    "消息": ["新闻", "公告", "利好", "利空"],
    "宏观": ["宏观", "板块", "行业"],
}


def build_intent_from_query(
    query: str,
    ticker: str,
) -> Dict[str, Any]:
    """Build user intent from query using keyword matching — no LLM call.

    Reuses ticker already extracted by _ai_extract_symbol_and_date.
    """
    text = query.lower()

    has_short = any(kw in query for kw in _SHORT_KEYWORDS)
    has_medium = any(kw in query for kw in _MEDIUM_KEYWORDS)

    if has_short and not has_medium:
        horizons = ["short"]
    elif has_medium and not has_short:
        horizons = ["medium"]
    else:
        horizons = ["short", "medium"]

    focus_areas: List[str] = []
    for label, keywords in _FOCUS_MAP.items():
        if any(kw in query for kw in keywords):
            focus_areas.append(label)

    # Extract "能否达到X%" style specific questions
    specific_questions: List[str] = []
    import re as _re
    price_q = _re.findall(r"能否[^，。？\n]{0,20}[%％涨跌]", query)
    specific_questions.extend(price_q)

    return {
        "raw_query": query,
        "ticker": ticker,
        "horizons": horizons,
        "focus_areas": focus_areas,
        "specific_questions": specific_questions,
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
