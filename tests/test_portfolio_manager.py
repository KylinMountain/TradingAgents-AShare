import pytest
from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager

def test_portfolio_manager_logic():
    # 1. 模拟 LLM
    class MockLLM:
        def invoke(self, messages):
            class MockResponse:
                def __init__(self):
                    self.content = """
### 组合调整建议
基于当前 500,000 元可用资金和风控通过的建议，建议买入 100 股。
该行业目前占比 15%，处于安全范围。

<!-- ALLOCATION: {"target_weight_pct": 10.0, "order_type": "BUY", "order_size_shares": 100, "estimated_cost": 20000.0, "sector_exposure_pct": 15.0, "risk_budget_consumed": 0.01} -->
最终交易建议：买入
"""
            return MockResponse()

    # 2. 构造状态
    state = {
        "company_of_interest": "600519",
        "trader_investment_plan": "建议买入 100 股，价格 2000",
        "final_trade_decision": "pass",
        "user_context": {
            "cash_available": 500000.0,
            "risk_profile": "平衡"
        },
        "market_report": "板块走势强劲",
        "macro_report": "白酒板块资金净流入"
    }

    # 3. 执行 PM 节点
    pm_node_func = create_portfolio_manager(MockLLM())
    result = pm_node_func(state)

    # 4. 验证结果
    assert "portfolio_report" in result
    assert "allocation_details" in result
    assert result["allocation_details"]["target_weight_pct"] == 10.0
    assert result["allocation_details"]["order_size_shares"] == 100
    
    print("Portfolio Manager successfully generated allocation details.")

if __name__ == "__main__":
    test_portfolio_manager_logic()
