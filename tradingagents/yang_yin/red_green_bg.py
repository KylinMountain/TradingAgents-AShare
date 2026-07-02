"""红绿背景（中期趋势）v2.1 — 上证GS信号 + 阳谱门槛

规则:
  🟢→🔴: GS=G 且 阳谱>40
  🔴→🟢: GS=S 零延迟
准确率: 92.3% (110天确认期)
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

YANG_THRESHOLD = 40
INDEX_CODE = "000001.SH"
BG_STATE_FILE = "bg_state.json"


def _get_tushare_pro():
    import tushare as ts
    token = os.environ.get("TUSHARE_TOKEN", "23651a8611b00bf491c7378d81d0bc6265543153530194be989e6ada")
    ts.set_token(token)
    return ts.pro_api()


def fetch_index_kline(days: int = 120) -> pd.DataFrame:
    """拉取上证指数 000001.SH 日K线，多源回退 + 当日Sina实时快照

    数据源优先级: Tushare → Tencent(AkShare) → Eastmoney(AkShare)
    然后尝试追加当日Sina实时行情
    """
    import urllib.request
    import re

    end_str = datetime.now().strftime("%Y%m%d")
    start_str = (datetime.now() - timedelta(days=days + 60)).strftime("%Y%m%d")

    raw = None
    last_exc = None

    # 1) Tushare
    try:
        pro = _get_tushare_pro()
        raw = pro.index_daily(ts_code=INDEX_CODE, start_date=start_str, end_date=end_str)
        if raw is not None and not raw.empty:
            raw = raw.rename(columns={"trade_date": "date", "vol": "volume"})
    except Exception as exc:
        last_exc = exc

    # 2) Tencent (akshare)
    if raw is None or raw.empty:
        try:
            import akshare as ak
            raw = ak.stock_zh_a_hist_tx(symbol="sh000001", start_date=start_str, end_date=end_str, adjust="qfq")
            if raw is not None and not raw.empty:
                raw = raw.rename(columns={"日期": "date", "开盘": "open", "收盘": "close",
                                          "最高": "high", "最低": "low", "成交量": "volume"})
        except Exception as exc:
            last_exc = exc

    # 3) Eastmoney (akshare)
    if raw is None or raw.empty:
        try:
            import akshare as ak
            raw = ak.stock_zh_index_daily_em(symbol="sh000001", start_date=start_str, end_date=end_str)
            if raw is not None and not raw.empty:
                raw = raw.rename(columns={"date": "date", "open": "open", "close": "close",
                                          "high": "high", "low": "low", "volume": "volume"})
        except Exception as exc:
            last_exc = exc

    if raw is None or raw.empty:
        raise RuntimeError(f"无法获取上证指数K线数据 (all sources failed): {last_exc}")

    raw["date"] = pd.to_datetime(raw["date"])
    df = raw.sort_values("date").reset_index(drop=True)

    # 4) 追加当日Sina实时快照
    now = datetime.now()
    today = pd.Timestamp(now.date())
    if today not in df["date"].dt.normalize().values:
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        if now >= market_open:
            try:
                req = urllib.request.Request(
                    "http://hq.sinajs.cn/list=sh000001",
                    headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    body = resp.read().decode("gbk")
                m = re.search(r'hq_str_sh000001="(.+)"', body)
                if m:
                    parts = m.group(1).split(",")
                    if len(parts) >= 32 and float(parts[3]) > 0:
                        row = pd.DataFrame([{
                            "date": today,
                            "open": float(parts[1]),
                            "high": float(parts[4]),
                            "low": float(parts[5]),
                            "close": float(parts[3]),
                            "volume": float(parts[8]) / 100,
                        }])
                        df = pd.concat([df, row], ignore_index=True).sort_values("date").reset_index(drop=True)
            except Exception:
                pass

    return df


def compute_gs(df: pd.DataFrame) -> pd.DataFrame:
    """计算GS策略信号 — 复用 niuxiong_line 统一实现

    Parameters
    ----------
    df : pd.DataFrame
        包含 open, high, low, close 列的K线数据，按日期升序

    Returns
    -------
    pd.DataFrame
        添加 a_line, bb_line, gs_signal 列 (G=红/S=绿)
    """
    from tradingagents.indicators.niuxiong_line import calculate_gs_strategy

    result = calculate_gs_strategy(df)
    result = result.rename(columns={"gs_a": "a_line", "gs_bb": "bb_line"})
    result["gs_signal"] = np.where(result["gs_k"], "G", "S")
    return result


def compute_background(
    gs_df: pd.DataFrame,
    yang_hist: pd.DataFrame,
    threshold: int = YANG_THRESHOLD,
) -> pd.DataFrame:
    """根据v2.1规则计算红绿背景序列

    翻红: GS=G 且 阳>threshold
    翻绿: GS=S (零延迟)

    Parameters
    ----------
    gs_df : DataFrame with date, gs_signal columns
    yang_hist : DataFrame with trade_date, yang_pct columns
    threshold : 阳谱翻红门槛 (默认40)

    Returns
    -------
    DataFrame with date, background, gs_signal, a_line, bb_line
    """
    gs = gs_df[["date", "gs_signal", "a_line", "bb_line"]].copy()
    gs["trade_date"] = gs["date"].dt.strftime("%Y%m%d")

    # Merge with yang history
    yang = yang_hist[["trade_date", "yang_pct"]].copy()
    merged = gs.merge(yang, on="trade_date", how="left")

    backgrounds = []
    current_bg = None

    for _, row in merged.iterrows():
        gs_sig = row["gs_signal"]
        yang_pct = row["yang_pct"]

        if current_bg is None:
            # 初始化: 第一天GS=G 且 阳>阈值 → 红, 否则绿
            if gs_sig == "G" and pd.notna(yang_pct) and yang_pct > threshold:
                current_bg = "红"
            else:
                current_bg = "绿"

        # 翻转判定
        if current_bg == "绿" and gs_sig == "G" and pd.notna(yang_pct) and yang_pct > threshold:
            current_bg = "红"
        elif current_bg == "红" and gs_sig == "S":
            current_bg = "绿"

        backgrounds.append(current_bg)

    merged["background"] = backgrounds
    return merged[["trade_date", "background", "gs_signal", "a_line", "bb_line"]]


def generate_history(pipeline, days: int = 200) -> pd.DataFrame:
    """全量回填红绿背景历史

    Parameters
    ----------
    pipeline : YangYinPipeline
    days : 拉取K线天数

    Returns
    -------
    DataFrame with trade_date, background, gs_signal, a_line, bb_line
    """
    from .aggregation import load_history

    kline = fetch_index_kline(days=days)
    gs = compute_gs(kline)
    yang_hist = load_history(pipeline)
    bg = compute_background(gs, yang_hist)
    return bg


def _bg_state_path(pipeline) -> str:
    from pathlib import Path
    summary_dir = pipeline.summary_dir if hasattr(pipeline, 'summary_dir') else pipeline.cache_dir
    return os.path.join(summary_dir, BG_STATE_FILE)


def load_bg_state(pipeline) -> Optional[dict]:
    """加载bg_state.json"""
    path = _bg_state_path(pipeline)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bg_state(state: dict, pipeline) -> None:
    """持久化bg_state.json"""
    path = _bg_state_path(pipeline)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def update_bg_state(kline_df: pd.DataFrame, yang_hist: pd.DataFrame, pipeline, trade_date: str) -> dict:
    """更新并持久化红绿背景状态（14点后新交易日才持久化）

    Returns current state dict with background, a_line, bb_line
    """
    gs = compute_gs(kline_df)
    bg = compute_background(gs, yang_hist)

    latest = bg[bg["trade_date"] == trade_date]
    if latest.empty:
        logger.warning(f"红绿背景: {trade_date} 无数据")
        return {"background": "绿", "a_line": 0, "bb_line": 0, "trade_date": trade_date}

    row = latest.iloc[-1]
    state = {
        "version": "v2.1",
        "last_date": int(trade_date),
        "A": round(float(row["a_line"]), 6),
        "BB": round(float(row["bb_line"]), 6),
        "background": row["background"],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # 仅14点后且新交易日才持久化（避免盘中A/BB双重推进）
    now = datetime.now()
    prev = load_bg_state(pipeline)
    is_new_day = prev is None or prev.get("last_date") != int(trade_date)
    if now.hour >= 14 and is_new_day:
        # 获取prev_A/prev_BB
        if prev and prev.get("last_date") == int(trade_date) - 1:
            state["prev_A"] = prev.get("A")
            state["prev_BB"] = prev.get("BB")
        save_bg_state(state, pipeline)
        logger.info(f"红绿背景持久化: {trade_date} → {state['background']}")

    return state


def get_history(pipeline, days: int = 30) -> list[dict]:
    """获取红绿背景历史（供API调用）"""
    from .aggregation import load_history

    kline = fetch_index_kline(days=max(days + 30, 120))
    gs = compute_gs(kline)
    yang_hist = load_history(pipeline)
    bg = compute_background(gs, yang_hist)

    if bg.empty:
        return []

    result = bg.sort_values("trade_date").tail(days)
    return result.to_dict(orient="records")
