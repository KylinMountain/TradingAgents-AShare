"""阳谱近似模型 v0.7 — 截面因子 + 岭回归直接预测阳谱%

盘后:
  from tradingagents.yang_yin import YangYinPipeline, run_scan_v7, save_snapshot
  pipe = YangYinPipeline()
  snapshot = run_scan_v7(pipe)
  save_snapshot(snapshot, pipe)

盘中:
  from tradingagents.yang_yin import YangYinPipeline, run_scan_intraday
  pipe = YangYinPipeline()
  snapshot = run_scan_intraday(pipe)  # 自动拉实时报价
"""

from .pipeline import YangYinPipeline, get_stock_list
from .rate_limiter import RateLimiter
from .scoring import score_stock, StockScore, fetch_batch_fund_flow
from .aggregation import (
    run_scan_v7,
    run_scan_intraday,
    save_snapshot,
    load_history,
    load_prev_yangpu,
    save_prev_yangpu,
    YangYinSnapshot,
)
from .factors_v7 import compute_factors, compute_factors_batch, compute_factors_intraday
from .model_v7 import predict_yangpu
from .gold_silver_v8_1 import (
    predict_gold_finger,
    generate_history as generate_gold_finger_history,
    load_gold_finger_history,
    save_gold_finger_history,
)
from .red_green_bg import (
    compute_gs,
    compute_background,
    generate_history as generate_bg_history,
    get_history as get_bg_history,
    load_bg_state,
    save_bg_state,
    update_bg_state,
)

__all__ = [
    "YangYinPipeline",
    "get_stock_list",
    "RateLimiter",
    "score_stock",
    "StockScore",
    "fetch_batch_fund_flow",
    "run_scan_v7",
    "run_scan_intraday",
    "save_snapshot",
    "load_history",
    "load_prev_yangpu",
    "save_prev_yangpu",
    "YangYinSnapshot",
    "compute_factors",
    "compute_factors_batch",
    "compute_factors_intraday",
    "predict_yangpu",
    "predict_gold_finger",
    "generate_gold_finger_history",
    "load_gold_finger_history",
    "save_gold_finger_history",
    "compute_gs",
    "compute_background",
    "generate_bg_history",
    "get_bg_history",
    "load_bg_state",
    "save_bg_state",
    "update_bg_state",
]
