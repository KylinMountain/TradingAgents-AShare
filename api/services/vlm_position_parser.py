"""Parse broker position screenshots into structured position data.

Uses the generic VLM service (vlm_service.py) for image recognition.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from api.services.vlm_service import call_vlm

logger = logging.getLogger(__name__)

POSITION_PROMPT = """你是一个持仓截图解析助手。用户会上传券商 App 的持仓截图。
请从图片中提取所有股票持仓信息，返回 JSON 数组，每个元素包含：
- symbol: 股票代码（6位数字，如 "600519"）
- name: 股票名称
- current_position: 持仓数量（股）
- average_cost: 成本价（元），如果图中没有则为 null
- market_value: 市值（元），如果图中没有则为 null

只返回 JSON 数组，不要有其他文字。如果图片中没有持仓信息，返回空数组 []。

请解析这张持仓截图。"""


def parse_position_image(
    image_bytes: bytes,
    content_type: str,
) -> list[dict[str, Any]]:
    """Parse a broker screenshot and return extracted positions."""
    raw = call_vlm(image_bytes, POSITION_PROMPT, content_type)
    return _parse_response(raw)


def _parse_response(raw: str) -> list[dict[str, Any]]:
    """Extract JSON array from VLM response, tolerating markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[vlm-parser] Failed to parse VLM response as JSON: %s", text[:200])
        return []

    if not isinstance(items, list):
        return []

    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).strip()
        if not symbol:
            continue
        result.append({
            "symbol": symbol,
            "name": item.get("name"),
            "current_position": _to_float(item.get("current_position")),
            "average_cost": _to_float(item.get("average_cost")),
            "market_value": _to_float(item.get("market_value")),
        })
    return result


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
