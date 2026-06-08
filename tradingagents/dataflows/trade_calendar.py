from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

logger = logging.getLogger(__name__)
CN_TZ = ZoneInfo("Asia/Shanghai")

_trade_dates_cache: tuple[list[date], set[date]] | None = None
_trade_dates_cache_time: datetime | None = None
_TRADE_DATES_CACHE_TTL = timedelta(hours=1)


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def cn_today_str() -> str:
    return now_cn().date().strftime("%Y-%m-%d")


def _parse_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _load_cn_trade_dates() -> tuple[list[date], set[date]]:
    global _trade_dates_cache, _trade_dates_cache_time
    now = datetime.now()
    if _trade_dates_cache is not None and _trade_dates_cache_time is not None:
        if now - _trade_dates_cache_time < _TRADE_DATES_CACHE_TTL:
            return _trade_dates_cache

    try:
        import akshare as ak  # type: ignore

        df = ak.tool_trade_date_hist_sina()
        if df is None or df.empty or "trade_date" not in df.columns:
            raise ValueError("empty trade date table")
        dates = sorted(
            pd_dt.date()
            for pd_dt in pd.to_datetime(df["trade_date"], errors="coerce")
            if str(pd_dt) != "NaT"
        )
        _trade_dates_cache = (dates, set(dates))
        _trade_dates_cache_time = now
        return _trade_dates_cache
    except Exception as e:
        logger.warning("交易日历加载失败，降级为仅周末过滤: %s", e)
        if _trade_dates_cache is not None:
            return _trade_dates_cache
        return [], set()


def is_cn_symbol(symbol: str) -> bool:
    s = symbol.strip().upper()
    return bool(re.match(r"^\d{6}(\.(SH|SZ|SS))?$", s))


def is_cn_trading_day(date_str: str) -> bool:
    d = _parse_date(date_str)
    dates, dates_set = _load_cn_trade_dates()
    if dates:
        return d in dates_set
    return d.weekday() < 5


def previous_cn_trading_day(date_str: str) -> str:
    d = _parse_date(date_str)
    dates, _ = _load_cn_trade_dates()
    if dates:
        idx = 0
        # 找到首个 >= d 的位置
        lo, hi = 0, len(dates)
        while lo < hi:
            mid = (lo + hi) // 2
            if dates[mid] < d:
                lo = mid + 1
            else:
                hi = mid
        idx = lo - 1
        if idx >= 0:
            return dates[idx].strftime("%Y-%m-%d")
    # Fallback to weekend-only rollback
    cur = d
    while True:
        cur = cur.fromordinal(cur.toordinal() - 1)
        if cur.weekday() < 5:
            return cur.strftime("%Y-%m-%d")


def cn_market_phase(now: datetime | None = None) -> str:
    now_dt = now or now_cn()
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=CN_TZ)
    else:
        now_dt = now_dt.astimezone(CN_TZ)

    today = now_dt.date().strftime("%Y-%m-%d")
    if not is_cn_trading_day(today):
        return "closed"

    t = now_dt.time()
    if t < time(9, 30):
        return "pre_open"
    if time(9, 30) <= t < time(11, 30):
        return "in_session"
    if time(11, 30) <= t < time(13, 0):
        return "lunch_break"
    if time(13, 0) <= t < time(15, 0):
        return "in_session"
    return "post_close"


def cn_no_data_reason(date_str: str) -> str:
    if not is_cn_trading_day(date_str):
        return "N/A：非交易日（A股休市）"

    today = cn_today_str()
    if date_str == today:
        phase = cn_market_phase()
        if phase == "pre_open":
            return "N/A：今日尚未开盘"
        if phase in ("in_session", "lunch_break"):
            return "N/A：今日盘中，日线未收盘（可参考实时价）"
        if phase == "post_close":
            return "N/A：今日已收盘，数据源尚未更新"

    return "N/A：该交易日暂无数据（可能停牌或数据延迟）"
