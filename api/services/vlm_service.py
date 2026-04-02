"""Generic Vision Language Model service.

Server-side configuration via environment variables:
  TA_VLM_API_KEY      — required, API key for the VLM provider
  TA_VLM_BASE_URL     — base URL (default: https://open.bigmodel.cn/api/paas/v4)
  TA_VLM_MODEL        — model name (default: glm-4.6v-flash)
  TA_VLM_PROVIDER     — "openai" (default) or "anthropic"
  TA_VLM_RAW_BASE64   — "1" (default) to send raw base64, "0" for data URI prefix
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def get_vlm_config() -> dict[str, str]:
    """Load VLM config from environment variables."""
    api_key = os.getenv("TA_VLM_API_KEY", "").strip()
    if not api_key:
        raise ValueError("未配置 VLM API Key（环境变量 TA_VLM_API_KEY）")
    return {
        "provider": os.getenv("TA_VLM_PROVIDER", "openai").strip(),
        "api_key": api_key,
        "base_url": os.getenv("TA_VLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").strip(),
        "model": os.getenv("TA_VLM_MODEL", "glm-4.6v-flash").strip(),
    }


def call_vlm(
    image_bytes: bytes,
    prompt: str,
    content_type: str = "image/png",
) -> str:
    """Send an image + text prompt to the configured VLM and return raw text response."""
    config = get_vlm_config()
    provider = config.get("provider", "openai")
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    media_type = content_type or "image/png"

    if provider == "anthropic":
        return _call_anthropic(base64_image, media_type, prompt, config)
    return _call_openai_compatible(base64_image, media_type, prompt, config)


def _call_openai_compatible(base64_image: str, media_type: str, prompt: str, config: dict) -> str:
    from openai import OpenAI
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config.get("base_url") or None,
    )
    raw_base64 = os.getenv("TA_VLM_RAW_BASE64", "1").strip() in ("1", "true", "yes")
    image_url = base64_image if raw_base64 else f"data:{media_type};base64,{base64_image}"

    response = client.chat.completions.create(
        model=config.get("model", "glm-4.6v-flash"),
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]},
        ],
        max_tokens=2000,
    )
    raw = response.choices[0].message.content or ""
    logger.info("[vlm] response (first 300 chars): %s", raw[:300])
    return raw


def _call_anthropic(base64_image: str, media_type: str, prompt: str, config: dict) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config["api_key"])
    response = client.messages.create(
        model=config.get("model", "claude-sonnet-4-20250514"),
        max_tokens=2000,
        messages=[
            {"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64_image}},
                {"type": "text", "text": prompt},
            ]},
        ],
    )
    raw = response.content[0].text if response.content else ""
    logger.info("[vlm] response (first 300 chars): %s", raw[:300])
    return raw
