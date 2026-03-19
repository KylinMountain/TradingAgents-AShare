import os
import time
from json import JSONDecodeError
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient
from .validators import validate_model


class UnifiedChatOpenAI(ChatOpenAI):
    """ChatOpenAI subclass that strips incompatible params for certain models."""

    def __init__(self, **kwargs):
        parse_retries = kwargs.pop("response_parse_retries", 2)
        parse_retry_delay = kwargs.pop("response_parse_retry_delay", 1.0)
        model = kwargs.get("model", "")
        if self._is_reasoning_model(model):
            kwargs.pop("temperature", None)
            kwargs.pop("top_p", None)
        super().__init__(**kwargs)
        object.__setattr__(self, "response_parse_retries", parse_retries)
        object.__setattr__(self, "response_parse_retry_delay", parse_retry_delay)

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        """Retry transient malformed-response errors from OpenAI-compatible gateways."""
        attempts = self.response_parse_retries + 1
        last_err = None
        for i in range(attempts):
            try:
                return super().invoke(input=input, config=config, **kwargs)
            except (JSONDecodeError, ValueError) as exc:
                # Some OpenAI-compatible gateways occasionally return non-JSON payloads.
                last_err = exc
                if i == attempts - 1:
                    break
                time.sleep(self.response_parse_retry_delay * (i + 1))
        raise last_err

    @staticmethod
    def _is_reasoning_model(model: str) -> bool:
        """Check if model is a reasoning model that doesn't support temperature."""
        model_lower = model.lower()
        return (
            model_lower.startswith("o1")
            or model_lower.startswith("o3")
            or "gpt-5" in model_lower
        )


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI, Ollama, OpenRouter, and xAI providers."""

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        provider: str = "openai",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    def get_llm(self) -> Any:
        """Return configured ChatOpenAI instance."""
        llm_kwargs = {"model": self.model}

        # Default temperature=0 for non-reasoning models; user-provided value in kwargs takes precedence
        if not UnifiedChatOpenAI._is_reasoning_model(self.model):
            llm_kwargs["temperature"] = self.kwargs.get("temperature", 0)

        if self.provider == "xai":
            llm_kwargs["base_url"] = "https://api.x.ai/v1"
            api_key = os.environ.get("XAI_API_KEY")
            if api_key:
                llm_kwargs["api_key"] = api_key
        elif self.provider == "openrouter":
            llm_kwargs["base_url"] = "https://openrouter.ai/api/v1"
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if api_key:
                llm_kwargs["api_key"] = api_key
        elif self.provider == "ollama":
            llm_kwargs["base_url"] = "http://localhost:11434/v1"
            llm_kwargs["api_key"] = "ollama"  # Ollama doesn't require auth
        elif self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in (
            "timeout", "max_retries", "reasoning_effort", "api_key", "callbacks",
            "response_parse_retries", "response_parse_retry_delay",
        ):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return UnifiedChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for the provider."""
        return validate_model(self.provider, self.model)
