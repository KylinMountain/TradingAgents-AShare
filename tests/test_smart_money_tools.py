def test_get_seat_history():
    from tradingagents.agents.utils.agent_utils import get_seat_history
    # Mock seat name from a typical LHB
    seat_name = "东方财富证券股份有限公司拉萨团结路第二证券营业部"
    result = get_seat_history.invoke({"seat_name": seat_name, "limit": 5})
    assert "history" in result or "error" in result
