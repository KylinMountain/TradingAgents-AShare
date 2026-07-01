"""大盘点金数据新鲜度检测 + 按需增量更新。

当 API 端点检测到缓存数据不是最新交易日时，自动补齐缺失日期。
不跑全量重建，只补缺口。
"""

import logging
import threading
import time
from datetime import datetime, timedelta

import pandas as pd

from .pipeline import YangYinPipeline

logger = logging.getLogger(__name__)

_update_lock = threading.Lock()
_MAX_MISSING_DAYS = 5


def _get_latest_cached_date(pipeline: YangYinPipeline) -> str | None:
    """读取 yang_yin_history.parquet 中最大的 trade_date，无数据返回 None。"""
    history_path = pipeline.summary_dir / "yang_yin_history.parquet"
    if not history_path.exists():
        return None
    hist = pd.read_parquet(history_path)
    if hist.empty:
        return None
    return str(hist["trade_date"].max())


def _get_target_trade_date() -> str:
    """返回"应该更新到哪个交易日"的 YYYYMMDD。

    规则：当前北京时间如果是交易日且已开盘→今天；盘前→上一交易日；非交易日→上一交易日。
    """
    from tradingagents.dataflows.trade_calendar import now_cn, is_cn_trading_day, cn_market_phase, previous_cn_trading_day

    now = now_cn()
    today_str = now.strftime("%Y-%m-%d")

    if not is_cn_trading_day(today_str):
        return previous_cn_trading_day(today_str).replace("-", "")

    phase = cn_market_phase(now)
    if phase == "pre_open":
        return previous_cn_trading_day(today_str).replace("-", "")

    return today_str.replace("-", "")


def _get_missing_trade_dates(latest_cached: str, target: str) -> list[str]:
    """返回 latest_cached(含)到 target(含)之间缺少的交易日列表(YYYYMMDD)。"""
    from tradingagents.dataflows.trade_calendar import is_cn_trading_day

    start = datetime.strptime(latest_cached, "%Y%m%d") + timedelta(days=1)
    end = datetime.strptime(target, "%Y%m%d")

    missing = []
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        if is_cn_trading_day(ds):
            missing.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return missing


def _do_post_market_update_sync(pipeline: YangYinPipeline, trade_date: str) -> None:
    """同步版盘后完整更新（复刻 scheduler 逻辑）。

    步骤：update_daily(带重试) → update_panel → update_feature_panel →
          run_scan_v7 → save_snapshot → _update_gold_finger → _update_red_green_bg
    """
    from .aggregation import run_scan_v7, save_snapshot, _update_gold_finger, _update_red_green_bg

    # update_daily 带重试
    for attempt in range(2):
        try:
            n = pipeline.update_daily(trade_date)
            logger.info(f"[staleness] update_daily({trade_date}): {n} 只入库")
            break
        except Exception as e:
            if attempt == 0:
                logger.warning(f"[staleness] update_daily 失败，60s后重试: {e}")
                time.sleep(60)
            else:
                logger.error(f"[staleness] update_daily 重试仍失败: {e}")
                raise

    pipeline.update_panel(trade_date)
    pipeline.update_feature_panel(trade_date)

    snapshot = run_scan_v7(pipeline, trade_date)
    save_snapshot(snapshot, pipeline)

    panel = pipeline.load_panel()
    _update_gold_finger(panel, pipeline, trade_date)
    _update_red_green_bg(pipeline, trade_date)

    from .aggregation import _notify_dapan_update
    _notify_dapan_update(pipeline)


def _do_intraday_update_sync(pipeline: YangYinPipeline, trade_date: str) -> None:
    """同步版盘中快照（用实时报价，快）。"""
    from .aggregation import run_scan_intraday, save_snapshot, _update_gold_finger, _update_red_green_bg

    snapshot = run_scan_intraday(pipeline, trade_date)
    save_snapshot(snapshot, pipeline)

    panel = pipeline.load_panel()
    _update_gold_finger(panel, pipeline, trade_date)
    _update_red_green_bg(pipeline, trade_date)

    from .aggregation import _notify_dapan_update
    _notify_dapan_update(pipeline)


def ensure_data_fresh(pipeline: YangYinPipeline = None) -> dict:
    """检测阳谱/金手指/红绿背景数据是否过期，过期则增量补齐。

    返回 {"updated": bool, "latest_date": str|None, "message": str}
    """
    if pipeline is None:
        pipeline = YangYinPipeline()

    target = _get_target_trade_date()
    cached = _get_latest_cached_date(pipeline)

    if cached and cached >= target:
        logger.debug(f"[staleness] 数据已是最新 (cached={cached}, target={target})")
        return {"updated": False, "latest_date": cached, "message": "数据已是最新"}

    # 非阻塞加锁：已有其他请求在更新则跳过
    if not _update_lock.acquire(blocking=False):
        logger.info("[staleness] 更新已在进行中，跳过")
        return {"updated": False, "latest_date": cached, "message": "更新进行中"}

    try:
        # 二次检查：拿锁后重新读，防止重复计算
        cached2 = _get_latest_cached_date(pipeline)
        if cached2 and cached2 >= target:
            return {"updated": False, "latest_date": cached2, "message": "数据已是最新(二次检查)"}

        missing = _get_missing_trade_dates(cached2 or "20000101", target)
        if not missing:
            return {"updated": False, "latest_date": cached2, "message": "无缺失交易日"}

        # 缺失超限只补最近 N 天
        if len(missing) > _MAX_MISSING_DAYS:
            logger.warning(f"[staleness] 缺失 {len(missing)} 天，只补最近 {_MAX_MISSING_DAYS} 天")
            missing = missing[-_MAX_MISSING_DAYS:]

        from tradingagents.dataflows.trade_calendar import now_cn, cn_market_phase
        now = now_cn()
        phase = cn_market_phase(now)
        in_trading = phase in ("in_session", "lunch_break")

        for date_str in missing:
            use_intraday = in_trading and date_str == target
            if use_intraday:
                logger.info(f"[staleness] 盘中快照 {date_str}")
                _do_intraday_update_sync(pipeline, date_str)
            else:
                logger.info(f"[staleness] 盘后更新 {date_str}")
                _do_post_market_update_sync(pipeline, date_str)

        logger.info(f"[staleness] 完成: 更新了 {len(missing)} 天")
        return {"updated": True, "latest_date": target, "message": f"更新了 {len(missing)} 天"}

    except Exception as e:
        logger.error(f"[staleness] 更新失败: {e}")
        raise
    finally:
        _update_lock.release()
