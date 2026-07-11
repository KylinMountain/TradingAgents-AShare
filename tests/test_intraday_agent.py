import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents.models.interface import Model

from scheduler.intraday_agent import analyze_cause, _clean_output
from scheduler.intraday_rules import BoardAnomaly

_FAKE_MODEL = MagicMock(spec=Model)

_ANOMALY = BoardAnomaly(board_name="CRO概念", anomaly_case="A", change_pct=4.43, net_inflow=19.56)
_CONFIG = {"llm_provider": "openai", "quick_think_llm": "gpt-4o-mini", "api_key": "test-key"}


class _FakeRunResult:
    def __init__(self, final_output):
        self.final_output = final_output


def test_clean_output_strips_tool_call_tags():
    dirty = '<tool_call>ignore</tool_call>正文{"name": "foo", "arguments": {"a": 1}}\n结尾'
    cleaned = _clean_output(dirty)
    assert "tool_call" not in cleaned
    assert '"name"' not in cleaned
    assert "正文" in cleaned and "结尾" in cleaned


@pytest.mark.asyncio
async def test_analyze_cause_falls_back_when_model_build_fails():
    with patch("scheduler.intraday_agent.build_intraday_agent_model", side_effect=RuntimeError("no key")):
        result = await analyze_cause(_ANOMALY, "2026-07-09", _CONFIG)
    assert result.llm_failed is True
    assert "CRO概念" in result.cause_summary
    assert result.fund_source is None


@pytest.mark.asyncio
async def test_analyze_cause_falls_back_on_timeout():
    async def _hangs(*args, **kwargs):
        await asyncio.sleep(10)

    with patch("scheduler.intraday_agent.build_intraday_agent_model", return_value=_FAKE_MODEL), \
         patch("scheduler.intraday_agent._TIMEOUT_SECONDS", 0.05), \
         patch("scheduler.intraday_agent.Runner.run", side_effect=_hangs):
        result = await analyze_cause(_ANOMALY, "2026-07-09", _CONFIG)
    assert result.llm_failed is True


@pytest.mark.asyncio
async def test_analyze_cause_falls_back_on_garbage_output():
    with patch("scheduler.intraday_agent.build_intraday_agent_model", return_value=_FAKE_MODEL), \
         patch("scheduler.intraday_agent.Runner.run", new=AsyncMock(return_value=_FakeRunResult("too short"))):
        result = await analyze_cause(_ANOMALY, "2026-07-09", _CONFIG)
    assert result.llm_failed is True


@pytest.mark.asyncio
async def test_analyze_cause_parses_structured_fields_on_success():
    good_output = (
        "【异动】CRO概念 Case A\n"
        "• 催化: 创新药政策利好密集释放\n"
        "• 资金来源: 机构\n"
        "• 判断: 持续行情\n"
    )
    with patch("scheduler.intraday_agent.build_intraday_agent_model", return_value=_FAKE_MODEL), \
         patch("scheduler.intraday_agent.Runner.run", new=AsyncMock(return_value=_FakeRunResult(good_output))):
        result = await analyze_cause(_ANOMALY, "2026-07-09", _CONFIG)
    assert result.llm_failed is False
    assert result.fund_source == "机构"
    assert result.judgement == "持续行情"
    assert "CRO概念" in result.cause_summary


@pytest.mark.asyncio
async def test_analyze_cause_truncates_overlong_fund_source_and_judgement():
    # Regression: api/database.py's fund_source/judgement columns have a
    # fixed max length; a verbose LLM response must never be able to trip a
    # DB length error regardless of the current column width.
    overlong = "机构" * 100
    good_output = (
        f"【异动】CRO概念 Case A\n"
        f"• 资金来源: {overlong}\n"
        f"• 判断: {overlong}\n"
    )
    with patch("scheduler.intraday_agent.build_intraday_agent_model", return_value=_FAKE_MODEL), \
         patch("scheduler.intraday_agent.Runner.run", new=AsyncMock(return_value=_FakeRunResult(good_output))):
        result = await analyze_cause(_ANOMALY, "2026-07-09", _CONFIG)
    assert len(result.fund_source) <= 64
    assert len(result.judgement) <= 64


@pytest.mark.asyncio
async def test_analyze_cause_falls_back_on_exception():
    with patch("scheduler.intraday_agent.build_intraday_agent_model", return_value=_FAKE_MODEL), \
         patch("scheduler.intraday_agent.Runner.run", new=AsyncMock(side_effect=RuntimeError("boom"))):
        result = await analyze_cause(_ANOMALY, "2026-07-09", _CONFIG)
    assert result.llm_failed is True
