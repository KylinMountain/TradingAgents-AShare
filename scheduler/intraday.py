"""Global, always-on intraday concept-board anomaly scan.

Runs as an independent asyncio task inside the scheduler process (see
scheduler/main.py), separate from the per-user scheduled-analysis loop.
Trading days only, 9:30-15:00 (lunch break skipped), 5-minute polling
that boosts to 2 minutes for 15 minutes after any anomaly is found.

Detection is pure code (scheduler/intraday_rules.py); the only LLM call
is the narrow cause-attribution agent (scheduler/intraday_agent.py), and
only for boards that actually tripped a rule. See
docs/superpowers/specs/2026-07-10-intraday-analysis-design.md.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

import pandas as pd

from scheduler.intraday_agent import analyze_cause
from scheduler.intraday_rules import BoardAnomaly, detect_board_anomalies, detect_zt_pool_concentration

logger = logging.getLogger(__name__)

_NORMAL_INTERVAL_SECONDS = 300  # 5 min
_BOOST_INTERVAL_SECONDS = 120  # 2 min
_BOOST_DURATION_SECONDS = 900  # 15 min
_TICK_TIMEOUT_SECONDS = 180  # one wedged akshare call must not stall the loop
_MAX_ATTRIBUTIONS_PER_TICK = 5  # cap LLM cost on broad-rally days

_RESTART_BACKOFF_SECONDS = 30

# 概念板块资金净额是当日累计值,热门板块命中后每个轮询周期都会重复命中;
# 同一 (交易日, 板块, 异动类型) 每天只追因一次。进程重启后由
# IntradaySignalDB 的 (trade_date, board_name, anomaly_case) 唯一约束兜底。
_attributed_keys: set[tuple[str, str, str]] = set()
_attributed_day: str | None = None


class _BoostState:
    """Tracks the temporary poll-interval speedup after an anomaly is found."""

    def __init__(self) -> None:
        self._boosted_until_ts = 0.0

    def trigger(self, now_ts: float) -> None:
        self._boosted_until_ts = now_ts + _BOOST_DURATION_SECONDS

    def current_interval(self, now_ts: float) -> int:
        return _BOOST_INTERVAL_SECONDS if now_ts < self._boosted_until_ts else _NORMAL_INTERVAL_SECONDS


def _filter_unattributed(trade_date: str, anomalies: list[BoardAnomaly]) -> list[BoardAnomaly]:
    """Drop (board, case) combos already attributed today; mark the rest as seen.

    Marked on detection (not on success): even an llm_failed row is already
    persisted with raw data, and re-attributing every poll would spam both
    the LLM budget and the feed on exactly the high-volatility days this
    feature exists for.
    """
    global _attributed_day
    if _attributed_day != trade_date:
        _attributed_keys.clear()
        _attributed_day = trade_date
    fresh: list[BoardAnomaly] = []
    for anomaly in anomalies:
        key = (trade_date, anomaly.board_name, anomaly.anomaly_case)
        if key in _attributed_keys:
            continue
        _attributed_keys.add(key)
        fresh.append(anomaly)
    return fresh


def _persist_signal(trade_date: str, anomaly: BoardAnomaly, result) -> None:
    from sqlalchemy.exc import IntegrityError

    from api.database import IntradaySignalDB, get_db_ctx

    with get_db_ctx() as db:
        db.add(
            IntradaySignalDB(
                id=uuid4().hex,
                trade_date=trade_date,
                board_name=anomaly.board_name,
                anomaly_case=anomaly.anomaly_case,
                change_pct=anomaly.change_pct,
                net_inflow=anomaly.net_inflow,
                cause_summary=result.cause_summary,
                fund_source=result.fund_source,
                judgement=result.judgement,
                llm_failed=result.llm_failed,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            # Backstop for the in-memory dedup: after a scheduler restart the
            # same (day, board, case) can be attributed once more, but never
            # persisted twice.
            db.rollback()
            logger.info(
                "[Intraday] %s Case %s on %s already persisted, skipping duplicate",
                anomaly.board_name, anomaly.anomaly_case, trade_date,
            )


async def _process_anomaly(trade_date: str, anomaly: BoardAnomaly, config: dict) -> None:
    """Attribute + persist a single anomaly. Isolated so one board's failure
    (LLM error, DB write error) never loses the other anomalies in the tick."""
    try:
        result = await analyze_cause(anomaly, trade_date, config)
        await asyncio.to_thread(_persist_signal, trade_date, anomaly, result)
        logger.info(
            "[Intraday] %s Case %s persisted (llm_failed=%s)",
            anomaly.board_name, anomaly.anomaly_case, result.llm_failed,
        )
    except Exception as exc:
        logger.error(
            "[Intraday] failed to process %s Case %s: %s",
            anomaly.board_name, anomaly.anomaly_case, exc,
        )


async def run_one_tick(trade_date: str) -> bool:
    """Fetch → detect → attribute → persist. Returns True iff any anomaly was found (drives boost)."""
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider

    provider = CnAkshareProvider()

    try:
        concept_df = await asyncio.to_thread(provider.get_concept_fund_flow_df)
    except Exception as exc:
        logger.warning("[Intraday] concept fund flow fetch failed: %s", exc)
        concept_df = pd.DataFrame()

    try:
        zt_df = await asyncio.to_thread(provider.get_zt_pool_df, trade_date)
    except Exception as exc:
        logger.warning("[Intraday] zt pool fetch failed: %s", exc)
        zt_df = pd.DataFrame()

    board_anomalies = detect_board_anomalies(concept_df)
    zt_concentrated = detect_zt_pool_concentration(zt_df)

    if not board_anomalies and not zt_concentrated:
        return False

    if board_anomalies:
        fresh_anomalies = _filter_unattributed(trade_date, board_anomalies)
        if len(fresh_anomalies) < len(board_anomalies):
            logger.info(
                "[Intraday] %d/%d anomalies already attributed today, skipping re-attribution",
                len(board_anomalies) - len(fresh_anomalies), len(board_anomalies),
            )
        # Cap per-tick attributions by |net_inflow|: a broad rally can match
        # dozens of boards, and unbounded fan-out stampedes both the LLM
        # provider and the akshare lock.
        top_anomalies = sorted(fresh_anomalies, key=lambda a: abs(a.net_inflow), reverse=True)[
            :_MAX_ATTRIBUTIONS_PER_TICK
        ]
        if len(top_anomalies) < len(fresh_anomalies):
            logger.info(
                "[Intraday] %d fresh anomalies exceed per-tick cap, attributing top %d by |net_inflow|",
                len(fresh_anomalies), len(top_anomalies),
            )
        if top_anomalies:
            from api.main import _build_runtime_config

            config = await asyncio.to_thread(_build_runtime_config, {})
            # Concurrent, not sequential: each anomaly's attribution has its own
            # timeout (scheduler/intraday_agent.py), and processing them one at a
            # time can eat most/all of the post-anomaly boost window on a
            # multi-board tick -- exactly the high-volatility case boost exists
            # to serve fastest.
            await asyncio.gather(*(_process_anomaly(trade_date, a, config) for a in top_anomalies))

    return True


async def intraday_loop() -> None:
    """Trading-hours-only concept-board anomaly scan, one tick per iteration."""
    from tradingagents.dataflows.trade_calendar import cn_market_phase, now_cn
    from tradingagents.dataflows.providers.cn_akshare_provider import set_scheduled_task_context

    # Mark every akshare call this task (and everything it awaits/to_thread's,
    # which inherits this task's contextvars) makes as "scheduled" so it's
    # capped by AKSHARE_CALL_LOCK's reserved sub-pool instead of competing
    # with interactive frontend requests at full priority.
    set_scheduled_task_context(True)

    boost = _BoostState()
    logger.info("[Intraday] Loop started.")
    while True:
        now = now_cn()
        try:
            if cn_market_phase(now) == "in_session":
                # wait_for: a wedged fetch (akshare TCP read with no timeout in
                # this process) must time the tick out instead of hanging the
                # loop forever -- the supervisor can only restart a task that
                # actually crashes. The orphaned thread stays bounded by the
                # akshare lock's stale reclaim.
                found = await asyncio.wait_for(
                    run_one_tick(now.strftime("%Y-%m-%d")),
                    timeout=_TICK_TIMEOUT_SECONDS,
                )
                if found:
                    boost.trigger(now.timestamp())
                    logger.info("[Intraday] anomaly found, boosting to %ds interval", _BOOST_INTERVAL_SECONDS)
        except Exception as exc:
            # A single bad tick (akshare hiccup, DB blip, etc.) must never kill the loop.
            logger.error("[Intraday] tick failed: %s", exc)
        interval = boost.current_interval(now_cn().timestamp())
        await asyncio.sleep(interval)


async def run_intraday_loop_forever() -> None:
    """Supervisor: restart intraday_loop with backoff if it ever exits
    unexpectedly. Real cancellation (process shutdown) is not swallowed."""
    while True:
        try:
            await intraday_loop()
            logger.error("[Intraday] loop returned unexpectedly, restarting in %ds", _RESTART_BACKOFF_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[Intraday] loop crashed, restarting in %ds: %s", _RESTART_BACKOFF_SECONDS, exc)
        await asyncio.sleep(_RESTART_BACKOFF_SECONDS)
