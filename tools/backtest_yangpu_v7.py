"""阳谱v0.7回测：110天因子计算+预测 vs 同花顺真实值"""
import sys
sys.path.insert(0, ".")

import pandas as pd
import numpy as np

from tradingagents.yang_yin.pipeline import YangYinPipeline
from tradingagents.yang_yin.factors_v7 import compute_factors
from tradingagents.yang_yin.model_v7 import predict_yangpu

# 加载真实值
csv_path = r"D:\下载\_app_data_所有对话_主对话_yangpu_data_yangpu_comparison_v7 (1).csv"
ref = pd.read_csv(csv_path)
ref = ref.set_index("trade_date")
print(f"参考数据: {len(ref)} 天")

# 加载面板
pipeline = YangYinPipeline()
panel = pipeline.load_panel()
if panel is None:
    print("面板不存在，正在构建...")
    panel = pipeline.build_panel()

all_dates = sorted(panel["trade_date"].unique())
ref_dates = [d for d in ref.index if str(d) in all_dates]
print(f"面板日期范围: {all_dates[0]} ~ {all_dates[-1]}")
print(f"匹配参考日期: {len(ref_dates)} / {len(ref)}")

# ── 模式1: 用真实prev_yangpu（验证因子计算正确性）──
print("\n=== 模式1: 真实prev_yangpu ===")
results1 = []
for i, dt in enumerate(ref_dates):
    dt_str = str(dt)
    # 前一日真实值
    prev = None
    if i > 0:
        prev_dt = ref_dates[i - 1]
        prev = ref.loc[prev_dt, "actual"]
    else:
        prev = 50.0  # 首日中性值

    factors = compute_factors(panel, dt_str, prev_yangpu=prev)
    if factors is None:
        continue
    pred = predict_yangpu(factors)
    actual = ref.loc[dt, "actual"]
    results1.append({
        "trade_date": dt_str,
        "actual": actual,
        "predicted": round(pred, 6),
        "diff": round(pred - actual, 4),
        "abs_diff": abs(pred - actual),
    })

df1 = pd.DataFrame(results1)
if not df1.empty:
    mae1 = (df1["abs_diff"].mean())
    corr1 = df1["actual"].corr(df1["predicted"])
    pct5 = (df1["abs_diff"] <= 5).mean() * 100
    pct10 = (df1["abs_diff"] > 10).mean() * 100
    print(f"天数: {len(df1)}, MAE: {mae1:.2f}%, 相关系数: {corr1:.4f}")
    print(f"≤5%: {pct5:.0f}%, >10%: {pct10:.0f}%")
    # 对比CSV中的predicted列
    if "predicted" in ref.columns:
        csv_pred = ref.loc[df1["trade_date"].astype(int), "predicted"].values
        our_pred = df1["predicted"].values
        match = np.allclose(our_pred, csv_pred, atol=1e-4)
        print(f"与CSV预测值一致: {'YES' if match else 'NO'}")
        if not match:
            max_diff = np.abs(our_pred - csv_pred).max()
            print(f"  最大偏差: {max_diff:.6f}")

# ── 模式2: 预测值滚动（模拟实战）──
print("\n=== 模式2: 预测值滚动 ===")
results2 = []
prev_pred = 50.0
for dt in ref_dates:
    dt_str = str(dt)
    factors = compute_factors(panel, dt_str, prev_yangpu=prev_pred)
    if factors is None:
        continue
    pred = predict_yangpu(factors)
    actual = ref.loc[dt, "actual"]
    results2.append({
        "trade_date": dt_str,
        "actual": actual,
        "predicted": round(pred, 2),
        "diff": round(pred - actual, 2),
        "abs_diff": abs(pred - actual),
    })
    prev_pred = pred

df2 = pd.DataFrame(results2)
if not df2.empty:
    mae2 = df2["abs_diff"].mean()
    corr2 = df2["actual"].corr(df2["predicted"])
    pct5_2 = (df2["abs_diff"] <= 5).mean() * 100
    pct10_2 = (df2["abs_diff"] > 10).mean() * 100
    print(f"天数: {len(df2)}, MAE: {mae2:.2f}%, 相关系数: {corr2:.4f}")
    print(f"≤5%: {pct5_2:.0f}%, >10%: {pct10_2:.0f}%")

# ── 最近14天详细对比 ──
print("\n=== 最近14天 同花顺 vs v0.7预测 ===")
recent = df2.tail(14).copy() if not df2.empty else None
if recent is not None:
    for _, row in recent.iterrows():
        bar = "█" * max(0, int(row["actual"] / 2))
        bar_pred = "▓" * max(0, int(row["predicted"] / 2))
        print(f"{row['trade_date']}  同花顺:{row['actual']:5.1f}% {bar}")
        print(f"           预测:{row['predicted']:5.1f}% {bar_pred}")
        print(f"           误差:{row['diff']:+.1f}%")
        print()

print("Done.")
