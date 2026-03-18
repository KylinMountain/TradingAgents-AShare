def test_get_industry_peers():
    from tradingagents.agents.utils.agent_utils import get_industry_peers
    
    ticker = "002261.SZ"
    result = get_industry_peers.invoke({"symbol": ticker})
    
    assert isinstance(result, str)
    assert "peers" in result.lower() or "competitor" in result.lower()