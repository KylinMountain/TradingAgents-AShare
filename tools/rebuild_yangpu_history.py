"""重建阳谱历史数据 — 用正确的 prev_yangpu 链式传递。

用法: python tools/rebuild_yangpu_history.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from tradingagents.yang_yin.pipeline import YangYinPipeline
from tradingagents.yang_yin.factors_v7 import compute_factors
from tradingagents.yang_yin.model_v7 import predict_yangpu
from tradingagents.yang_yin.aggregation import save_prev_yangpu

FIRST_PREV = 60.0  # 2025-11-06 真实阳谱值

pipeline = YangYinPipeline()

# 确保特征面板存在 — 一次向量化完成所有滚动特征，后续逐日聚合秒级
feat = pipeline.load_feature_panel()
if feat is None:
    print("构建特征面板...")
    feat = pipeline.build_feature_panel()

if feat is None or feat.empty:
    raise RuntimeError("特征面板不存在，先执行 build_panel() + build_feature_panel()")

all_dates = sorted(feat["trade_date"].unique())
print(f"特征面板: {len(all_dates)} 天, {all_dates[0]} ~ {all_dates[-1]}")

rows = []
prev = FIRST_PREV
for dt in all_dates:
    # compute_factors 检测到 rsi14 列 → 走 _compute_factors_from_features 秒级路径
    factors = compute_factors(feat, dt, prev_yangpu=prev)
    if factors is None:
        print(f"  {dt}: 因子计算返回None，跳过")
        continue

    pred = predict_yangpu(factors)
    n_stocks = feat[feat["trade_date"] == dt]["ts_code"].nunique()

    rows.append({
        "trade_date": dt,
        "total_scored": n_stocks,
        "yang_pct": round(pred, 1),
        "yin_pct": round(100 - pred, 1),
        "updated_at": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]} 15:00",
    })

    prev = pred
    if len(rows) % 30 == 0:
        print(f"  {dt}: 阳谱 {pred:.1f}% (prev={prev:.1f})")

# 写回 history
history_path = pipeline.summary_dir / "yang_yin_history.parquet"
hist_df = pd.DataFrame(rows)
hist_df.to_parquet(history_path, index=False)
print(f"\n历史已写入: {history_path} ({len(hist_df)} 条)")

# 更新 prev_yangpu.json
last = rows[-1]
save_prev_yangpu(last["yang_pct"], last["trade_date"], pipeline, source="market_close")
print(f"prev_yangpu 已更新: {last['yang_pct']}% (source=market_close)")

# 最后5天预览
print("\n最后5天:")
for r in rows[-5:]:
    print(f"  {r['trade_date']}: 阳谱 {r['yang_pct']}%  阴谱 {r['yin_pct']}%")
