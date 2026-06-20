"""全市场聚合统计 — v0.7截面因子 → 岭回归直接预测阳谱%"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from .pipeline import YangYinPipeline

logger = logging.getLogger(__name__)


@dataclass
class YangYinSnapshot:
    trade_date: str
    total_scored: int            # 有效股票数（面板中当日有数据的股票）
    yang_pct: float              # 阳谱% (0-100) — v0.7岭回归预测值
    yin_pct: float               # 阴谱% = 100 - 阳谱%
    data_time: str = ""          # 数据对应的时间点: 盘中=报价拉取时刻, 盘后=15:00收盘
    # 废弃的旧字段（保留兼容性，恒为0）
    yang_count: int = 0
    yin_count: int = 0
    avg_score: float = 0.0
    d1_trend_pct: float = 0.0
    d2_momentum_pct: float = 0.0
    d3_vol_price_pct: float = 0.0
    d4_capital_pct: float = 0.0
    sector_breakdown: dict = field(default_factory=dict)
    scores: pd.DataFrame | None = None


def run_scan_v7(
    pipeline: YangYinPipeline = None,
    trade_date: str = None,
    prev_yangpu: float | None = None,
) -> YangYinSnapshot:
    """v0.7 岭回归预测：计算截面因子 → 直接输出阳谱%。

    参数:
        pipeline: YangYinPipeline 实例
        trade_date: 目标交易日，默认今天
        prev_yangpu: 前一日阳谱值（估算或真实），None则用50中性值
    """
    from .factors_v7 import compute_factors
    from .model_v7 import predict_yangpu

    if pipeline is None:
        pipeline = YangYinPipeline()
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y%m%d")

    pipeline.update_daily(trade_date)

    panel = pipeline.load_panel()
    if panel is None or panel.empty:
        # 面板不存在，首次构建
        panel = pipeline.build_panel()

    if str(trade_date) not in panel["trade_date"].values:
        # 增量更新面板
        panel = pipeline.update_panel(trade_date)

    factors = compute_factors(panel, trade_date, prev_yangpu=prev_yangpu)
    if factors is None:
        raise RuntimeError(f"无法计算因子: {trade_date}")

    yang_pct = predict_yangpu(factors)
    total = panel[panel["trade_date"] == trade_date]["ts_code"].nunique()

    snapshot = YangYinSnapshot(
        trade_date=trade_date,
        total_scored=total,
        yang_pct=round(yang_pct, 1),
        yin_pct=round(100 - yang_pct, 1),
        data_time=f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]} 15:00",
    )

    # 持久化 prev_yangpu 供下一日（盘中或盘后）
    save_prev_yangpu(yang_pct, trade_date, pipeline)

    logger.info(
        f"扫描完成 {trade_date}: 阳谱 {snapshot.yang_pct}% | "
        f"有效股票 {total} | prev_yangpu={factors.get('prev_yangpu', 'N/A')}"
    )
    return snapshot


def save_snapshot(snapshot: YangYinSnapshot, pipeline: YangYinPipeline = None):
    """保存快照到 summary/yang_yin_history.parquet"""
    if pipeline is None:
        pipeline = YangYinPipeline()
    history_path = pipeline.summary_dir / "yang_yin_history.parquet"

    data_time = snapshot.data_time or datetime.now().strftime("%Y-%m-%d %H:%M")
    row = {
        "trade_date": snapshot.trade_date,
        "total_scored": snapshot.total_scored,
        "yang_pct": snapshot.yang_pct,
        "yin_pct": snapshot.yin_pct,
        "updated_at": data_time,
    }
    new_row = pd.DataFrame([row])

    if history_path.exists():
        hist = pd.read_parquet(history_path)
        hist = hist[hist["trade_date"] != snapshot.trade_date]
        hist = pd.concat([hist, new_row], ignore_index=True)
    else:
        hist = new_row

    hist.to_parquet(history_path, index=False)
    logger.info(f"快照已保存: {history_path}")


def load_history(pipeline: YangYinPipeline = None) -> pd.DataFrame:
    """加载历史阳谱记录"""
    if pipeline is None:
        pipeline = YangYinPipeline()
    history_path = pipeline.summary_dir / "yang_yin_history.parquet"
    if not history_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(history_path)


# ── prev_yangpu 持久化 ──────────────────────────────────

def _prev_yangpu_path(pipeline: YangYinPipeline = None):
    if pipeline is None:
        pipeline = YangYinPipeline()
    return pipeline.summary_dir / "prev_yangpu.json"


def load_prev_yangpu(pipeline: YangYinPipeline = None) -> float:
    """读取前一日预测的阳谱值，文件不存在则返回50"""
    import json
    path = _prev_yangpu_path(pipeline)
    if not path.exists():
        return 50.0
    data = json.loads(path.read_text(encoding="utf-8"))
    return float(data.get("yang_pct", 50.0))


def save_prev_yangpu(yang_pct: float, trade_date: str = None,
                     pipeline: YangYinPipeline = None):
    """保存当日阳谱预测值供下一日盘中使用"""
    import json
    path = _prev_yangpu_path(pipeline)
    data = {"yang_pct": round(yang_pct, 2), "trade_date": trade_date or ""}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    logger.info(f"prev_yangpu 已保存: {yang_pct:.1f}%")


# ── 盘中实时扫描 ──────────────────────────────────────

def run_scan_intraday(
    pipeline: YangYinPipeline = None,
    trade_date: str = None,
) -> YangYinSnapshot:
    """盘中实时阳谱：realtime_quote拉现价 → 合并面板历史 → 因子+预测。

    不保存快照（盘后 run_scan_v7 覆盖）。
    """
    from .factors_v7 import compute_factors_intraday
    from .model_v7 import predict_yangpu

    if pipeline is None:
        pipeline = YangYinPipeline()
    if trade_date is None:
        trade_date = pd.Timestamp.now().strftime("%Y%m%d")

    prev = load_prev_yangpu(pipeline)

    # 加载面板
    panel = pipeline.load_panel()
    if panel is None:
        raise RuntimeError("面板不存在，先执行 build_panel()")

    # 拉实时报价
    logger.info("拉取全市场实时报价...")
    realtime = pipeline.fetch_realtime_snapshot()
    if realtime.empty:
        raise RuntimeError("实时报价为空")

    # 计算因子
    factors = compute_factors_intraday(panel, realtime, trade_date, prev_yangpu=prev)
    if factors is None:
        raise RuntimeError(f"盘中因子计算失败: {trade_date}")

    yang_pct = predict_yangpu(factors)
    total = len(realtime)

    # 保存 prev 供下次使用
    save_prev_yangpu(yang_pct, trade_date, pipeline)

    snapshot = YangYinSnapshot(
        trade_date=trade_date,
        total_scored=total,
        yang_pct=round(yang_pct, 1),
        yin_pct=round(100 - yang_pct, 1),
        data_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    logger.info(
        f"盘中扫描 {trade_date}: 阳谱 {snapshot.yang_pct}% | "
        f"实时报价 {total} 只 | prev_yangpu={prev:.1f}"
    )
    return snapshot
