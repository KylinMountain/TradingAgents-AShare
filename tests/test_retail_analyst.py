import pytest
from tradingagents.agents.analysts.retail_investor_analyst import create_retail_investor_analyst
from tradingagents.agents.managers.game_theory_manager import create_game_theory_manager

def test_retail_investor_and_game_theory_logic():
    # 1. 模拟 LLM
    class MockLLM:
        def __init__(self, content):
            self.content = content
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            class MockResponse:
                def __init__(self, c):
                    self.content = c
                    self.tool_calls = []
            return MockResponse(self.content)

    # 2. 测试散户分析师输出
    retail_content = """
【散户情绪】大家都在热议 600519，雪球热度第一！
但是今天好多炸板的，大家都怕了，都在喊‘要崩了’。
<!-- VERDICT: {"direction": "看空", "reason": "热度极高但炸板导致恐慌"} -->
"""
    retail_node = create_retail_investor_analyst(MockLLM(retail_content), [])
    state = {
        "company_of_interest": "600519",
        "trade_date": "2024-01-15",
        "horizon": "short"
    }
    retail_result = retail_node(state)
    assert "retail_report" in retail_result
    print("Retail Investor Analyst successfully generated sentiment report.")

    # 3. 测试博弈裁判集成
    game_theory_content = """
主力正在‘悄悄建仓’（来自主力报告），但散户处于‘极度恐慌’状态（来自散户报告）。
这是一个典型的反向做多机会。
<!-- GAME_THEORY: {"board": "洗盘阶段", "players": ["主力", "散户"], "player_states": {"主力": "吸筹", "散户": "恐慌"}, "likely_actions": {"主力": ["继续买入"], "散户": ["低位割肉"]}, "dominant_strategy": "反向做多", "fragile_equilibrium": "价格突破阻力位", "counter_consensus_signal": "极强", "confidence": 0.9} -->
"""
    gt_node = create_game_theory_manager(MockLLM(game_theory_content))
    state_for_gt = {
        "smart_money_report": "主力净流入，换手率低。",
        "retail_report": retail_result["retail_report"],
        "sentiment_report": "市场情绪中性。"
    }
    gt_result = gt_node(state_for_gt)
    
    assert "game_theory_report" in gt_result
    assert "game_theory_signals" in gt_result
    assert gt_result["game_theory_signals"]["counter_consensus_signal"] == "极强"
    print("Game Theory Manager successfully identified Contrarian Signal from Retail Report.")

if __name__ == "__main__":
    test_retail_investor_and_game_theory_logic()
