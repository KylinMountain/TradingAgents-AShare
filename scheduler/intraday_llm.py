"""Adapt TradingAgents' existing multi-provider LLM config into an openai-agents
SDK ``Model`` instance, without introducing any new environment variables.

The intraday cause-attribution agent (scheduler/intraday_agent.py) needs an
``agents.Agent``-compatible model. openai-agents natively only speaks the
OpenAI Chat Completions/Responses protocol, so providers that already use
that protocol (openai/ollama/openrouter/xai/deepseek — see
tradingagents/llm_clients/openai_client.py) are wired directly via
``OpenAIChatCompletionsModel``. anthropic/google use openai-agents' litellm
extension instead, resolved from the exact same config/env vars the main
graph already uses.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from agents.extensions.models.litellm_model import LitellmModel
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

# provider -> (default base_url, env var name for API key). deepseek's default
# can still be overridden by config["backend_url"] (see _build_openai_compatible_model)
# to mirror OpenAIClient.get_llm()'s `self.base_url or "https://api.deepseek.com"`;
# xai/openrouter/ollama are hardcoded in the original too, so no override there.
_OPENAI_COMPATIBLE_ENDPOINTS = {
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),  # api_key is the literal "ollama"
    "deepseek": ("https://api.deepseek.com", "DEEPSEEK_API_KEY"),
}
_BACKEND_URL_OVERRIDABLE_PROVIDERS = {"deepseek"}

# provider -> litellm model-string prefix (google's is "gemini", not "google")
_LITELLM_PREFIXES = {
    "anthropic": "anthropic",
    "google": "gemini",
}

# Mirrors OpenAIClient.get_llm()'s deliberate "极致稳定性配置": zero retries
# (a silent SDK-level retry can double-run an expensive prompt and still blow
# the outer analyze_cause() timeout) and a generous per-call timeout.
_MAX_RETRIES = 0
_REQUEST_TIMEOUT_SECONDS = 300.0


def build_intraday_agent_model(config: Dict[str, Any]):
    """Build an openai-agents Model for the configured provider + quick_think_llm.

    ``config`` is the same runtime config dict the main TradingAgentsGraph
    uses (``config["llm_provider"]``, ``config["quick_think_llm"]``,
    ``config.get("backend_url")``, ``config.get("api_key")``).
    """
    provider = str(config.get("llm_provider", "openai")).lower()
    model_name = config.get("quick_think_llm") or config.get("deep_think_llm")
    if not model_name:
        raise ValueError("config missing quick_think_llm/deep_think_llm")

    if provider in _LITELLM_PREFIXES:
        return _build_litellm_model(provider, model_name, config)

    return _build_openai_compatible_model(provider, model_name, config)


def _build_openai_compatible_model(provider: str, model_name: str, config: Dict[str, Any]):
    if provider in _OPENAI_COMPATIBLE_ENDPOINTS:
        default_base_url, env_key_name = _OPENAI_COMPATIBLE_ENDPOINTS[provider]
        if provider in _BACKEND_URL_OVERRIDABLE_PROVIDERS:
            base_url = config.get("backend_url") or default_base_url
        else:
            base_url = default_base_url
        if provider == "ollama":
            api_key = "ollama"
        else:
            api_key = os.environ.get(env_key_name) if env_key_name else None
    else:
        # Plain "openai" (or an unrecognized value defaulting to openai-compatible):
        # same resolution as OpenAIClient.get_llm()'s fallthrough branch.
        base_url = config.get("backend_url") or "https://api.openai.com/v1"
        api_key = config.get("api_key") or None  # None -> AsyncOpenAI reads OPENAI_API_KEY itself

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=_MAX_RETRIES,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


def _build_litellm_model(provider: str, model_name: str, config: Dict[str, Any]):
    prefix = _LITELLM_PREFIXES[provider]
    litellm_model_name = f"{prefix}/{model_name}"
    api_key = config.get("api_key") or None  # None -> litellm reads the provider's standard env var
    base_url = config.get("backend_url") or None  # None -> litellm uses the provider's default endpoint
    return LitellmModel(model=litellm_model_name, api_key=api_key, base_url=base_url)
