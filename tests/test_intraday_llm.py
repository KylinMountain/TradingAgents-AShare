from agents.extensions.models.litellm_model import LitellmModel
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from scheduler.intraday_llm import build_intraday_agent_model


def test_openai_provider_uses_chatcompletions_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    model = build_intraday_agent_model({"llm_provider": "openai", "quick_think_llm": "gpt-4o-mini"})
    assert isinstance(model, OpenAIChatCompletionsModel)
    assert model.model == "gpt-4o-mini"


def test_xai_provider_resolves_env_key_and_base_url(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-xai-key")
    model = build_intraday_agent_model({"llm_provider": "xai", "quick_think_llm": "grok-4-1-fast"})
    assert isinstance(model, OpenAIChatCompletionsModel)
    assert str(model._client.base_url) == "https://api.x.ai/v1/"
    assert model._client.api_key == "test-xai-key"


def test_deepseek_provider(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-ds-key")
    model = build_intraday_agent_model({"llm_provider": "deepseek", "quick_think_llm": "deepseek-chat"})
    assert isinstance(model, OpenAIChatCompletionsModel)
    assert str(model._client.base_url).rstrip("/") == "https://api.deepseek.com"
    assert model._client.api_key == "test-ds-key"


def test_deepseek_provider_honors_backend_url_override(monkeypatch):
    # Regression: deepseek's base_url used to be hardcoded regardless of a
    # configured relay/gateway, unlike OpenAIClient.get_llm()'s original
    # `self.base_url or "https://api.deepseek.com"`.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-ds-key")
    model = build_intraday_agent_model(
        {"llm_provider": "deepseek", "quick_think_llm": "deepseek-chat", "backend_url": "https://relay.example.com/v1"}
    )
    assert str(model._client.base_url).rstrip("/") == "https://relay.example.com/v1"


def test_xai_provider_ignores_backend_url_matching_original_hardcoding(monkeypatch):
    # xai/openrouter/ollama are fully hardcoded in the mirrored original too,
    # so a backend_url override should NOT apply to them (no divergence there).
    monkeypatch.setenv("XAI_API_KEY", "test-xai-key")
    model = build_intraday_agent_model(
        {"llm_provider": "xai", "quick_think_llm": "grok-4-1-fast", "backend_url": "https://relay.example.com/v1"}
    )
    assert str(model._client.base_url) == "https://api.x.ai/v1/"


def test_openai_compatible_model_disables_retries_and_sets_long_timeout(monkeypatch):
    # Mirrors OpenAIClient.get_llm()'s deliberate max_retries=0/timeout=300.0 —
    # otherwise the SDK's default retries can silently re-run an expensive
    # prompt and blow the outer analyze_cause() timeout budget.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    model = build_intraday_agent_model({"llm_provider": "openai", "quick_think_llm": "gpt-4o-mini"})
    assert model._client.max_retries == 0
    assert model._client.timeout == 300.0


def test_ollama_provider_uses_literal_api_key():
    model = build_intraday_agent_model({"llm_provider": "ollama", "quick_think_llm": "llama3"})
    assert isinstance(model, OpenAIChatCompletionsModel)
    assert model._client.api_key == "ollama"
    assert str(model._client.base_url) == "http://localhost:11434/v1/"


def test_anthropic_provider_uses_litellm_with_anthropic_prefix():
    model = build_intraday_agent_model(
        {"llm_provider": "anthropic", "quick_think_llm": "claude-haiku-4-5", "api_key": "test-anthropic-key"}
    )
    assert isinstance(model, LitellmModel)
    assert model.model == "anthropic/claude-haiku-4-5"


def test_anthropic_provider_forwards_backend_url_to_litellm():
    # Regression: base_url used to be silently dropped for anthropic/google,
    # breaking custom-gateway deployments that the main graph's
    # AnthropicClient.get_llm() honors via config["backend_url"].
    model = build_intraday_agent_model(
        {
            "llm_provider": "anthropic",
            "quick_think_llm": "claude-haiku-4-5",
            "api_key": "test-anthropic-key",
            "backend_url": "https://gateway.example.com",
        }
    )
    assert model.base_url == "https://gateway.example.com"


def test_google_provider_uses_gemini_litellm_prefix_not_google():
    model = build_intraday_agent_model({"llm_provider": "google", "quick_think_llm": "gemini-2.5-flash"})
    assert isinstance(model, LitellmModel)
    assert model.model == "gemini/gemini-2.5-flash"


def test_falls_back_to_deep_think_llm_when_quick_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    model = build_intraday_agent_model({"llm_provider": "openai", "deep_think_llm": "gpt-4o"})
    assert model.model == "gpt-4o"


def test_raises_when_no_model_configured():
    import pytest

    with pytest.raises(ValueError):
        build_intraday_agent_model({"llm_provider": "openai"})
