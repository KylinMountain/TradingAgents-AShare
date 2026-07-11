"""Tool set for the intraday cause-attribution Agent (openai-agents SDK).

Deliberately narrow (4 tools) and thin wrappers around existing
CnAkshareProvider methods, plus a DuckDuckGo web_search fallback for
international/off-exchange catalysts. See
docs/superpowers/specs/2026-07-10-intraday-analysis-design.md for the
search-order rationale.

Note: get_news()/get_lhb_detail() on CnAkshareProvider require an actual
6-digit ticker code, but board-level anomaly context only carries the
leading stock's *name* (e.g. "益诺思") — there's no reliable name->code
resolution available here, so per-ticker news isn't wired in as a tool.
get_lhb_market_snapshot (whole day's list, no ticker required) and
web_search (free-text) cover that gap instead.

Each ``@function_tool``-decorated wrapper is a thin shell around a plain
``*_fn`` function so the logic can be unit tested without going through
the openai-agents SDK's tool-calling machinery.
"""

from __future__ import annotations

import concurrent.futures as _cf
import json
import logging

from agents import function_tool
from ddgs import DDGS

from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider

logger = logging.getLogger(__name__)

_provider = CnAkshareProvider()

# DDGS's own request-level timeout (backed by the `primp` HTTP client, which
# properly bounds DNS+connect+read) -- this is the primary defense and should
# make the call return well within it in the vast majority of cases.
_DDGS_REQUEST_TIMEOUT_SECONDS = 8

# Backstop only: in the rare case DDGS still wedges past its own timeout,
# bound how long we wait before giving up. The worker thread can't be killed
# (Python has no thread-cancel API), so it may linger until its socket
# eventually errors out; a small *shared, reused* pool (rather than a fresh
# one per call) caps how many such threads can pile up over a trading day
# instead of growing unbounded.
_SEARCH_TIMEOUT_SECONDS = 12
_search_executor = _cf.ThreadPoolExecutor(max_workers=4, thread_name_prefix="intraday-websearch")


def get_market_wire_fn(limit: int = 30) -> str:
    return _provider.get_sina_global_news(page="1", page_size=str(limit), tag_id="1,4,7")


def get_concept_fund_flow_fn() -> str:
    return _provider.get_concept_fund_flow()


def get_lhb_market_snapshot_fn(date: str, limit: int = 30) -> str:
    return _provider.get_lhb_market_snapshot(date, limit=limit)


def _ddgs_search(query: str, max_results: int):
    return DDGS(timeout=_DDGS_REQUEST_TIMEOUT_SECONDS).text(query, max_results=max_results)


def web_search_fn(query: str, max_results: int = 10) -> str:
    try:
        fut = _search_executor.submit(_ddgs_search, query, max_results)
        try:
            results = fut.result(timeout=_SEARCH_TIMEOUT_SECONDS)
        except _cf.TimeoutError:
            # DDGS's own timeout should have fired by now; this only trips if
            # it's wedged below the HTTP-client layer (e.g. OS-level DNS
            # hang). The submitted job stays queued on the shared executor
            # and is not cancelled (Python has no thread-cancel API) -- it
            # will eventually finish and free its slot on its own.
            logger.warning("web_search timed out after %ds: %s", _SEARCH_TIMEOUT_SECONDS, query[:80])
            return json.dumps({"query": query, "results": [], "count": 0, "error": "search_timeout"}, ensure_ascii=False)
        except Exception as exc:
            logger.warning("web_search failed: %s", exc)
            return json.dumps({"query": query, "results": [], "count": 0, "error": str(exc)}, ensure_ascii=False)
    except Exception as exc:
        logger.warning("web_search failed to submit: %s", exc)
        return json.dumps({"query": query, "results": [], "count": 0, "error": str(exc)}, ensure_ascii=False)

    try:
        items = [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in results
        ]
        return json.dumps({"query": query, "results": items, "count": len(items)}, ensure_ascii=False)
    except Exception as exc:
        logger.error("web_search post-processing failed: %s", exc)
        return json.dumps({"query": query, "results": [], "count": 0, "error": str(exc)}, ensure_ascii=False)


@function_tool
def get_market_wire(limit: int = 30) -> str:
    """获取新浪财经全球快讯（宏观/财经类，扮演国内新闻电报的角色）。

    参数：
      - limit: 返回条数，默认 30。

    用于第一步排查市场级催化（政策、宏观事件、突发新闻）。
    """
    return get_market_wire_fn(limit=limit)


@function_tool
def get_concept_fund_flow() -> str:
    """获取概念板块资金流向排名（全市场，按净流入排序）。

    用于核实异动板块的资金方向，以及排查是否有关联板块同步异动。
    """
    return get_concept_fund_flow_fn()


@function_tool
def get_lhb_market_snapshot(date: str, limit: int = 30) -> str:
    """获取当日全市场龙虎榜明细（不限定个股），用于判断资金来源是机构还是游资。

    参数：
      - date: 交易日，格式 YYYY-MM-DD。
      - limit: 返回条数，默认 30。

    "上榜原因"/席位名称里含"机构专用"通常是机构资金；含具体营业部名称（尤其知名游资席位）通常是游资。
    """
    return get_lhb_market_snapshot_fn(date, limit=limit)


@function_tool
def web_search(query: str, max_results: int = 10) -> str:
    """通用网页搜索（DuckDuckGo 后端，支持中英文）。

    仅当国内快讯/龙虎榜/资金流都查不到催化、且怀疑是国际/海外事件（如美股财报、
    出口管制、地缘政治）时才使用。不要对 A 股板块名直接调用本工具。

    参数：
      - query: 搜索查询字符串。
      - max_results: 返回结果数，默认 10。

    返回 JSON 字符串：{"query","results":[{"title","url","snippet"}, ...]}。
    """
    return web_search_fn(query, max_results=max_results)


INTRADAY_CAUSE_TOOLS = [get_market_wire, get_concept_fund_flow, get_lhb_market_snapshot, web_search]
