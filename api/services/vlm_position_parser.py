"""Parse broker position screenshots using Vision Language Models.

VLM configuration is server-side via environment variables:
  TA_VLM_API_KEY      — required, API key for the VLM provider
  TA_VLM_BASE_URL     — base URL (default: https://open.bigmodel.cn/api/paas/v4)
  TA_VLM_MODEL        — model name (default: glm-4.6v-flashx)
  TA_VLM_PROVIDER     — "openai" (default) or "anthropic"
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个持仓截图解析助手。用户会上传券商 App 的持仓截图。
请从图片中提取所有股票持仓信息，返回 JSON 数组，每个元素包含：
- symbol: 股票代码（6位数字，如 "600519"）
- name: 股票名称
- current_position: 持仓数量（股）
- average_cost: 成本价（元），如果图中没有则为 null
- market_value: 市值（元），如果图中没有则为 null

只返回 JSON 数组，不要有其他文字。如果图片中没有持仓信息，返回空数组 []。"""


def _get_vlm_config() -> dict[str, str]:
    """Load VLM config from environment variables."""
    api_key = os.getenv("TA_VLM_API_KEY", "").strip()
    if not api_key:
        raise ValueError("未配置 VLM API Key（环境变量 TA_VLM_API_KEY）")
    return {
        "provider": os.getenv("TA_VLM_PROVIDER", "openai").strip(),
        "api_key": api_key,
        "base_url": os.getenv("TA_VLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").strip(),
        "model": os.getenv("TA_VLM_MODEL", "glm-4.6v-flashx").strip(),
    }


def parse_position_image(
    image_bytes: bytes,
    content_type: str,
) -> list[dict[str, Any]]:
    """Parse a broker screenshot and return extracted positions."""
    vlm_config = _get_vlm_config()
    raw = _call_vlm(image_bytes, content_type, vlm_config)
    return _parse_response(raw)


def _call_vlm(
    image_bytes: bytes,
    content_type: str,
    vlm_config: dict[str, Any],
) -> str:
    """Call VLM API with the image and return raw text response."""
    provider = vlm_config.get("provider", "openai")
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    media_type = content_type or "image/png"

    if provider == "anthropic":
        return _call_anthropic(base64_image, media_type, vlm_config)
    return _call_openai_compatible(base64_image, media_type, vlm_config)


def _call_openai_compatible(base64_image: str, media_type: str, vlm_config: dict) -> str:
    from openai import OpenAI
    client = OpenAI(
        api_key=vlm_config["api_key"],
        base_url=vlm_config.get("base_url") or None,
    )
    # Some providers (e.g. ZhipuAI) expect raw base64 without data URI prefix;
    # others (OpenAI, etc.) expect the full data URI. Use TA_VLM_RAW_BASE64=1 for raw.
    raw_base64 = os.getenv("TA_VLM_RAW_BASE64", "1").strip() in ("1", "true", "yes")
    image_url = base64_image if raw_base64 else f"data:{media_type};base64,{base64_image}"

    response = client.chat.completions.create(
        model=vlm_config.get("model", "glm-4.6v-flashx"),
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": SYSTEM_PROMPT + "\n\n请解析这张持仓截图。"},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]},
        ],
        max_tokens=2000,
    )
    return response.choices[0].message.content or "[]"


def _call_anthropic(base64_image: str, media_type: str, vlm_config: dict) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=vlm_config["api_key"])
    response = client.messages.create(
        model=vlm_config.get("model", "claude-sonnet-4-20250514"),
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64_image}},
                {"type": "text", "text": "请解析这张持仓截图。"},
            ]},
        ],
    )
    return response.content[0].text if response.content else "[]"


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
