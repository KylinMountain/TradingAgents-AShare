import unittest
from unittest.mock import MagicMock, patch
from api.main import _build_runtime_config
from tradingagents.llm_clients.openai_client import OpenAIClient

class TestConfigFallback(unittest.TestCase):
    def test_intelligent_fallback_logic(self):
        """测试 _build_runtime_config 的互相借用逻辑"""
        # 场景 1: 用户只配置了 deep_think_llm，漏了 quick
        overrides = {
            "deep_think_llm": "claude-3-5-sonnet",
            "quick_think_llm": ""
        }
        config = _build_runtime_config(overrides)
        self.assertEqual(config["quick_think_llm"], "claude-3-5-sonnet", "Quick 应该借用 Deep 的值")

        # 场景 2: 用户只配置了 quick_think_llm，漏了 deep
        overrides = {
            "quick_think_llm": "gpt-4o",
            "deep_think_llm": None
        }
        config = _build_runtime_config(overrides)
        self.assertEqual(config["deep_think_llm"], "gpt-4o", "Deep 应该借用 Quick 的值")

    def test_openai_client_hard_fallback(self):
        """测试 OpenAIClient 的最后一道防线：空字符串自动重置为默认模型"""
        # 场景：即使通过了 _build_runtime_config，如果最终传入空串
        client = OpenAIClient(model="", provider="openai")
        self.assertEqual(client.model, "gpt-4o-mini", "空字符串应强制降级为 gpt-4o-mini")
        
        client_ollama = OpenAIClient(model=None, provider="ollama")
        self.assertEqual(client_ollama.model, "llama3", "Ollama 空模型应降级为 llama3")

if __name__ == "__main__":
    unittest.main()
