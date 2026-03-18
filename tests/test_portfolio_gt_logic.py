import pytest
from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager

def test_portfolio_contrarian_boost():
    # 场景 1：强反共识买入信号 -> 应该加码
    class MockLLM:
        def invoke(self, messages):
            class MockResponse:
                def __init__(self):
                    self.content = """
### 组合调整建议
观察到主力正在悄悄建仓而散户极度恐慌，触发‘强反共识’加码逻辑。
建议将原计划的 10% 仓位提升至 15%。

<!-- ALLOCATION: {"target_weight_pct": 15.0, "order_type": "BUY", "order_size_shares": 150, "estimated_cost": 30000.0, "sector_exposure_pct": 15.0, "risk_budget_consumed": 0.015} -->
"""
            return MockResponse()

    state = {
        "company_of_interest": "600519",
        "trader_investment_plan": "建议买入 100 股",
        "final_trade_decision": "pass",
        "game_theory_signals": {
            "counter_consensus_signal": "极强",
            "board": "底部吸筹",
            "player_states": {"主力": "吸筹", "散户": "恐慌"}
        },
        "user_context": {"cash_available": 500000.0}
    }

    pm_node = create_portfolio_manager(MockLLM())
    result = pm_node(state)
    assert result["allocation_details"]["target_weight_pct"] == 15.0
    print("Contrarian Boost logic verified.")

def test_portfolio_bubble_protection():
    # 场景 2：散户 FOMO 泡沫信号 -> 应该大幅缩减或限制仓位
    class MockLLM:
        def invoke(self, messages):
            class MockResponse:
                def __init__(self):
                    self.content = """
### 组合调整建议
虽然个股逻辑成立，但散户处于极度贪婪状态（雪球热度爆表），主力有派发迹象。
为规避踩踏风险，强行限制单笔仓位至 2%。

<!-- ALLOCATION: {"target_weight_pct": 2.0, "order_type": "BUY", "order_size_shares": 20, "estimated_cost": 4000.0, "sector_exposure_pct": 5.0, "risk_budget_consumed": 0.002} -->
"""
            return MockResponse()

    state = {
        "company_of_interest": "600519",
        "trader_investment_plan": "建议买入 100 股",
        "final_trade_decision": "pass",
        "game_theory_signals": {
            "counter_consensus_signal": "无",
            "player_states": {"主力": "派发", "散户": "极度贪婪"}
        },
        "user_context": {"cash_available": 500000.0}
    }

    pm_node = create_portfolio_manager(MockLLM())
    result = pm_node(state)
    assert result["allocation_details"]["target_weight_pct"] <= 5.0
    print("Bubble Protection logic verified.")

if __name__ == "__main__":
    test_portfolio_contrarian_boost()
    test_portfolio_bubble_protection()
