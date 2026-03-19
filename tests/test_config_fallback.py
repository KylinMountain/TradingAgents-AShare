import unittest
from unittest.mock import MagicMock, patch
import os

# 模拟环境变量，因为 api.main 会在导入时读取它们
os.environ["QUICK_THINK_LLM"] = "env-default-quick"
os.environ["DEEP_THINK_LLM"] = "env-default-deep"

from api.main import _build_runtime_config
from tradingagents.llm_clients.openai_client import OpenAIClient

class TestConfigFallback(unittest.TestCase):
    def test_priority_and_empty_filter(self):
        """验证: 用户配置(非空) > 环境变量，且空配置不覆盖环境变量"""
        # 强制 Mock DEFAULT_CONFIG 保证测试环境纯净
        with patch('api.main.DEFAULT_CONFIG', {"quick_think_llm": "env-default-quick", "deep_think_llm": "env-default-deep"}):
            # 场景: 数据库里 quick 被填成了空字符串，deep 填了新值
            overrides = {
                "quick_think_llm": "",
                "deep_think_llm": "user-custom-deep"
            }
            config = _build_runtime_config(overrides)
            
            # 结果: quick 应该保留环境变量的默认值，而不是变成空
            self.assertEqual(config["quick_think_llm"], "env-default-quick", "空字符串不应覆盖环境变量默认值")
            self.assertEqual(config["deep_think_llm"], "user-custom-deep", "有效的用户配置应生效")

    def test_intelligent_cross_borrowing(self):
        """验证: 如果环境变量也没设(None)，则进行互相借用"""
        # 我们需要临时清除 config 里的默认值来模拟这种极端情况
        with patch('api.main.DEFAULT_CONFIG', {"quick_think_llm": None, "deep_think_llm": None}):
            overrides = {
                "quick_think_llm": "only-one-model",
                "deep_think_llm": ""
            }
            config = _build_runtime_config(overrides)
            self.assertEqual(config["deep_think_llm"], "only-one-model", "Deep 应该借用唯一的有效配置")

    def test_no_hardcoded_fallback_in_client(self):
        """验证: OpenAIClient 不再有硬编码的 gpt-4o-mini 降级"""
        client = OpenAIClient(model="actual-model", provider="openai")
        self.assertEqual(client.model, "actual-model")
        
        # 如果真的传入空，它就应该是空（或者触发基类的初始化，但不应该自造 gpt-4o-mini）
        client_empty = OpenAIClient(model="", provider="openai")
        self.assertEqual(client_empty.model, "", "构造函数不应自造模型名")

if __name__ == "__main__":
    unittest.main()
