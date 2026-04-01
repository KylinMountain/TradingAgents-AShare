"""Tests for TradingAgentsGraph dual-horizon propagation (Task 10)."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradingagents.graph.propagation import Propagator
from tradingagents.graph.data_collector import DataCollector
from tradingagents.graph.setup import GraphSetup


# ---------------------------------------------------------------------------
# Propagator tests
# ---------------------------------------------------------------------------

class TestPropagatorInitialState:
    def test_default_horizon_and_traces(self):
        p = Propagator()
        state = p.create_initial_state("600519", "2024-01-15")
        assert state["horizon"] == "short"
        assert state["analyst_traces"] == []
        assert "user_intent" not in state

    def test_custom_horizon(self):
        p = Propagator()
        state = p.create_initial_state("600519", "2024-01-15", horizon="medium")
        assert state["horizon"] == "medium"

    def test_user_intent_injected(self):
        p = Propagator()
        intent = {"ticker": "600519", "horizons": ["short", "medium"], "focus_areas": ["量价"], "specific_questions": []}
        state = p.create_initial_state("600519", "2024-01-15", user_intent=intent)
        assert state["user_intent"] == intent

    def test_user_intent_not_present_when_none(self):
        p = Propagator()
        state = p.create_initial_state("600519", "2024-01-15", user_intent=None)
        assert "user_intent" not in state

    def test_base_fields_present(self):
        p = Propagator()
        state = p.create_initial_state("AAPL", "2024-06-01")
        assert state["company_of_interest"] == "AAPL"
        assert state["trade_date"] == "2024-06-01"
        assert "investment_debate_state" in state
        assert "risk_debate_state" in state


# ---------------------------------------------------------------------------
# TradingAgentsGraph._build_horizon_result tests
# ---------------------------------------------------------------------------

def _make_mock_graph_class():
    """Return a lightweight TradingAgentsGraph without real LLM/tool setup."""
    with patch("tradingagents.graph.trading_graph.create_llm_client"), \
         patch("tradingagents.graph.trading_graph.FinancialSituationMemory"), \
         patch("tradingagents.graph.trading_graph.GraphSetup"), \
         patch("tradingagents.graph.trading_graph.ConditionalLogic"), \
         patch("tradingagents.graph.trading_graph.Propagator"), \
         patch("tradingagents.graph.trading_graph.Reflector"), \
         patch("tradingagents.graph.trading_graph.SignalProcessor"), \
         patch("tradingagents.graph.trading_graph.set_config"):
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        ta = TradingAgentsGraph.__new__(TradingAgentsGraph)
        ta.debug = False
        ta.config = {}
        ta.callbacks = []
        ta.ticker = None
        ta.log_states_dict = {}
        ta.quick_thinking_llm = MagicMock()
        ta.data_collector = DataCollector()
        ta.propagator = Propagator()
        ta.graph = MagicMock()
        ta.signal_processor = MagicMock()
        return ta


class TestBuildHorizonResult:
    def setup_method(self):
        self.ta = _make_mock_graph_class()

    def test_extracts_horizon_and_decision(self):
        state = {
            "horizon": "short",
            "company_of_interest": "600519",
            "trade_date": "2024-01-15",
            "final_trade_decision": "买入",
            "investment_plan": "计划A",
            "trader_investment_plan": "交易计划",
            "analyst_traces": [{"agent": "market_analyst", "verdict": "看多"}],
            "market_report": "市场报告",
            "sentiment_report": "",
            "news_report": "",
            "fundamentals_report": "",
            "macro_report": "",
            "smart_money_report": "",
            "volume_price_report": "",
        }
        result = self.ta._build_horizon_result("short", state)
        assert result["horizon"] == "short"
        assert result["final_trade_decision"] == "买入"
        assert len(result["analyst_traces"]) == 1

    def test_missing_fields_default_to_empty(self):
        result = self.ta._build_horizon_result("medium", {})
        assert result["horizon"] == "medium"
        assert result["final_trade_decision"] == ""
        assert result["analyst_traces"] == []


# ---------------------------------------------------------------------------
# propagate_async integration (mocked graph)
# ---------------------------------------------------------------------------

class TestPropagateAsync:
    def setup_method(self):
        self.ta = _make_mock_graph_class()

    def _fake_state(self, horizon: str) -> dict:
        return {
            "company_of_interest": "600519",
            "trade_date": "2024-01-15",
            "horizon": horizon,
            "final_trade_decision": f"{horizon}_decision",
            "investment_plan": "",
            "trader_investment_plan": "",
            "analyst_traces": [],
            "market_report": "",
            "sentiment_report": "",
            "news_report": "",
            "fundamentals_report": "",
            "macro_report": "",
            "smart_money_report": "",
            "volume_price_report": "",
        }

    def test_returns_short_term_result_and_reserved_medium_slot(self):
        self.ta.graph.ainvoke = AsyncMock(
            side_effect=lambda state, **kw: self._fake_state(state["horizon"])
        )
        self.ta.data_collector.collect = MagicMock(return_value={})
        self.ta.data_collector.evict = MagicMock()

        result = asyncio.run(self.ta.propagate_async("600519", "2024-01-15"))

        assert "short_term" in result
        assert "medium_term" in result
        assert result["short_term"]["horizon"] == "short"
        assert result["medium_term"] is None
        assert result["user_intent"]["ticker"] == "600519"

    def test_data_collected_and_evicted(self):
        self.ta.graph.ainvoke = AsyncMock(
            side_effect=lambda state, **kw: self._fake_state(state["horizon"])
        )
        collect_mock = MagicMock(return_value={})
        evict_mock = MagicMock()
        self.ta.data_collector.collect = collect_mock
        self.ta.data_collector.evict = evict_mock

        asyncio.run(self.ta.propagate_async("600519", "2024-01-15"))

        collect_mock.assert_called_once_with("600519", "2024-01-15")
        evict_mock.assert_called_once_with("600519", "2024-01-15")

    def test_query_parses_intent(self):
        self.ta.graph.ainvoke = AsyncMock(
            side_effect=lambda state, **kw: self._fake_state(state["horizon"])
        )
        self.ta.data_collector.collect = MagicMock(return_value={})
        self.ta.data_collector.evict = MagicMock()

        parsed_intent = {
            "raw_query": "分析600519短线机会",
            "ticker": "600519",
            "horizons": ["short"],
            "focus_areas": ["技术面"],
            "specific_questions": [],
        }
        with patch("tradingagents.graph.trading_graph.parse_intent", return_value=parsed_intent):
            result = asyncio.run(
                self.ta.propagate_async("600519", "2024-01-15", query="分析600519短线机会")
            )

        assert result["user_intent"]["focus_areas"] == ["技术面"]


class _FakeWorkflow:
    def __init__(self, *_args, **_kwargs):
        self.nodes = {}
        self.edges = []
        self.conditional_edges = []

    def add_node(self, name, node):
        self.nodes[name] = node

    def add_edge(self, source, target):
        self.edges.append((source, target))

    def add_conditional_edges(self, source, condition, mapping):
        self.conditional_edges.append((source, condition, mapping))

    def compile(self, checkpointer=None):
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "conditional_edges": self.conditional_edges,
            "checkpointer": checkpointer,
        }


def test_graph_setup_wires_market_analyst_without_name_errors():
    quick_llm = object()
    deep_llm = object()
    tool_nodes = {"market": object()}
    conditional_logic = SimpleNamespace(
        should_continue_market=lambda *_args, **_kwargs: "done",
        should_continue_debate=lambda *_args, **_kwargs: "Research Manager",
        should_continue_risk_analysis=lambda *_args, **_kwargs: "Risk Judge",
        should_revise_after_risk_judge=lambda *_args, **_kwargs: "END",
    )

    create_market = MagicMock(return_value="market_node")
    factories = {
        "create_aggressive_debator": MagicMock(return_value="aggressive_node"),
        "create_bear_researcher": MagicMock(return_value="bear_node"),
        "create_bull_researcher": MagicMock(return_value="bull_node"),
        "create_conservative_debator": MagicMock(return_value="conservative_node"),
        "create_fundamentals_analyst": MagicMock(return_value="fundamentals_node"),
        "create_macro_analyst": MagicMock(return_value="macro_node"),
        "create_market_analyst": create_market,
        "create_neutral_debator": MagicMock(return_value="neutral_node"),
        "create_news_analyst": MagicMock(return_value="news_node"),
        "create_research_manager": MagicMock(return_value="research_node"),
        "create_risk_manager": MagicMock(return_value="risk_node"),
        "create_smart_money_analyst": MagicMock(return_value="smart_money_node"),
        "create_social_media_analyst": MagicMock(return_value="social_node"),
        "create_trader": MagicMock(return_value="trader_node"),
    }

    with patch("tradingagents.graph.setup._load_agent_factories", return_value=factories), \
         patch("tradingagents.graph.setup.StateGraph", _FakeWorkflow):
        graph_setup = GraphSetup(
            quick_llm,
            deep_llm,
            tool_nodes,
            bull_memory=object(),
            bear_memory=object(),
            trader_memory=object(),
            invest_judge_memory=object(),
            risk_manager_memory=object(),
            conditional_logic=conditional_logic,
            data_collector=object(),
        )

        compiled = graph_setup.setup_graph(["market"], checkpointer="cp")

    create_market.assert_called_once_with(quick_llm, graph_setup.data_collector)
    assert "Market Analyst" in compiled["nodes"]
    assert "Market Analyst Done" in compiled["nodes"]
    assert ("tools_market", "Market Analyst") in compiled["edges"]
    assert compiled["checkpointer"] == "cp"
