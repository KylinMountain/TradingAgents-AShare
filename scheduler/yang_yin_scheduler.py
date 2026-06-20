"""阳谱定时任务 — 盘中15分钟快照 + 盘后存储

集成到 scheduler/main.py 的 _startup() 中运行。
"""

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

CST = ZoneInfo("Asia/Shanghai")

# 盘中时段
MORNING_START = (9, 30)
MORNING_END = (11, 30)
AFTERNOON_START = (13, 0)
AFTERNOON_END = (15, 0)

# 盘后计算时间
POST_MARKET_HOUR = 16
POST_MARKET_MINUTE = 5

# 盘中快照间隔（分钟）
INTRADAY_INTERVAL = 15


def _is_trading_time(now: datetime) -> bool:
    t = (now.hour, now.minute)
    return (MORNING_START <= t <= MORNING_END or
            AFTERNOON_START <= t <= AFTERNOON_END)


def _is_post_market_time(now: datetime) -> bool:
    return (now.hour, now.minute) >= (POST_MARKET_HOUR, POST_MARKET_MINUTE)


def _is_trading_day(date_str: str) -> bool:
    from tradingagents.dataflows.trade_calendar import is_cn_trading_day
    return is_cn_trading_day(date_str)


async def _wait_until(target_hour: int, target_min: int = 0):
    """Sleep until the next occurrence of target_hour:target_min CST."""
    now = datetime.now(CST)
    target = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
    if target <= now:
        return  # already passed
    wait_sec = (target - now).total_seconds()
    logger.info(f"等待 {wait_sec:.0f}s 到 {target_hour:02d}:{target_min:02d}")
    await asyncio.sleep(wait_sec)


async def _run_intraday_scan(trade_date: str):
    """执行一次盘中快照。单次失败静默跳过，连续失败告警。"""
    try:
        from tradingagents.yang_yin import YangYinPipeline, run_scan_intraday
        pipeline = YangYinPipeline()
        snapshot = await asyncio.to_thread(run_scan_intraday, pipeline, trade_date)
        now = datetime.now(CST).strftime("%H:%M")
        logger.info(f"[{now}] 盘中阳谱 {snapshot.yang_pct}%  阴谱 {snapshot.yin_pct}%")
        _intraday_fail_count = 0
        return snapshot
    except Exception as e:
        _intraday_fail_count = getattr(_run_intraday_scan, "_fail_count", 0) + 1
        _run_intraday_scan._fail_count = _intraday_fail_count
        if _intraday_fail_count <= 2:
            logger.warning(f"盘中快照失败 ({_intraday_fail_count}/3): {e}")
        else:
            logger.error(f"盘中快照连续失败 {_intraday_fail_count} 次: {e}")
        return None


async def _run_post_market_scan(trade_date: str):
    """盘后完整计算 + 存储。update_daily失败重试一次，全流程失败告警。"""
    from tradingagents.yang_yin import YangYinPipeline, run_scan_v7, save_snapshot

    pipeline = YangYinPipeline()

    # update_daily 带重试
    for attempt in range(2):
        try:
            n = pipeline.update_daily(trade_date)
            logger.info(f"update_daily: {n} 只入库")
            break
        except Exception as e:
            if attempt == 0:
                logger.warning(f"update_daily 失败，60s后重试: {e}")
                await asyncio.sleep(60)
            else:
                logger.error(f"update_daily 重试仍失败: {e}")
                return None

    # update_panel / feature_panel
    try:
        pipeline.update_panel(trade_date)
        pipeline.update_feature_panel(trade_date)
    except Exception as e:
        logger.error(f"面板更新失败: {e}")
        return None

    # 阳谱计算 + 存储
    try:
        snapshot = await asyncio.to_thread(run_scan_v7, pipeline, trade_date)
        await asyncio.to_thread(save_snapshot, snapshot, pipeline)
        logger.info(f"盘后存储完成: 阳谱 {snapshot.yang_pct}%  阴谱 {snapshot.yin_pct}%")
        return snapshot
    except Exception as e:
        logger.error(f"盘后计算/存储失败: {e}")
        return None


async def yang_yin_loop():
    """阳谱定时循环 — 盘中每15分钟快照 + 盘后16:05完整计算。

    由 scheduler/main.py 的 _startup() 调用，与主调度循环并行运行。
    """
    logger.info("[阳谱] 定时循环启动 (盘中每15分, 盘后16:05)")

    while True:
        try:
            now = datetime.now(CST)
            today = now.strftime("%Y-%m-%d")
            today_yyyymmdd = now.strftime("%Y%m%d")

            if not _is_trading_day(today):
                await asyncio.sleep(60)
                continue

            # ── 盘中快照 ──
            if _is_trading_time(now):
                # 对齐到整15分钟
                next_minute = ((now.minute // INTRADAY_INTERVAL) + 1) * INTRADAY_INTERVAL
                if next_minute >= 60:
                    wait = 60  # 跨小时，等1分钟再检查
                else:
                    # 等待到下一个15分钟节点
                    target = now.replace(minute=next_minute, second=5, microsecond=0)
                    wait = max(1, (target - now).total_seconds())
                await asyncio.sleep(wait)
                await _run_intraday_scan(today_yyyymmdd)
                continue

            # ── 盘后 ──
            if _is_post_market_time(now):
                await _run_post_market_scan(today_yyyymmdd)
                # 等到次日再检查
                await asyncio.sleep(3600)
                continue

            # 非交易时间，每分钟检查一次
            await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("[阳谱] 定时循环已取消")
            break
        except Exception as e:
            logger.error(f"[阳谱] 循环异常: {e}")
            await asyncio.sleep(60)
