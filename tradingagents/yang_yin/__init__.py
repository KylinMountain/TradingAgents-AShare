"""阳谱近似模型 v0.7 — 截面因子 + 岭回归直接预测阳谱%

用法:
  from tradingagents.yang_yin import YangYinPipeline, run_scan_v7, save_snapshot

  pipe = YangYinPipeline()
  # 首轮：下载K线 + 构建面板
  pipe.download_full(start_date="20240101")
  pipe.build_panel()
  # 每日扫描
  snapshot = run_scan_v7(pipe)
  save_snapshot(snapshot, pipe)
  print(f"阳谱 {snapshot.yang_pct}%")
"""

from .pipeline import YangYinPipeline, get_stock_list
from .rate_limiter import RateLimiter
from .scoring import score_stock, StockScore, fetch_batch_fund_flow
from .aggregation import run_scan_v7, save_snapshot, load_history, YangYinSnapshot
from .factors_v7 import compute_factors, compute_factors_batch
from .model_v7 import predict_yangpu

__all__ = [
    "YangYinPipeline",
    "get_stock_list",
    "RateLimiter",
    "score_stock",
    "StockScore",
    "fetch_batch_fund_flow",
    "run_scan_v7",
    "save_snapshot",
    "load_history",
    "YangYinSnapshot",
    "compute_factors",
    "compute_factors_batch",
    "predict_yangpu",
]
