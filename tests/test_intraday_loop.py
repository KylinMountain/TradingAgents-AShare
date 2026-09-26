import asyncio
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

import scheduler.intraday as intraday
from scheduler.intraday import _BoostState, run_intraday_loop_forever, run_one_tick
from scheduler.intraday_rules import BoardAnomaly


@pytest.fixture(autouse=True)
def _clear_attribution_dedup():
    intraday._attributed_keys.clear()
    intraday._attributed_day = None
    yield
    intraday._attributed_keys.clear()
    intraday._attributed_day = None


def test_boost_state_default_is_normal_interval():
    boost = _BoostState()
    assert boost.current_interval(1000.0) == 300


def test_boost_state_triggers_then_expires():
    boost = _BoostState()
    boost.trigger(now_ts=1000.0)
    assert boost.current_interval(1000.0) == 120
    assert boost.current_interval(1000.0 + 900 - 1) == 120
    assert boost.current_interval(1000.0 + 900 + 1) == 300


@pytest.mark.asyncio
async def test_run_one_tick_no_anomaly_does_nothing():
    with patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_concept_fund_flow_df", return_value=pd.DataFrame()), \
         patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_zt_pool_df", return_value=pd.DataFrame()), \
         patch("scheduler.intraday.analyze_cause", new=AsyncMock()) as mock_analyze, \
         patch("scheduler.intraday._persist_signal") as mock_persist:
        found = await run_one_tick("2026-07-10")
    assert found is False
    mock_analyze.assert_not_called()
    mock_persist.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_tick_zt_concentration_only_boosts_without_llm_call():
    zt_df = pd.DataFrame([{"code": i} for i in range(81)])
    with patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_concept_fund_flow_df", return_value=pd.DataFrame()), \
         patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_zt_pool_df", return_value=zt_df), \
         patch("scheduler.intraday.analyze_cause", new=AsyncMock()) as mock_analyze, \
         patch("scheduler.intraday._persist_signal") as mock_persist:
        found = await run_one_tick("2026-07-10")
    assert found is True
    mock_analyze.assert_not_called()
    mock_persist.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_tick_board_anomaly_triggers_attribution_and_persist():
    concept_df = pd.DataFrame([{"行业": "CRO概念", "行业-涨跌幅": 4.43, "净额": 19.56}])
    fake_result = type("R", (), {"cause_summary": "text", "fund_source": "机构", "judgement": "持续行情", "llm_failed": False})()

    with patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_concept_fund_flow_df", return_value=concept_df), \
         patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_zt_pool_df", return_value=pd.DataFrame()), \
         patch("scheduler.intraday.analyze_cause", new=AsyncMock(return_value=fake_result)) as mock_analyze, \
         patch("scheduler.intraday._persist_signal") as mock_persist, \
         patch("api.main._build_runtime_config", return_value={"llm_provider": "openai"}):
        found = await run_one_tick("2026-07-10")

    assert found is True
    mock_analyze.assert_called_once()
    called_anomaly = mock_analyze.call_args[0][0]
    assert isinstance(called_anomaly, BoardAnomaly)
    assert called_anomaly.board_name == "CRO概念"
    mock_persist.assert_called_once_with("2026-07-10", called_anomaly, fake_result)


@pytest.mark.asyncio
async def test_run_one_tick_processes_multiple_anomalies_concurrently_and_isolated():
    concept_df = pd.DataFrame(
        [
            {"行业": "板块甲", "行业-涨跌幅": 4.43, "净额": 19.56},
            {"行业": "板块乙", "行业-涨跌幅": 5.0, "净额": 20.0},
        ]
    )
    fake_result = type("R", (), {"cause_summary": "text", "fund_source": None, "judgement": None, "llm_failed": False})()

    async def _analyze(anomaly, trade_date, config):
        if anomaly.board_name == "板块甲":
            raise RuntimeError("boom")
        return fake_result

    with patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_concept_fund_flow_df", return_value=concept_df), \
         patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_zt_pool_df", return_value=pd.DataFrame()), \
         patch("scheduler.intraday.analyze_cause", new=AsyncMock(side_effect=_analyze)), \
         patch("scheduler.intraday._persist_signal") as mock_persist, \
         patch("api.main._build_runtime_config", return_value={"llm_provider": "openai"}):
        found = await run_one_tick("2026-07-10")

    assert found is True
    # 板块甲's attribution raised, but 板块乙 must still be persisted.
    assert mock_persist.call_count == 1
    assert mock_persist.call_args[0][1].board_name == "板块乙"


@pytest.mark.asyncio
async def test_run_one_tick_survives_concept_fetch_failure():
    with patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_concept_fund_flow_df", side_effect=RuntimeError("network down")), \
         patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_zt_pool_df", return_value=pd.DataFrame()):
        found = await run_one_tick("2026-07-10")
    assert found is False


@pytest.mark.asyncio
async def test_run_intraday_loop_forever_restarts_after_crash_then_stops_on_cancel():
    calls = {"n": 0}

    async def _fake_loop():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("crash")
        raise asyncio.CancelledError()

    with patch("scheduler.intraday.intraday_loop", new=_fake_loop), \
         patch("scheduler.intraday._RESTART_BACKOFF_SECONDS", 0):
        with pytest.raises(asyncio.CancelledError):
            await run_intraday_loop_forever()

    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_same_anomaly_is_attributed_only_once_per_day():
    """热门板块每个轮询周期都会重复命中(净额为当日累计值),但同一
    (交易日, 板块, 异动类型) 每天只追因一次;新的一天允许再次追因。"""
    concept_df = pd.DataFrame([{"行业": "CRO概念", "行业-涨跌幅": 4.43, "净额": 19.56}])
    fake_result = type("R", (), {"cause_summary": "text", "fund_source": None, "judgement": None, "llm_failed": False})()

    with patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_concept_fund_flow_df", return_value=concept_df), \
         patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_zt_pool_df", return_value=pd.DataFrame()), \
         patch("scheduler.intraday.analyze_cause", new=AsyncMock(return_value=fake_result)) as mock_analyze, \
         patch("scheduler.intraday._persist_signal"), \
         patch("api.main._build_runtime_config", return_value={"llm_provider": "openai"}):
        assert await run_one_tick("2026-07-10") is True
        # 第二次 tick 仍然命中(仍触发 boost),但不再重复追因/落库
        assert await run_one_tick("2026-07-10") is True

    mock_analyze.assert_called_once()

    with patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_concept_fund_flow_df", return_value=concept_df), \
         patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_zt_pool_df", return_value=pd.DataFrame()), \
         patch("scheduler.intraday.analyze_cause", new=AsyncMock(return_value=fake_result)) as mock_analyze_next_day, \
         patch("scheduler.intraday._persist_signal"), \
         patch("api.main._build_runtime_config", return_value={"llm_provider": "openai"}):
        assert await run_one_tick("2026-07-11") is True

    mock_analyze_next_day.assert_called_once()


@pytest.mark.asyncio
async def test_per_tick_attribution_cap_keeps_top_by_abs_inflow():
    """普涨日命中板块数可能远超上限,每 tick 只追因 |净额| 最大的前 5 个。"""
    concept_df = pd.DataFrame(
        [{"行业": f"板块{i}", "行业-涨跌幅": 4.5, "净额": 3.1 + i} for i in range(7)]
    )
    fake_result = type("R", (), {"cause_summary": "text", "fund_source": None, "judgement": None, "llm_failed": False})()

    with patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_concept_fund_flow_df", return_value=concept_df), \
         patch("tradingagents.dataflows.providers.cn_akshare_provider.CnAkshareProvider.get_zt_pool_df", return_value=pd.DataFrame()), \
         patch("scheduler.intraday.analyze_cause", new=AsyncMock(return_value=fake_result)) as mock_analyze, \
         patch("scheduler.intraday._persist_signal"), \
         patch("api.main._build_runtime_config", return_value={"llm_provider": "openai"}):
        assert await run_one_tick("2026-07-10") is True

    assert mock_analyze.call_count == 5
    attributed = {call.args[0].board_name for call in mock_analyze.call_args_list}
    assert attributed == {"板块6", "板块5", "板块4", "板块3", "板块2"}


@pytest.mark.asyncio
async def test_loop_survives_wedged_tick_via_timeout():
    """akshare 调用卡死(无 socket 超时的 TCP 读)时,单 tick 必须在
    _TICK_TIMEOUT_SECONDS 后超时,循环继续而不是永久挂住。"""
    from datetime import datetime

    async def _wedged(*_args, **_kwargs):
        await asyncio.Event().wait()

    fake_now = datetime(2026, 7, 10, 10, 0, 0)
    with patch("tradingagents.dataflows.trade_calendar.cn_market_phase", return_value="in_session"), \
         patch("tradingagents.dataflows.trade_calendar.now_cn", return_value=fake_now), \
         patch("scheduler.intraday.run_one_tick", side_effect=_wedged), \
         patch("scheduler.intraday._TICK_TIMEOUT_SECONDS", 0.01):
        loop_task = asyncio.create_task(intraday.intraday_loop())
        await asyncio.sleep(0.1)
        assert not loop_task.done(), "超时后循环应继续运行,而不是挂死或退出"
        loop_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await loop_task


def test_persist_signal_swallows_duplicate_key():
    """进程重启后内存去重丢失,DB 唯一约束兜底:重复插入不得抛出。"""
    from sqlalchemy.exc import IntegrityError

    from scheduler.intraday import _persist_signal

    class _FakeDB:
        rolled_back = False

        def add(self, _row):
            pass

        def commit(self):
            raise IntegrityError("INSERT INTO intraday_signals", {}, Exception("duplicate key"))

        def rollback(self):
            self.rolled_back = True

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    anomaly = BoardAnomaly("板块", "A", 4.0, 10.0)
    result = type("R", (), {"cause_summary": "x", "fund_source": None, "judgement": None, "llm_failed": True})()
    fake_db = _FakeDB()
    with patch("api.database.get_db_ctx", return_value=fake_db):
        _persist_signal("2026-07-10", anomaly, result)
    assert fake_db.rolled_back
