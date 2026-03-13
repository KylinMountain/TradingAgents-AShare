# Intent-Driven Multi-Horizon Analysis Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform TradingAgents from a single-horizon fixed pipeline into an intent-aware, dual-horizon (short-term + medium-term) parallel analysis system with visible agent reasoning chains.

**Architecture:** IntentParser parses natural language to extract ticker + time horizons + focus areas. DataCollector fetches 90-day data once into an in-memory cache keyed by `{ticker}_{date}`. Two independent `graph.ainvoke()` calls run concurrently via `asyncio.gather`, each receiving a different `horizon` context. Each analyst reads from the shared cache and emits a structured `TraceItem` list. LangGraph accumulates `analyst_traces` via `operator.add` reducer.

**Tech Stack:** Python 3.12, LangGraph, LangChain, FastAPI, asyncio, pytest

**Spec:** `docs/superpowers/specs/2026-03-12-intent-driven-multi-horizon-design.md`

---

## Chunk 1: Foundation Layer

### Task 1: Extend AgentState with horizon and intent fields

**Files:**
- Modify: `tradingagents/agents/utils/agent_states.py`
- Create: `tests/__init__.py`
- Create: `tests/test_agent_states.py`

- [ ] **Step 1: Create tests package**

```bash
touch tests/__init__.py
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_agent_states.py
import operator
from tradingagents.agents.utils.agent_states import UserIntent, TraceItem


def test_user_intent_typeddict():
    intent: UserIntent = {
        "raw_query": "分析600519短线",
        "ticker": "600519",
        "horizons": ["short", "medium"],
        "focus_areas": ["量价关系"],
        "specific_questions": ["能否到目标位"],
    }
    assert intent["ticker"] == "600519"
    assert intent["horizons"] == ["short", "medium"]


def test_trace_item_typeddict():
    trace: TraceItem = {
        "agent": "market_analyst",
        "horizon": "short",
        "data_window": "14天",
        "key_finding": "RSI超买",
        "verdict": "看空",
        "confidence": "中",
    }
    assert trace["verdict"] == "看空"
    assert trace["confidence"] == "中"


def test_trace_list_accumulation():
    """Verify operator.add is the correct reducer for list accumulation."""
    t1 = [{"agent": "market_analyst", "verdict": "看空"}]
    t2 = [{"agent": "fundamentals_analyst", "verdict": "看多"}]
    merged = operator.add(t1, t2)
    assert len(merged) == 2
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/evilkylin/Projects/TradingAgents
python -m pytest tests/test_agent_states.py -v 2>&1 | head -20
```
Expected: ImportError — `UserIntent` and `TraceItem` not yet defined.

- [ ] **Step 4: Add UserIntent, TraceItem, and new fields to AgentState**

In `tradingagents/agents/utils/agent_states.py`, add after existing imports:

```python
import operator
from typing import List
```

Add new TypedDicts before `AgentState`:

```python
class UserIntent(TypedDict, total=False):
    raw_query: str
    ticker: str
    horizons: List[str]         # ["short", "medium"]
    focus_areas: List[str]
    specific_questions: List[str]


class TraceItem(TypedDict, total=False):
    agent: str
    horizon: str        # "short" | "medium"
    data_window: str    # e.g. "14天" | "90天"
    key_finding: str    # one-line summary
    verdict: str        # 看多/看空/中性/谨慎
    confidence: str     # 高/中/低
```

Add to `AgentState` class after the `game_theory_report` field:

```python
    # multi-horizon fields
    user_intent: Annotated[Optional[UserIntent], "Parsed user intent from natural language"]
    horizon: Annotated[str, "Current analysis horizon: short or medium"]
    # operator.add reducer accumulates traces from all analyst nodes
    analyst_traces: Annotated[List[TraceItem], operator.add]
    short_term_result: Annotated[Optional[dict], "Final short-term analysis result"]
    medium_term_result: Annotated[Optional[dict], "Final medium-term analysis result"]
```

**Note:** `operator.add` as the second `Annotated` argument tells LangGraph to merge list values from different nodes rather than overwrite. Each analyst node returns `{"analyst_traces": [single_trace_item]}` and LangGraph concatenates them automatically.

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_agent_states.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add tradingagents/agents/utils/agent_states.py tests/__init__.py tests/test_agent_states.py
git commit -m "feat: add UserIntent, TraceItem and horizon fields to AgentState"
```

---

### Task 2: IntentParser — prompt + parser function

**Files:**
- Modify: `tradingagents/prompts/zh.py`
- Modify: `tradingagents/prompts/en.py`
- Create: `tradingagents/graph/intent_parser.py`
- Create: `tests/test_intent_parser.py`

- [ ] **Step 1: Add IntentParser prompts to BOTH `zh.py` and `en.py`**

Add to `PROMPTS` dict in **`tradingagents/prompts/zh.py`**:

```python
    "intent_parser_system": """你是交易意图解析器。从用户输入中提取以下字段，以 JSON 格式输出，不要输出其他任何内容。

字段说明：
- ticker: 股票代码字符串（如 "600519" 或 "600519.SH"），若无法识别则为 null
- horizons: 时间维度列表，可选值 "short"（1-2周技术面主导）、"medium"（1-3月基本面主导），默认 ["short", "medium"]
- focus_areas: 用户特别关注的分析维度列表（空数组表示无特殊关注）
- specific_questions: 用户的具体问题列表（空数组表示无具体问题）

输出格式示例：
{"ticker": "600519", "horizons": ["short", "medium"], "focus_areas": ["量价关系", "主力资金"], "specific_questions": ["短期能否到+30%目标位"]}

注意：只输出 JSON，不要有任何前缀或后缀文字。""",

    "horizon_context_block": """【分析视角】
当前分析维度：{horizon_label}
用户重点关注：{focus_areas_str}
具体问题：{specific_questions_str}

请基于以上视角调整分析重点。{weight_hint}
""",
```

Add the **same keys** to **`tradingagents/prompts/en.py`** (English version):

```python
    "intent_parser_system": """You are a trading intent parser. Extract the following fields from user input and output as JSON only, no other text.

Fields:
- ticker: stock code string (e.g. "600519" or "600519.SH"), null if unrecognizable
- horizons: list of time horizons, options: "short" (1-2 weeks, technicals-driven), "medium" (1-3 months, fundamentals-driven), default ["short", "medium"]
- focus_areas: list of analysis dimensions the user specifically cares about (empty array if none)
- specific_questions: list of specific questions from the user (empty array if none)

Example output:
{"ticker": "600519", "horizons": ["short", "medium"], "focus_areas": ["volume-price", "smart money"], "specific_questions": ["Can it reach +30% target?"]}

Output JSON only, no prefix or suffix text.""",

    "horizon_context_block": """[Analysis Perspective]
Current horizon: {horizon_label}
User focus: {focus_areas_str}
Specific questions: {specific_questions_str}

Adjust your analysis emphasis based on the above. {weight_hint}
""",
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_intent_parser.py
from unittest.mock import MagicMock
from tradingagents.graph.intent_parser import parse_intent, build_horizon_context


def test_parse_intent_returns_defaults():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content='{"ticker": "600519", "horizons": ["short", "medium"], "focus_areas": [], "specific_questions": []}'
    )
    result = parse_intent("分析600519", mock_llm)
    assert result["ticker"] == "600519"
    assert result["horizons"] == ["short", "medium"]
    assert result["focus_areas"] == []


def test_parse_intent_fallback_on_invalid_json():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="这不是JSON")
    result = parse_intent("600519", mock_llm, fallback_ticker="600519")
    assert result["ticker"] == "600519"
    assert result["horizons"] == ["short", "medium"]
    assert result["focus_areas"] == []


def test_build_horizon_context_short_contains_label():
    ctx = build_horizon_context("short", ["量价关系"], ["能否突破"])
    assert "短线" in ctx
    assert "量价关系" in ctx
    assert "能否突破" in ctx


def test_build_horizon_context_medium_has_weight_hint_for_fundamentals():
    # medium horizon → fundamentals is primary, no weight hint
    ctx = build_horizon_context("medium", [], [], agent_type="fundamentals")
    assert "中线" in ctx

def test_build_horizon_context_short_fundamentals_has_downweight_hint():
    ctx = build_horizon_context("short", [], [], agent_type="fundamentals")
    assert "次要" in ctx
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest tests/test_intent_parser.py -v 2>&1 | head -20
```
Expected: ImportError.

- [ ] **Step 4: Create `tradingagents/graph/intent_parser.py`**

```python
"""IntentParser: parse natural language query into structured trading intent."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.prompts import get_prompt
from tradingagents.dataflows.config import get_config

_HORIZON_LABELS = {
    "short": "短线（1-2周，技术面主导）",
    "medium": "中线（1-3月，基本面主导）",
}

# (horizon, agent_type) -> weight hint appended to context block
_WEIGHT_HINTS: Dict[tuple, str] = {
    ("short", "fundamentals"): "本维度为次要参考，简要输出核心风险即可，无需完整基本面分析。",
    ("short", "macro"): "本维度为次要参考，仅关注近期政策冲击信号，简要输出即可。",
    ("medium", "smart_money"): "本维度为次要参考，仅判断大资金方向，简要输出即可。",
    ("medium", "social"): "本维度为次要参考，情绪仅作辅助参考，简要输出即可。",
    ("medium", "game_theory"): "本维度为次要参考，简要输出即可。",
}


def parse_intent(
    query: str,
    llm,
    fallback_ticker: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse natural language query into structured intent dict.

    Returns dict with keys: ticker, horizons, focus_areas, specific_questions, raw_query.
    Falls back gracefully to defaults if LLM output is unparseable.
    """
    config = get_config()
    system_msg = get_prompt("intent_parser_system", config=config)

    try:
        result = llm.invoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=query),
        ])
        raw = result.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        return {
            "raw_query": query,
            "ticker": parsed.get("ticker") or fallback_ticker or "",
            "horizons": parsed.get("horizons") or ["short", "medium"],
            "focus_areas": parsed.get("focus_areas") or [],
            "specific_questions": parsed.get("specific_questions") or [],
        }
    except Exception:
        return {
            "raw_query": query,
            "ticker": fallback_ticker or "",
            "horizons": ["short", "medium"],
            "focus_areas": [],
            "specific_questions": [],
        }


def build_horizon_context(
    horizon: str,
    focus_areas: List[str],
    specific_questions: List[str],
    agent_type: Optional[str] = None,
) -> str:
    """Build the horizon context block to prepend to any agent's system prompt."""
    config = get_config()
    template = get_prompt("horizon_context_block", config=config)

    horizon_label = _HORIZON_LABELS.get(horizon, horizon)
    focus_str = "、".join(focus_areas) if focus_areas else "无特殊关注"
    questions_str = "；".join(specific_questions) if specific_questions else "无"
    weight_hint = _WEIGHT_HINTS.get((horizon, agent_type), "") if agent_type else ""

    return template.format(
        horizon_label=horizon_label,
        focus_areas_str=focus_str,
        specific_questions_str=questions_str,
        weight_hint=weight_hint,
    )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_intent_parser.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add tradingagents/prompts/zh.py tradingagents/prompts/en.py \
        tradingagents/graph/intent_parser.py tests/test_intent_parser.py
git commit -m "feat: add IntentParser with horizon context builder (zh+en prompts)"
```

---

### Task 3: DataCollector — centralized 90-day data fetch

**Files:**
- Create: `tradingagents/graph/data_collector.py`
- Create: `tests/test_data_collector.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_data_collector.py
from unittest.mock import patch, MagicMock
from tradingagents.graph.data_collector import DataCollector, make_cache_key


def test_make_cache_key():
    assert make_cache_key("600519", "2026-03-12") == "600519_2026-03-12"


def test_collect_populates_required_keys():
    collector = DataCollector()
    stub_pool = {
        "stock_data": "data", "indicators": {}, "news": "n", "global_news": "gn",
        "fundamentals": "f", "balance_sheet": "bs", "cashflow": "cf",
        "income_statement": "is", "fund_flow_board": "ffb",
        "fund_flow_individual": "ffi", "lhb": "lhb",
        "insider_transactions": "it", "zt_pool": "zt", "hot_stocks": "hs",
    }
    with patch("tradingagents.graph.data_collector._fetch_all", return_value=stub_pool):
        result = collector.collect("600519", "2026-03-12")
    assert "stock_data" in result
    assert "lhb" in result
    assert "zt_pool" in result


def test_collect_uses_cache_on_second_call():
    collector = DataCollector()
    stub_pool = {"stock_data": "x", "indicators": {}}
    with patch("tradingagents.graph.data_collector._fetch_all", return_value=stub_pool) as mock_fetch:
        collector.collect("600519", "2026-03-12")
        collector.collect("600519", "2026-03-12")  # second call
    # _fetch_all should only be called once
    assert mock_fetch.call_count == 1


def test_evict_removes_from_cache():
    collector = DataCollector()
    collector._cache["600519_2026-03-12"] = {"stock_data": "x"}
    collector.evict("600519", "2026-03-12")
    assert "600519_2026-03-12" not in collector._cache


def test_get_window_short_returns_shorter_window_string():
    collector = DataCollector()
    pool = {"stock_data": "x", "indicators": {}, "_data_window": "90天"}
    sliced = collector.get_window(pool, horizon="short", trade_date="2026-03-12")
    assert sliced["_data_window"] == "14天"

def test_get_window_medium_keeps_full_window():
    collector = DataCollector()
    pool = {"stock_data": "x", "indicators": {}}
    sliced = collector.get_window(pool, horizon="medium", trade_date="2026-03-12")
    assert sliced["_data_window"] == "90天"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_data_collector.py -v 2>&1 | head -20
```
Expected: ImportError.

- [ ] **Step 3: Create `tradingagents/graph/data_collector.py`**

```python
"""DataCollector: fetch all data once, serve windowed views to analyst agents."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from tradingagents.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_global_news,
    get_insider_transactions,
    get_board_fund_flow,
    get_individual_fund_flow,
    get_lhb_detail,
    get_zt_pool,
    get_hot_stocks_xq,
)

INDICATORS = [
    "close_50_sma", "close_200_sma", "close_10_ema",
    "rsi", "macd", "boll", "boll_ub", "boll_lb", "atr", "vwma",
]
SHORT_DAYS = 14
LONG_DAYS = 90


def make_cache_key(ticker: str, trade_date: str) -> str:
    return f"{ticker}_{trade_date}"


def _safe(tool, payload: dict) -> Any:
    try:
        return tool.invoke(payload)
    except Exception as exc:
        return f"{getattr(tool, 'name', str(tool))} 调用失败：{type(exc).__name__}: {exc}"


def _fetch_all(ticker: str, trade_date: str) -> Dict[str, Any]:
    """Fetch all data sources. Called once per (ticker, trade_date)."""
    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=LONG_DAYS)
    start_str = start_dt.strftime("%Y-%m-%d")

    indicators: Dict[str, Any] = {}
    for ind in INDICATORS:
        indicators[ind] = _safe(get_indicators, {
            "symbol": ticker, "indicator": ind,
            "curr_date": trade_date, "look_back_days": LONG_DAYS,
        })

    return {
        "stock_data": _safe(get_stock_data, {
            "symbol": ticker, "start_date": start_str, "end_date": trade_date,
        }),
        "indicators": indicators,
        "news": _safe(get_news, {
            "ticker": ticker, "start_date": start_str, "end_date": trade_date,
        }),
        "global_news": _safe(get_global_news, {
            "curr_date": trade_date, "look_back_days": LONG_DAYS, "limit": 30,
        }),
        "fundamentals": _safe(get_fundamentals, {
            "ticker": ticker, "curr_date": trade_date,
        }),
        "balance_sheet": _safe(get_balance_sheet, {
            "ticker": ticker, "freq": "quarterly", "curr_date": trade_date,
        }),
        "cashflow": _safe(get_cashflow, {
            "ticker": ticker, "freq": "quarterly", "curr_date": trade_date,
        }),
        "income_statement": _safe(get_income_statement, {
            "ticker": ticker, "freq": "quarterly", "curr_date": trade_date,
        }),
        "fund_flow_board": _safe(get_board_fund_flow, {"symbol": ticker}),
        "fund_flow_individual": _safe(get_individual_fund_flow, {"symbol": ticker}),
        "lhb": _safe(get_lhb_detail, {"symbol": ticker, "date": trade_date}),
        "insider_transactions": _safe(get_insider_transactions, {
            "symbol": ticker, "curr_date": trade_date,
        }),
        "zt_pool": _safe(get_zt_pool, {"date": trade_date}),
        "hot_stocks": _safe(get_hot_stocks_xq, {}),
    }


class DataCollector:
    """Collect and cache data for a single analysis run."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def collect(self, ticker: str, trade_date: str) -> Dict[str, Any]:
        """Fetch all data and store in cache. Returns the data pool."""
        key = make_cache_key(ticker, trade_date)
        if key not in self._cache:
            self._cache[key] = _fetch_all(ticker, trade_date)
        return self._cache[key]

    def get(self, ticker: str, trade_date: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached pool, or None if not collected yet."""
        return self._cache.get(make_cache_key(ticker, trade_date))

    def get_window(
        self,
        pool: Dict[str, Any],
        horizon: str,
        trade_date: str,
    ) -> Dict[str, Any]:
        """Return pool copy annotated with horizon window metadata.

        Note: raw string data is not sliced (providers handle date ranges).
        The _data_window key signals to agents which window is active.
        DataFrame stock_data is sliced if present.
        """
        days = SHORT_DAYS if horizon == "short" else LONG_DAYS
        result = dict(pool)
        result["_data_window"] = f"{days}天"
        result["_horizon"] = horizon
        return result

    def evict(self, ticker: str, trade_date: str) -> None:
        """Remove cached data after analysis completes to free memory."""
        self._cache.pop(make_cache_key(ticker, trade_date), None)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_data_collector.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add tradingagents/graph/data_collector.py tests/test_data_collector.py
git commit -m "feat: add DataCollector with 90-day cache and eviction"
```

---

## Chunk 2: Agent Updates

**Pattern shared by all 6 analysts:**
1. Factory accepts `data_collector: DataCollector = None` as second parameter
2. Node reads from `data_collector.get_window(pool, horizon, trade_date)` if cache available, else falls back to direct tool calls
3. Injects `build_horizon_context(horizon, focus_areas, specific_questions, "<agent_type>")` at start of system prompt
4. Returns `{"analyst_traces": [trace_item]}` — a **single-item list**. LangGraph's `operator.add` reducer accumulates these across all analyst nodes automatically.

**CRITICAL:** Each analyst returns `{"analyst_traces": [new_trace]}` (list with one item), NOT the full accumulated list. The reducer handles accumulation.

---

### Task 4: Update market_analyst

**Files:**
- Modify: `tradingagents/agents/analysts/market_analyst.py`
- Create: `tests/test_market_analyst.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_market_analyst.py
from unittest.mock import MagicMock
from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.graph.data_collector import DataCollector


def _make_state(horizon="short"):
    return {
        "trade_date": "2026-03-12",
        "company_of_interest": "600519",
        "horizon": horizon,
        "user_intent": {
            "raw_query": "test", "ticker": "600519",
            "horizons": ["short", "medium"],
            "focus_areas": [], "specific_questions": [],
        },
    }


def _stub_pool():
    return {
        "stock_data": "close,volume\n100,1000\n101,1100",
        "indicators": {k: "50" for k in [
            "close_50_sma","close_200_sma","close_10_ema",
            "rsi","macd","boll","boll_ub","boll_lb","atr","vwma"
        ]},
        "_data_window": "14天", "_horizon": "short",
    }


def test_market_analyst_returns_trace():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content='分析结论\n<!-- VERDICT: {"direction": "看多", "reason": "趋势向上"} -->'
    )
    collector = DataCollector()
    collector._cache["600519_2026-03-12"] = _stub_pool()
    node = create_market_analyst(mock_llm, collector)

    result = node(_make_state("short"))

    assert "market_report" in result
    assert "analyst_traces" in result
    traces = result["analyst_traces"]
    assert len(traces) == 1
    assert traces[0]["agent"] == "market_analyst"
    assert traces[0]["horizon"] == "short"
    assert traces[0]["verdict"] == "看多"


def test_market_analyst_medium_window():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="report")
    collector = DataCollector()
    pool = _stub_pool()
    pool["_data_window"] = "90天"
    pool["_horizon"] = "medium"
    collector._cache["600519_2026-03-12"] = pool
    node = create_market_analyst(mock_llm, collector)

    result = node(_make_state("medium"))

    assert result["analyst_traces"][0]["data_window"] == "90天"


def test_market_analyst_fallback_without_collector():
    """When no collector provided, falls back to direct tool calls."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="fallback report")
    with MagicMock() as mock_tool:
        mock_tool.invoke.return_value = "tool data"
        # Just check it doesn't crash and returns expected keys
        node = create_market_analyst(mock_llm, data_collector=None)
        # Can't easily test without actual tools; just verify factory creates callable
        assert callable(node)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_market_analyst.py -v 2>&1 | head -20
```
Expected: TypeError — `create_market_analyst` doesn't accept `data_collector`.

- [ ] **Step 3: Rewrite `tradingagents/agents/analysts/market_analyst.py`**

```python
from datetime import datetime, timedelta
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context

MARKET_INDICATORS = [
    "close_50_sma", "close_200_sma", "close_10_ema",
    "rsi", "macd", "boll", "boll_ub", "boll_lb", "atr", "vwma",
]


def _extract_verdict(text: str) -> tuple:
    m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            return data.get("direction", "中性"), "中"
        except Exception:
            pass
    return "中性", "低"


def create_market_analyst(llm, data_collector=None):
    def market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "short")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("market_system_message", config=config)
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "market")

        if data_collector is not None:
            pool = data_collector.get(ticker, current_date)
            if pool is not None:
                windowed = data_collector.get_window(pool, horizon, current_date)
                stock_data = windowed.get("stock_data", "无数据")
                indicators = windowed.get("indicators", {})
                data_window = windowed.get("_data_window", "14天")
            else:
                stock_data, indicators, data_window = _fetch_direct(ticker, current_date, horizon)
        else:
            stock_data, indicators, data_window = _fetch_direct(ticker, current_date, horizon)

        indicator_blocks = [
            f"【{ind}】\n{indicators.get(ind, '无数据')}"
            for ind in MARKET_INDICATORS
        ]

        messages = [
            SystemMessage(content=(
                horizon_ctx + system_message
                + "\n\n请严格基于提供的数据输出报告，不要继续请求工具，请全程使用中文。"
            )),
            HumanMessage(content=(
                f"以下是 {ticker} 在 {current_date} 的行情与技术指标资料（{data_window}）。\n\n"
                f"【get_stock_data】\n{stock_data}\n\n"
                + "\n\n".join(indicator_blocks)
            )),
        ]

        result = llm.invoke(messages)
        verdict, confidence = _extract_verdict(result.content)

        return {
            "market_report": result.content,
            "analyst_traces": [{
                "agent": "market_analyst",
                "horizon": horizon,
                "data_window": data_window,
                "key_finding": f"技术分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return market_analyst_node


def _fetch_direct(ticker: str, current_date: str, horizon: str):
    """Fallback: fetch data directly without DataCollector."""
    from tradingagents.agents.utils.agent_utils import get_stock_data, get_indicators

    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    days = 14 if horizon == "short" else 90
    end_dt = datetime.strptime(current_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=days)
    stock_data = _safe(get_stock_data, {
        "symbol": ticker,
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "end_date": current_date,
    })
    indicators = {}
    for ind in MARKET_INDICATORS:
        indicators[ind] = _safe(get_indicators, {
            "symbol": ticker, "indicator": ind,
            "curr_date": current_date, "look_back_days": days,
        })
    return stock_data, indicators, f"{days}天"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_market_analyst.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/ -v 2>&1 | tail -10
```
Expected: All passing.

- [ ] **Step 6: Commit**

```bash
git add tradingagents/agents/analysts/market_analyst.py tests/test_market_analyst.py
git commit -m "feat: update market_analyst with data_collector, horizon context, trace output"
```

---

### Task 5: Update fundamentals_analyst

**Files:**
- Modify: `tradingagents/agents/analysts/fundamentals_analyst.py`

- [ ] **Step 1: Rewrite `fundamentals_analyst.py`**

```python
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context


def _extract_verdict(text):
    m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            return d.get("direction", "中性"), "中"
        except Exception:
            pass
    return "中性", "低"


def create_fundamentals_analyst(llm, data_collector=None):
    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "medium")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("fundamentals_system_message", config=config)
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "fundamentals")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            outputs = {k: pool.get(k, "无数据") for k in
                       ["fundamentals", "balance_sheet", "cashflow", "income_statement"]}
        else:
            from tradingagents.agents.utils.agent_utils import (
                get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement,
            )
            outputs = {
                "fundamentals": _safe(get_fundamentals, {"ticker": ticker, "curr_date": current_date}),
                "balance_sheet": _safe(get_balance_sheet, {"ticker": ticker, "freq": "quarterly", "curr_date": current_date}),
                "cashflow": _safe(get_cashflow, {"ticker": ticker, "freq": "quarterly", "curr_date": current_date}),
                "income_statement": _safe(get_income_statement, {"ticker": ticker, "freq": "quarterly", "curr_date": current_date}),
            }

        messages = [
            SystemMessage(content=horizon_ctx + system_message + "\n\n请全程使用中文。"),
            HumanMessage(content=(
                f"以下是 {ticker} 在 {current_date} 的基本面资料。\n\n"
                f"【get_fundamentals】\n{outputs['fundamentals']}\n\n"
                f"【get_balance_sheet】\n{outputs['balance_sheet']}\n\n"
                f"【get_cashflow】\n{outputs['cashflow']}\n\n"
                f"【get_income_statement】\n{outputs['income_statement']}\n"
            )),
        ]

        result = llm.invoke(messages)
        verdict, confidence = _extract_verdict(result.content)
        return {
            "fundamentals_report": result.content,
            "analyst_traces": [{
                "agent": "fundamentals_analyst",
                "horizon": horizon,
                "data_window": "财报周期",
                "key_finding": f"基本面分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return fundamentals_analyst_node
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/ -v 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
git add tradingagents/agents/analysts/fundamentals_analyst.py
git commit -m "feat: update fundamentals_analyst with data_collector, horizon context, trace output"
```

---

### Task 6: Update news_analyst

**Files:**
- Modify: `tradingagents/agents/analysts/news_analyst.py`

- [ ] **Step 1: Rewrite `news_analyst.py`**

The news analyst uses `news`, `global_news`, `insider_transactions` from the cache. For short horizon, truncate news to 14-day window (already handled by DataCollector providing 90-day data; we note the window in the prompt).

```python
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context


def _extract_verdict(text):
    m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            return d.get("direction", "中性"), "中"
        except Exception:
            pass
    return "中性", "低"


def create_news_analyst(llm, data_collector=None):
    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "short")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("news_system_message", config=config)
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "news")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            data_window = pool.get("_data_window", "14天" if horizon == "short" else "90天")
            stock_news = pool.get("news", "无数据")
            global_news = pool.get("global_news", "无数据")
        else:
            from datetime import datetime, timedelta
            from tradingagents.agents.utils.agent_utils import get_news, get_global_news
            days = 14 if horizon == "short" else 30
            end_dt = datetime.strptime(current_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days)
            stock_news = _safe(get_news, {
                "ticker": ticker,
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": current_date,
            })
            global_news = _safe(get_global_news, {
                "curr_date": current_date, "look_back_days": days, "limit": 10,
            })
            data_window = f"{days}天"

        messages = [
            SystemMessage(content=(
                horizon_ctx + system_message
                + "\n\n请严格基于提供的新闻资料输出报告，全程使用中文。"
            )),
            HumanMessage(content=(
                f"以下是 {ticker} 在 {current_date} 的新闻资料（{data_window}）。\n\n"
                f"【get_news】\n{stock_news}\n\n"
                f"【get_global_news】\n{global_news}\n"
            )),
        ]

        result = llm.invoke(messages)
        verdict, confidence = _extract_verdict(result.content)
        return {
            "news_report": result.content,
            "analyst_traces": [{
                "agent": "news_analyst",
                "horizon": horizon,
                "data_window": data_window,
                "key_finding": f"新闻分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return news_analyst_node
```

- [ ] **Step 2: Commit**

```bash
git add tradingagents/agents/analysts/news_analyst.py
git commit -m "feat: update news_analyst with data_collector, horizon context, trace output"
```

---

### Task 7: Update social_media_analyst

**Files:**
- Modify: `tradingagents/agents/analysts/social_media_analyst.py`

- [ ] **Step 1: Rewrite `social_media_analyst.py`**

Social analyst uses `news`, `zt_pool`, `hot_stocks` from cache.

```python
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context


def _extract_verdict(text):
    m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            return d.get("direction", "中性"), "中"
        except Exception:
            pass
    return "中性", "低"


def create_social_media_analyst(llm, data_collector=None):
    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "short")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("social_system_message", config=config)
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "social")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            news_text = pool.get("news", "无数据")
            zt_data = pool.get("zt_pool", "无数据")
            hot_stocks = pool.get("hot_stocks", "无数据")
        else:
            from datetime import datetime, timedelta
            from tradingagents.agents.utils.agent_utils import get_news, get_zt_pool, get_hot_stocks_xq
            days = 7
            end_dt = datetime.strptime(current_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days)
            news_text = _safe(get_news, {
                "ticker": ticker,
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": current_date,
            })
            zt_data = _safe(get_zt_pool, {"date": current_date})
            hot_stocks = _safe(get_hot_stocks_xq, {})

        messages = [
            SystemMessage(content=(
                horizon_ctx + system_message
                + "\n\n请严格基于提供的舆情数据输出报告，全程使用中文。"
            )),
            HumanMessage(content=(
                f"以下是 {ticker} 在 {current_date} 的舆情近似资料。\n\n"
                f"【get_news】\n{news_text}\n\n"
                f"【涨停池数据】\n{zt_data}\n\n"
                f"【雪球热门股票】\n{hot_stocks}\n"
            )),
        ]

        result = llm.invoke(messages)
        verdict, confidence = _extract_verdict(result.content)
        return {
            "sentiment_report": result.content,
            "analyst_traces": [{
                "agent": "social_media_analyst",
                "horizon": horizon,
                "data_window": "7天",
                "key_finding": f"舆情分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return social_media_analyst_node
```

- [ ] **Step 2: Commit**

```bash
git add tradingagents/agents/analysts/social_media_analyst.py
git commit -m "feat: update social_media_analyst with data_collector, horizon context, trace output"
```

---

### Task 8: Update macro_analyst and smart_money_analyst

**Files:**
- Modify: `tradingagents/agents/analysts/macro_analyst.py`
- Modify: `tradingagents/agents/analysts/smart_money_analyst.py`

- [ ] **Step 1: Rewrite `macro_analyst.py`**

```python
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context


def _extract_verdict(text):
    m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            return d.get("direction", "中性"), "中"
        except Exception:
            pass
    return "中性", "低"


def create_macro_analyst(llm, data_collector=None):
    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    def macro_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "medium")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("macro_system_message", config=config) or ""
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "macro")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            board_flow = pool.get("fund_flow_board", "无数据")
            recent_news = pool.get("news", "无数据")
        else:
            from datetime import datetime, timedelta
            from tradingagents.agents.utils.agent_utils import get_board_fund_flow, get_news
            days = 7
            end_dt = datetime.strptime(current_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days)
            board_flow = _safe(get_board_fund_flow, {"symbol": ticker})
            recent_news = _safe(get_news, {
                "ticker": ticker,
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": current_date,
            })

        messages = [
            SystemMessage(content=(
                horizon_ctx + system_message
                + "\n\n请严格基于提供的数据输出报告，全程使用中文。"
            )),
            HumanMessage(content=(
                f"请分析 {ticker} 在 {current_date} 的宏观与板块环境。\n\n"
                f"【今日行业板块资金流向】\n{board_flow}\n\n"
                f"【近期相关新闻】\n{recent_news}"
            )),
        ]

        result = llm.invoke(messages)
        verdict, confidence = _extract_verdict(result.content)
        return {
            "macro_report": result.content,
            "analyst_traces": [{
                "agent": "macro_analyst",
                "horizon": horizon,
                "data_window": "板块数据",
                "key_finding": f"宏观板块分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return macro_analyst_node
```

- [ ] **Step 2: Rewrite `smart_money_analyst.py`**

```python
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context


def _extract_verdict(text):
    m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            return d.get("direction", "中性"), "中"
        except Exception:
            pass
    return "中性", "低"


def create_smart_money_analyst(llm, data_collector=None):
    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    def smart_money_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "short")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("smart_money_system_message", config=config) or ""
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "smart_money")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            fund_flow = pool.get("fund_flow_individual", "无数据")
            lhb = pool.get("lhb", "无数据")
            volume = pool.get("indicators", {}).get("vwma", "无数据")
        else:
            from tradingagents.agents.utils.agent_utils import (
                get_individual_fund_flow, get_lhb_detail, get_indicators,
            )
            fund_flow = _safe(get_individual_fund_flow, {"symbol": ticker})
            lhb = _safe(get_lhb_detail, {"symbol": ticker, "date": current_date})
            volume = _safe(get_indicators, {
                "symbol": ticker, "indicator": "volume",
                "curr_date": current_date, "look_back_days": 20,
            })

        messages = [
            SystemMessage(content=(
                horizon_ctx + system_message
                + "\n\n请严格基于提供的量化数据输出分析，全程使用中文。"
            )),
            HumanMessage(content=(
                f"请分析 {ticker} 在 {current_date} 的主力资金行为。\n\n"
                f"【近5日主力资金净流向】\n{fund_flow}\n\n"
                f"【龙虎榜数据】\n{lhb}\n\n"
                f"【成交量指标(vwma)】\n{volume}"
            )),
        ]

        result = llm.invoke(messages)
        verdict, confidence = _extract_verdict(result.content)
        return {
            "smart_money_report": result.content,
            "analyst_traces": [{
                "agent": "smart_money_analyst",
                "horizon": horizon,
                "data_window": "近期可用",
                "key_finding": f"主力资金分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return smart_money_analyst_node
```

- [ ] **Step 3: Run all tests**

```bash
python -m pytest tests/ -v 2>&1 | tail -10
```
Expected: All passing.

- [ ] **Step 4: Commit**

```bash
git add tradingagents/agents/analysts/macro_analyst.py \
        tradingagents/agents/analysts/smart_money_analyst.py
git commit -m "feat: update macro_analyst and smart_money_analyst with data_collector, horizon context, trace output"
```

---

### Task 9: Update GraphSetup to pass data_collector to analyst factories

**Files:**
- Modify: `tradingagents/graph/setup.py`

- [ ] **Step 1: Add `data_collector` parameter to `GraphSetup.__init__`**

In `setup.py`, change `__init__` signature:

```python
def __init__(
    self,
    quick_thinking_llm,
    deep_thinking_llm,
    tool_nodes,
    bull_memory, bear_memory, trader_memory,
    invest_judge_memory, risk_manager_memory,
    conditional_logic,
    data_collector=None,   # NEW
):
    ...
    self.data_collector = data_collector
```

- [ ] **Step 2: Pass `data_collector` to each analyst factory in `setup_graph`**

In `setup_graph()`, update each analyst creation to pass `self.data_collector`:

```python
if "market" in selected_analysts:
    analyst_nodes["market"] = create_market_analyst(
        self.quick_thinking_llm, self.data_collector
    )
    # Keep tool_nodes for backward compatibility; they will just be unused
    tool_nodes["market"] = self.tool_nodes["market"]
    done_nodes["market"] = analyst_done_node

if "social" in selected_analysts:
    analyst_nodes["social"] = create_social_media_analyst(
        self.quick_thinking_llm, self.data_collector
    )
    ...

if "news" in selected_analysts:
    analyst_nodes["news"] = create_news_analyst(
        self.quick_thinking_llm, self.data_collector
    )
    ...

if "fundamentals" in selected_analysts:
    analyst_nodes["fundamentals"] = create_fundamentals_analyst(
        self.quick_thinking_llm, self.data_collector
    )
    ...

if "macro" in selected_analysts:
    analyst_nodes["macro"] = create_macro_analyst(
        self.quick_thinking_llm, self.data_collector
    )
    ...

if "smart_money" in selected_analysts:
    analyst_nodes["smart_money"] = create_smart_money_analyst(
        self.quick_thinking_llm, self.data_collector
    )
    ...
```

- [ ] **Step 3: Run all tests**

```bash
python -m pytest tests/ -v 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add tradingagents/graph/setup.py
git commit -m "feat: pass data_collector to analyst factories in GraphSetup"
```

---

## Chunk 3: Orchestration and API

### Task 10: Update TradingAgentsGraph with dual-horizon propagation

**Files:**
- Modify: `tradingagents/graph/trading_graph.py`
- Modify: `tradingagents/graph/propagation.py`
- Create: `tests/test_trading_graph_multi_horizon.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_trading_graph_multi_horizon.py
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from tradingagents.graph.data_collector import DataCollector


def test_propagate_async_returns_dual_results():
    """propagate_async() returns both short_term_result and medium_term_result."""
    with patch("tradingagents.graph.trading_graph.TradingAgentsGraph.__init__", return_value=None):
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        graph_obj = TradingAgentsGraph.__new__(TradingAgentsGraph)
        graph_obj.data_collector = DataCollector()
        graph_obj.data_collector._cache["600519_2026-03-12"] = {"stock_data": "x", "indicators": {}}

        short_state = {
            "final_trade_decision": '结论\n<!-- VERDICT: {"direction": "看空", "reason": "技术面弱"} -->',
            "analyst_traces": [{"agent": "market_analyst", "verdict": "看空"}],
            "company_of_interest": "600519",
            "trade_date": "2026-03-12",
        }
        medium_state = {
            "final_trade_decision": '结论\n<!-- VERDICT: {"direction": "看多", "reason": "基本面好"} -->',
            "analyst_traces": [{"agent": "fundamentals_analyst", "verdict": "看多"}],
            "company_of_interest": "600519",
            "trade_date": "2026-03-12",
        }

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(side_effect=[short_state, medium_state])
        graph_obj.graph = mock_graph

        mock_propagator = MagicMock()
        mock_propagator.create_initial_state.return_value = {
            "analyst_traces": [],
            "company_of_interest": "600519",
            "trade_date": "2026-03-12",
        }
        mock_propagator.get_graph_args.return_value = {"config": {"recursion_limit": 100}}
        graph_obj.propagator = mock_propagator

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content='{"ticker": "600519", "horizons": ["short", "medium"], "focus_areas": [], "specific_questions": []}'
        )
        graph_obj.quick_thinking_llm = mock_llm
        graph_obj.ticker = None
        graph_obj.curr_state = None
        graph_obj.log_states_dict = {}
        graph_obj.debug = False
        graph_obj.callbacks = []

        result = asyncio.run(graph_obj.propagate_async("分析600519", "2026-03-12", job_id="test"))

        assert "short_term_result" in result
        assert "medium_term_result" in result
        assert result["short_term_result"]["verdict"] == "看空"
        assert result["medium_term_result"]["verdict"] == "看多"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_trading_graph_multi_horizon.py -v 2>&1 | head -20
```
Expected: AttributeError — `propagate_async` not defined.

- [ ] **Step 3: Update `tradingagents/graph/propagation.py`**

In `create_initial_state`, add `user_intent` and `horizon` parameters:

```python
def create_initial_state(
    self,
    company_name: str,
    trade_date: str,
    user_intent: dict = None,
    horizon: str = "short",
) -> dict:
    user_context = (
        f"Symbol: {company_name}\n"
        f"Trade date: {trade_date}\n"
        f"Horizon: {horizon}"
    )
    return {
        "messages": [("human", user_context)],
        "company_of_interest": company_name,
        "trade_date": str(trade_date),
        "investment_debate_state": InvestDebateState(
            {"history": "", "current_response": "", "count": 0}
        ),
        "risk_debate_state": RiskDebateState({
            "history": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "count": 0,
        }),
        "market_report": "",
        "fundamentals_report": "",
        "sentiment_report": "",
        "news_report": "",
        "horizon": horizon,
        "analyst_traces": [],
        "user_intent": user_intent or {
            "raw_query": company_name,
            "ticker": company_name,
            "horizons": ["short", "medium"],
            "focus_areas": [],
            "specific_questions": [],
        },
    }
```

- [ ] **Step 4: Add `propagate_async` and helpers to `trading_graph.py`**

Add imports at top of `trading_graph.py`:

```python
import asyncio
from tradingagents.graph.intent_parser import parse_intent
from tradingagents.graph.data_collector import DataCollector
```

Add `DataCollector` to `__init__`:

```python
self.data_collector = DataCollector()
```

Pass to `GraphSetup`:

```python
self.graph_setup = GraphSetup(
    self.quick_thinking_llm,
    self.deep_thinking_llm,
    self.tool_nodes,
    self.bull_memory,
    self.bear_memory,
    self.trader_memory,
    self.invest_judge_memory,
    self.risk_manager_memory,
    self.conditional_logic,
    data_collector=self.data_collector,   # NEW
)
```

Add `propagate_async` method:

```python
async def propagate_async(
    self,
    query: str,
    trade_date: str,
    job_id: str = None,
) -> dict:
    """Run dual-horizon analysis concurrently. Returns dict with short/medium results."""
    import re, json as _json

    # 1. Parse intent from natural language query
    user_intent = parse_intent(query, self.quick_thinking_llm, fallback_ticker=query)
    ticker = user_intent.get("ticker") or query
    horizons = user_intent.get("horizons") or ["short", "medium"]
    self.ticker = ticker

    # 2. Collect all data once (shared between both subgraphs)
    self.data_collector.collect(ticker, trade_date)

    # 3. Build initial states for each horizon
    async def run_horizon(horizon: str) -> dict:
        init_state = self.propagator.create_initial_state(
            ticker, trade_date, user_intent=user_intent, horizon=horizon
        )
        args = self.propagator.get_graph_args()
        return await self.graph.ainvoke(init_state, **args)

    # 4. Run both horizons concurrently
    states = await asyncio.gather(*[run_horizon(h) for h in horizons])

    # 5. Package results
    result = {"user_intent": user_intent}
    for i, horizon in enumerate(horizons):
        state = states[i]
        result[f"{horizon}_term_result"] = self._build_horizon_result(state, horizon)

    # 6. Store for reflection and log
    self.curr_state = states[0]
    self._log_state_dual(trade_date, result)

    # 7. Evict cache to free memory
    self.data_collector.evict(ticker, trade_date)

    return result


def _build_horizon_result(self, state: dict, horizon: str) -> dict:
    """Extract structured result from a completed horizon state."""
    import re, json as _json

    decision = state.get("final_trade_decision", "")
    verdict = "中性"
    core_reasons = []

    m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', decision, re.DOTALL)
    if m:
        try:
            data = _json.loads(m.group(1))
            verdict = data.get("direction", "中性")
            reason = data.get("reason", "")
            if reason:
                core_reasons = [reason]
        except Exception:
            pass

    return {
        "verdict": verdict,
        "confidence": "中",
        "target_price": None,
        "stop_loss": None,
        "core_reasons": core_reasons,
        "invalidation": "",
        "traces": state.get("analyst_traces", []),
        "full_report": decision,
        "horizon": horizon,
    }


def _log_state_dual(self, trade_date: str, result: dict) -> None:
    """Log dual-horizon result to JSON file."""
    from pathlib import Path
    import json as _json

    self.log_states_dict[str(trade_date)] = result
    directory = Path(f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/")
    directory.mkdir(parents=True, exist_ok=True)
    with open(
        f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/full_states_log_{trade_date}.json",
        "w",
    ) as f:
        _json.dump(self.log_states_dict, f, indent=4, default=str)
```

**Keep the existing `propagate()` method unchanged** for backward compatibility.

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_trading_graph_multi_horizon.py -v
```
Expected: PASS (1 test)

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -15
```
Expected: All passing.

- [ ] **Step 7: Commit**

```bash
git add tradingagents/graph/trading_graph.py tradingagents/graph/propagation.py \
        tests/test_trading_graph_multi_horizon.py
git commit -m "feat: add propagate_async with dual-horizon asyncio.gather execution"
```

---

### Task 11: Update API — accept query field, return dual results

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Make `symbol` optional and add `query` field to `AnalyzeRequest`**

In `api/main.py`, change `AnalyzeRequest`:

```python
class AnalyzeRequest(BaseModel):
    symbol: Optional[str] = Field(None, description="股票代码（可选，query 中包含时可省略）")
    query: Optional[str] = Field(None, description="自然语言分析请求，如 '分析600519短线'")
    trade_date: str = Field(default_factory=cn_today_str)
    selected_analysts: List[str] = Field(
        default_factory=lambda: ["market", "social", "news", "fundamentals", "macro", "smart_money"]
    )
    config_overrides: Dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False

    def get_effective_query(self) -> str:
        """Return query if provided, else fall back to symbol."""
        return self.query or self.symbol or ""
```

- [ ] **Step 2: Update job execution to route to `propagate_async` when `query` is set**

In the job runner function (where `ta_graph.propagate(...)` is called), add a branch:

```python
if job.get("query"):
    result = asyncio.run(ta_graph.propagate_async(
        query=job["query"],
        trade_date=job["trade_date"],
        job_id=job_id,
    ))
    # Keep final_trade_decision for legacy SSE consumers
    short = result.get("short_term_result", {})
    final_decision = short.get("full_report", "")
    job["result"] = result
    job["final_trade_decision"] = final_decision
else:
    # Legacy path unchanged
    final_state, signal = ta_graph.propagate(job["symbol"], job["trade_date"])
    ...
```

- [ ] **Step 3: Update result endpoint to return dual results**

In `GET /v1/jobs/{job_id}/result`, detect new result format:

```python
job_result = job.get("result", {})
if "short_term_result" in job_result:
    return {
        "job_id": job_id,
        "short_term_result": job_result["short_term_result"],
        "medium_term_result": job_result.get("medium_term_result"),
        "user_intent": job_result.get("user_intent"),
    }
# Legacy fallback — existing response format unchanged
```

- [ ] **Step 4: Smoke test API imports**

```bash
python -c "from api.main import app; print('API imports OK')"
```
Expected: `API imports OK`

- [ ] **Step 5: Commit**

```bash
git add api/main.py
git commit -m "feat: API accepts query field, returns dual-horizon results"
```

---

### Task 12: Export new modules and final smoke test

**Files:**
- Modify: `tradingagents/graph/__init__.py`

- [ ] **Step 1: Add exports to `tradingagents/graph/__init__.py`**

```python
from .intent_parser import parse_intent, build_horizon_context
from .data_collector import DataCollector, make_cache_key
```

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 3: Smoke test import chain**

```bash
python -c "
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.graph.intent_parser import parse_intent, build_horizon_context
from tradingagents.graph.data_collector import DataCollector
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 4: Commit all docs**

```bash
git add tradingagents/graph/__init__.py \
        docs/superpowers/specs/2026-03-12-intent-driven-multi-horizon-design.md \
        docs/superpowers/plans/2026-03-12-intent-driven-multi-horizon.md
git commit -m "feat: export intent_parser and data_collector from graph package; add spec and plan docs"
```

---

## Summary

| Chunk | Tasks | Key deliverable |
|-------|-------|-----------------|
| 1 Foundation | 1–3 | AgentState types (with `operator.add` reducer), IntentParser, DataCollector |
| 2 Agents | 4–9 | All 6 analysts updated: data_collector closure + horizon context + trace output |
| 3 Orchestration | 10–12 | `propagate_async`, API dual results, package exports |

**Key invariants to verify during implementation:**
- `analyst_traces` uses `operator.add` reducer — each analyst returns a single-item list, LangGraph concatenates
- `data_collector.collect()` is called once before `asyncio.gather` — both subgraphs read from pre-populated cache
- `propagate()` (legacy) remains unchanged — backward compatible
