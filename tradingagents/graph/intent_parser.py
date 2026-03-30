"""IntentParser: parse natural language query into structured trading intent."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.agents.utils.context_utils import normalize_user_context
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

    Returns dict with keys: ticker, horizons, focus_areas, specific_questions, user_context, raw_query.
    Falls back gracefully to defaults if LLM output is unparseable.
    """
    config = get_config()
    system_msg = get_prompt("intent_parser_system", config=config)
    fallback_user_context = _extract_user_context_fallback(query)

    try:
        result = llm.invoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=query),
        ])
        raw = result.content.strip()
        # Clean markdown code fences more robustly (handle potential whitespace/newlines)
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
        
        # Simple cleanup for common LLM JSON errors
        raw = re.sub(r",\s*([\]}])", r"\1", raw)
        
        parsed = json.loads(raw) or {}
        parsed_user_context = normalize_user_context(parsed.get("user_context") or {})
        return {
            "raw_query": query,
            "ticker": parsed.get("ticker") or fallback_ticker or "",
            "horizons": parsed.get("horizons") if isinstance(parsed.get("horizons"), list) else ["short"],
            "focus_areas": parsed.get("focus_areas") if isinstance(parsed.get("focus_areas"), list) else [],
            "specific_questions": parsed.get("specific_questions") if isinstance(parsed.get("specific_questions"), list) else [],
            "user_context": _merge_inferred_user_context(parsed_user_context, fallback_user_context),
        }
    except Exception:
        return {
            "raw_query": query,
            "ticker": fallback_ticker or "",
            "horizons": ["short"],
            "focus_areas": [],
            "specific_questions": [],
            "user_context": fallback_user_context,
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


def _merge_inferred_user_context(
    parsed_context: Dict[str, Any],
    fallback_context: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(parsed_context)
    for key, value in fallback_context.items():
        if key in {"cash_available", "current_position", "current_position_pct", "average_cost", "max_loss_pct"}:
            merged[key] = value
            continue
        if key == "constraints":
            existing = [str(item).strip() for item in merged.get("constraints", []) if str(item).strip()]
            for item in value:
                text = str(item).strip()
                if text and text not in existing:
                    existing.append(text)
            if existing:
                merged["constraints"] = existing
            continue
        if key not in merged or merged.get(key) in (None, "", []):
            merged[key] = value
    return normalize_user_context(merged)


def _extract_user_context_fallback(query: str) -> Dict[str, Any]:
    text = (query or "").strip()
    if not text:
        return {}

    context: Dict[str, Any] = {}

    objective_patterns = [
        (r"(想|准备|打算|计划).*建仓|想建仓|准备建仓|打算建仓", "建仓"),
        (r"(想|准备|打算|计划|考虑).*加仓|想加仓|准备加仓|考虑加仓", "加仓"),
        (r"(想|准备|打算|计划|考虑).*减仓|想减仓|准备减仓|考虑减仓", "减仓"),
        (r"(想|准备|打算|计划|考虑).*止损|想止损|准备止损|考虑止损", "止损"),
        (r"继续拿着|继续持有|拿着不动|持有中|被套|套牢", "持有处理"),
        (r"先观察|先观望|继续观察|先看看|观望", "观察"),
    ]
    for pattern, label in objective_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            context["objective"] = label
            break

    risk_keywords = {
        "保守": "保守",
        "稳健": "保守",
        "平衡": "平衡",
        "激进": "激进",
        "高风险": "激进",
    }
    for keyword, label in risk_keywords.items():
        if keyword in text:
            context["risk_profile"] = label
            break

    horizon_keywords = {
        "短线": "短线",
        "短期": "短线",
        "波段": "波段",
        "中线": "中线",
        "中期": "中线",
        "长期": "长期",
    }
    for keyword, label in horizon_keywords.items():
        if keyword in text:
            context["investment_horizon"] = label
            break

    position_keywords = {
        "满仓": 100.0,
        "重仓": 80.0,
        "半仓": 50.0,
        "轻仓": 20.0,
        "空仓": 0.0,
    }
    for keyword, pct in position_keywords.items():
        if keyword in text:
            context["current_position_pct"] = pct
            break

    cash_match = re.search(r"(?:可用资金|现金|仓位资金)[^\d]{0,8}(\d+(?:\.\d+)?)(万|亿)?", text, re.IGNORECASE)
    if cash_match:
        amount = cash_match.group(1)
        unit = cash_match.group(2) or ""
        context["cash_available"] = f"{amount}{unit}"

    patterns = {
        "average_cost": r"(?:成本价?|均价|持仓成本|买入价|在高位)\D{0,6}(\d+(?:\.\d+)?)",
        "max_loss_pct": r"(?:最大(?:亏损|回撤)|容忍亏损|止损(?:位)?|最多(?:只能)?亏)[^\d]{0,8}(\d+(?:\.\d+)?)\s*%",
        "current_position": r"(?:持有|现有|目前有)[^\d]{0,8}(\d+(?:\.\d+)?)\s*股",
        "current_position_pct": r"(?:仓位|持仓占比)[^\d]{0,8}(\d+(?:\.\d+)?)\s*%",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            context[key] = match.group(1)

    constraints: List[str] = []
    constraint_keywords = {
        "不加杠杆": "不加杠杆",
        "不融资": "不融资",
        "不追高": "不追高",
        "只做t+1": "只做T+1",
        "只做T+1": "只做T+1",
        "不能补仓": "不能补仓",
        "不接受隔夜": "不接受隔夜",
    }
    lowered = text.lower()
    for keyword, label in constraint_keywords.items():
        if keyword.lower() in lowered and label not in constraints:
            constraints.append(label)
    if constraints:
        context["constraints"] = constraints

    return normalize_user_context(context)
