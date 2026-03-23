from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessageChunk

from .base_client import BaseLLMClient
from .validators import validate_model


def _extract_text_from_content(content):
    """Extract text from extended thinking content blocks.

    When extended thinking is enabled, Anthropic returns content as a list:
        [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "..."}]
    This helper extracts only the text blocks and joins them into a string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") not in ("thinking",):
                    # Unknown block type, try to get text
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


class NormalizedChatAnthropic(ChatAnthropic):
    """ChatAnthropic with normalized content output.

    Claude models with extended thinking return content as a list of blocks.
    This normalizes to string for consistent downstream handling.
    """

    def _normalize_content(self, response):
        response.content = _extract_text_from_content(response.content)
        return response

    def invoke(self, input, config=None, **kwargs):
        return self._normalize_content(super().invoke(input, config, **kwargs))

    async def ainvoke(self, input, config=None, **kwargs):
        return self._normalize_content(await super().ainvoke(input, config, **kwargs))

    def _normalize_chunk(self, chunk):
        if isinstance(chunk, AIMessageChunk) and isinstance(chunk.content, list):
            chunk.content = _extract_text_from_content(chunk.content)
        return chunk

    def stream(self, input, config=None, **kwargs):
        for chunk in super().stream(input, config, **kwargs):
            yield self._normalize_chunk(chunk)

    async def astream(self, input, config=None, **kwargs):
        async for chunk in super().astream(input, config, **kwargs):
            yield self._normalize_chunk(chunk)


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return configured ChatAnthropic instance."""
        llm_kwargs = {"model": self.model}

        if self.base_url:
            # ChatAnthropic auto-appends /v1, so strip it if present
            base = self.base_url.rstrip("/")
            if base.endswith("/v1"):
                base = base[:-3]
            llm_kwargs["base_url"] = base

        for key in ("timeout", "max_retries", "api_key", "max_tokens", "callbacks"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return NormalizedChatAnthropic(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for Anthropic."""
        return validate_model("anthropic", self.model)
