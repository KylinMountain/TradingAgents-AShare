"""Tests for tradingagents.llm_clients.factory."""

import pytest

from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.openai_client import OpenAIClient


def test_deepseek_provider_creates_openai_client():
    client = create_llm_client(provider="deepseek", model="deepseek-chat")
    assert isinstance(client, OpenAIClient)
    assert client.provider == "deepseek"


def test_deepseek_default_base_url(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    client = create_llm_client(provider="deepseek", model="deepseek-chat")
    llm = client.get_llm()
    assert llm.openai_api_base == "https://api.deepseek.com"


def test_unsupported_provider_still_raises():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        create_llm_client(provider="not-a-real-provider", model="foo")
