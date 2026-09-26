import json
import time
from unittest.mock import patch

from scheduler import intraday_tools


def test_web_search_returns_parsed_results():
    fake_results = [
        {"title": "标题A", "href": "https://a.example", "body": "摘要A"},
        {"title": "标题B", "href": "https://b.example", "body": "摘要B"},
    ]
    with patch.object(intraday_tools, "_ddgs_search", return_value=fake_results):
        out = json.loads(intraday_tools.web_search_fn("测试查询"))
    assert out["query"] == "测试查询"
    assert out["count"] == 2
    assert out["results"][0]["title"] == "标题A"


def test_ddgs_search_passes_explicit_timeout():
    # Regression: DDGS() used to be constructed with no timeout, relying
    # entirely on the outer ThreadPoolExecutor timeout (which can't stop an
    # already-wedged thread). DDGS's own timeout is enforced by its
    # underlying HTTP client and should be the primary defense.
    with patch.object(intraday_tools, "DDGS") as mock_ddgs_cls:
        intraday_tools._ddgs_search("测试查询", 10)
    mock_ddgs_cls.assert_called_once_with(timeout=intraday_tools._DDGS_REQUEST_TIMEOUT_SECONDS)


def test_web_search_times_out_instead_of_hanging():
    def _wedged(query, max_results):
        time.sleep(2)  # simulate DDGS hanging on DNS/TLS failure (bounded so the test itself stays fast)
        return []

    with patch.object(intraday_tools, "_ddgs_search", side_effect=_wedged):
        with patch.object(intraday_tools, "_SEARCH_TIMEOUT_SECONDS", 0.2):
            start = time.monotonic()
            out = json.loads(intraday_tools.web_search_fn("卡死查询"))
            elapsed = time.monotonic() - start
    assert out["error"] == "search_timeout"
    assert out["results"] == []
    assert elapsed < 5  # bounded by the short timeout, not the 60s sleep


def test_web_search_handles_exception_gracefully():
    with patch.object(intraday_tools, "_ddgs_search", side_effect=RuntimeError("boom")):
        out = json.loads(intraday_tools.web_search_fn("异常查询"))
    assert out["count"] == 0
    assert "error" in out


def test_get_market_wire_fn_delegates_to_provider():
    with patch.object(intraday_tools._provider, "get_sina_global_news", return_value="news text") as m:
        result = intraday_tools.get_market_wire_fn(limit=50)
    assert result == "news text"
    m.assert_called_once_with(page="1", page_size="50", tag_id="1,4,7")


def test_get_concept_fund_flow_fn_delegates_to_provider():
    with patch.object(intraday_tools._provider, "get_concept_fund_flow", return_value="board text") as m:
        result = intraday_tools.get_concept_fund_flow_fn()
    assert result == "board text"
    m.assert_called_once()


def test_get_lhb_market_snapshot_fn_delegates_to_provider():
    with patch.object(intraday_tools._provider, "get_lhb_market_snapshot", return_value="lhb text") as m:
        result = intraday_tools.get_lhb_market_snapshot_fn("2026-07-09", limit=15)
    assert result == "lhb text"
    m.assert_called_once_with("2026-07-09", limit=15)


def test_all_tools_are_registered():
    names = {t.name for t in intraday_tools.INTRADAY_CAUSE_TOOLS}
    assert names == {"get_market_wire", "get_concept_fund_flow", "get_lhb_market_snapshot", "web_search"}
