from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping


def extract_tagged_json(text: str, tag: str) -> dict[str, Any]:
    pattern = rf"<!--\s*{re.escape(tag)}:\s*(\{{.*?\}})\s*-->"
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def strip_tagged_json(text: str, tag: str) -> str:
    pattern = rf"\n?<!--\s*{re.escape(tag)}:\s*\{{.*?\}}\s*-->\s*"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()


def format_claims_for_prompt(
    claims: Iterable[Mapping[str, Any]] | None,
    focus_claim_ids: Iterable[str] | None = None,
    empty_message: str = "当前没有已登记 claim，本轮请先提出 1 到 2 条最关键 claim。",
) -> str:
    claim_list = list(claims or [])
    if not claim_list:
        return empty_message

    focus_set = {str(item) for item in (focus_claim_ids or []) if str(item).strip()}
    lines: list[str] = []
    for claim in claim_list:
        claim_id = str(claim.get("claim_id", "")).strip()
        status = str(claim.get("status", "open")).strip() or "open"
        speaker = str(claim.get("speaker", "")).strip() or "Unknown"
        summary = str(claim.get("claim", "")).strip() or "未提供 claim 文本"
        evidence = claim.get("evidence") or []
        evidence_text = "；".join(str(item).strip() for item in evidence if str(item).strip()) or "无明确证据"
        prefix = "* " if claim_id in focus_set else "- "
        lines.append(
            f"{prefix}{claim_id} [{status}] {speaker}: {summary} | 证据: {evidence_text}"
        )
    return "\n".join(lines)


def format_claim_subset_for_prompt(
    claims: Iterable[Mapping[str, Any]] | None,
    claim_ids: Iterable[str] | None,
    empty_message: str = "当前没有未解决 claim。",
) -> str:
    claim_id_set = {str(item) for item in (claim_ids or []) if str(item).strip()}
    if not claim_id_set:
        return empty_message
    subset = [claim for claim in (claims or []) if str(claim.get("claim_id", "")) in claim_id_set]
    return format_claims_for_prompt(subset, focus_claim_ids=claim_id_set, empty_message=empty_message)


def summarize_game_theory_signals(signals: Mapping[str, Any] | None) -> str:
    payload = signals or {}
    if not payload:
        return "暂无结构化博弈信号。"

    players = payload.get("players") or []
    likely_actions = payload.get("likely_actions") or {}
    if isinstance(likely_actions, dict):
        action_lines = []
        for key, value in likely_actions.items():
            if isinstance(value, list):
                value_text = " / ".join(str(item) for item in value if str(item).strip())
            else:
                value_text = str(value)
            action_lines.append(f"{key}: {value_text}")
        actions_text = "; ".join(action_lines) if action_lines else "未提供"
    else:
        actions_text = str(likely_actions)

    return "\n".join(
        [
            f"局面: {payload.get('board', '未提供')}",
            f"参与者: {', '.join(str(item) for item in players) if players else '未提供'}",
            f"主导策略: {payload.get('dominant_strategy', '未提供')}",
            f"脆弱均衡: {payload.get('fragile_equilibrium', '未提供')}",
            f"潜在动作: {actions_text}",
            f"反共识信号: {payload.get('counter_consensus_signal', '未提供')}",
            f"置信度: {payload.get('confidence', '未提供')}",
        ]
    )


def summarize_risk_feedback(feedback: Mapping[str, Any] | None) -> str:
    payload = feedback or {}
    verdict = str(payload.get("latest_risk_verdict", "")).strip()
    if not verdict:
        return "当前没有待处理的风控回退要求。"

    hard_constraints = payload.get("hard_constraints") or []
    soft_constraints = payload.get("soft_constraints") or []
    preconditions = payload.get("execution_preconditions") or []
    de_risk_triggers = payload.get("de_risk_triggers") or []

    return "\n".join(
        [
            f"风控裁决: {verdict}",
            f"是否要求重做: {'是' if payload.get('revision_required') else '否'}",
            f"打回原因: {payload.get('revision_reason', '未提供')}",
            f"硬约束: {'; '.join(str(item) for item in hard_constraints) if hard_constraints else '无'}",
            f"软约束: {'; '.join(str(item) for item in soft_constraints) if soft_constraints else '无'}",
            f"执行前提: {'; '.join(str(item) for item in preconditions) if preconditions else '无'}",
            f"降风险触发器: {'; '.join(str(item) for item in de_risk_triggers) if de_risk_triggers else '无'}",
        ]
    )


def default_round_goal(domain: str, next_count: int) -> str:
    goals = {
        "investment": [
            "建立最核心的正反两方 claim，并明确为何是现在。",
            "优先攻击对手最脆弱的假设，不要扩散议题。",
            "围绕时间窗口与触发条件，判断交易时机是否成立。",
            "围绕失败路径与失效条件，判断谁低估了回撤风险。",
            "检查剩余分歧是否仍有信息增量，否则准备收口。",
        ],
        "risk": [
            "建立最关键的执行风险 claim，明确风险预算冲突点。",
            "围绕仓位、止损、流动性约束，攻击对手最薄弱一环。",
            "判断哪些风险是可接受波动，哪些风险是硬性红线。",
            "逼迫双方给出可执行替代方案，而不是抽象立场。",
            "检查是否还存在未解决的高影响执行风险，否则准备收口。",
        ],
    }
    domain_key = domain if domain in goals else "investment"
    goal_list = goals[domain_key]
    index = min(max(next_count - 1, 0), len(goal_list) - 1)
    return goal_list[index]


def update_debate_state_with_payload(
    *,
    state: Mapping[str, Any],
    raw_response: str,
    speaker_label: str,
    speaker_key: str,
    stance: str,
    history_key: str,
    marker: str,
    claim_prefix: str,
    domain: str,
    speaker_field: str,
    store_current_response: bool = True,
) -> dict[str, Any]:
    payload = extract_tagged_json(raw_response, marker)
    cleaned_response = strip_tagged_json(raw_response, marker)

    claims = [dict(item) for item in state.get("claims", [])]
    claim_map = {
        str(item.get("claim_id", "")).strip(): item
        for item in claims
        if str(item.get("claim_id", "")).strip()
    }

    claim_counter = int(state.get("claim_counter", 0) or 0)
    responded_claim_ids = _filter_known_claim_ids(payload.get("responded_claim_ids"), claim_map)
    resolved_claim_ids = _filter_known_claim_ids(payload.get("resolved_claim_ids"), claim_map)
    unresolved_claim_ids = _filter_known_claim_ids(payload.get("unresolved_claim_ids"), claim_map)

    open_claim_ids = set(_string_list(state.get("open_claim_ids")))
    resolved_set = set(_string_list(state.get("resolved_claim_ids")))
    unresolved_set = set(_string_list(state.get("unresolved_claim_ids")))

    for claim_id in responded_claim_ids:
        if claim_id in claim_map and claim_map[claim_id].get("status") == "open":
            claim_map[claim_id]["status"] = "addressed"

    for claim_id in resolved_claim_ids:
        if claim_id in claim_map:
            claim_map[claim_id]["status"] = "resolved"
        open_claim_ids.discard(claim_id)
        unresolved_set.discard(claim_id)
        resolved_set.add(claim_id)

    for claim_id in unresolved_claim_ids:
        if claim_id in claim_map:
            claim_map[claim_id]["status"] = "unresolved"
        open_claim_ids.add(claim_id)
        unresolved_set.add(claim_id)
        resolved_set.discard(claim_id)

    for claim_payload in payload.get("new_claims", []) or []:
        claim_text = str(claim_payload.get("claim", "")).strip()
        if not claim_text:
            continue
        claim_counter += 1
        claim_id = f"{claim_prefix}-{claim_counter}"
        evidence = [
            str(item).strip()
            for item in (claim_payload.get("evidence") or [])[:3]
            if str(item).strip()
        ]
        confidence = _safe_float(claim_payload.get("confidence"), 0.6)
        target_claim_ids = _filter_known_claim_ids(claim_payload.get("target_claim_ids"), claim_map)
        claim_entry = {
            "claim_id": claim_id,
            "speaker": speaker_label,
            "speaker_key": speaker_key,
            "stance": stance,
            "claim": claim_text,
            "evidence": evidence,
            "confidence": confidence,
            "status": "open",
            "target_claim_ids": target_claim_ids,
            "round_index": int(state.get("count", 0) or 0) + 1,
        }
        claims.append(claim_entry)
        claim_map[claim_id] = claim_entry
        open_claim_ids.add(claim_id)

    next_focus_claim_ids = _filter_known_claim_ids(payload.get("next_focus_claim_ids"), claim_map)
    if not next_focus_claim_ids:
        preferred_ids = list(unresolved_set) + [cid for cid in open_claim_ids if cid not in unresolved_set]
        next_focus_claim_ids = preferred_ids[:2]

    summary = str(payload.get("round_summary", "")).strip() or _fallback_summary(cleaned_response)
    round_goal = str(payload.get("round_goal", "")).strip() or default_round_goal(
        domain, int(state.get("count", 0) or 0) + 1
    )

    argument = f"{speaker_label}: {cleaned_response}"
    new_state = dict(state)
    updates = {
        "history": _append_history(state.get("history", ""), argument),
        history_key: _append_history(state.get(history_key, ""), argument),
        "current_speaker": speaker_key,
        speaker_field: speaker_key,
        "count": int(state.get("count", 0) or 0) + 1,
        "claims": claims,
        "claim_counter": claim_counter,
        "open_claim_ids": sorted(open_claim_ids),
        "resolved_claim_ids": sorted(resolved_set),
        "unresolved_claim_ids": sorted(unresolved_set),
        "focus_claim_ids": next_focus_claim_ids,
        "round_summary": summary,
        "round_goal": round_goal,
    }
    if store_current_response:
        updates["current_response"] = argument
    new_state.update(updates)
    return new_state


def _append_history(history: Any, argument: str) -> str:
    existing = str(history or "").strip()
    if not existing:
        return argument
    return f"{existing}\n{argument}"


def _filter_known_claim_ids(values: Any, claim_map: Mapping[str, Any]) -> list[str]:
    result = []
    for item in _string_list(values):
        if item in claim_map:
            result.append(item)
    return result


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for item in values:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _safe_float(value: Any, fallback: float) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return fallback


def _fallback_summary(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return "本轮未提取到有效摘要。"
    return compact[:120]


def build_empty_risk_debate_state() -> dict[str, Any]:
    return {
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
        "claims": [],
        "focus_claim_ids": [],
        "open_claim_ids": [],
        "resolved_claim_ids": [],
        "unresolved_claim_ids": [],
        "round_summary": "",
        "round_goal": default_round_goal("risk", 1),
        "claim_counter": 0,
    }
