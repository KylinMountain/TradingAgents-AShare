"""
市场状态判断模块

基于上证指数(000001.SH)牛线(EMA99)的二元分类：
- 收盘 > 牛线 → 牛市
- 收盘 < 牛线 → 熊市

牛线 = EMA(X1, 99), X1 = (H+L+O+2C)/5
"""

import os
import numpy as np
import pandas as pd


def calculate_bull_line(df: pd.DataFrame) -> pd.Series:
    """
    计算牛线 EMA(X1, 99)

    Parameters
    ----------
    df : pd.DataFrame
        包含 open, high, low, close 的 DataFrame

    Returns
    -------
    pd.Series
        牛线值
    """
    x1 = (df["high"] + df["low"] + df["open"] + 2 * df["close"]) / 5
    return x1.ewm(span=99, adjust=False).mean()


def classify_market_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    对上证指数日K数据做市场状态分类

    Parameters
    ----------
    df : pd.DataFrame
        上证指数日K，需含 open, high, low, close 列，DatetimeIndex

    Returns
    -------
    pd.DataFrame
        添加了 bull_line, market_state 列的 DataFrame
    """
    result = df.copy()
    result["bull_line"] = calculate_bull_line(result)
    result["market_state"] = np.where(
        result["close"] > result["bull_line"], "牛市", "熊市"
    )
    return result


def fetch_sh_index_data(start_date: str = "20150101", end_date: str = None) -> pd.DataFrame:
    """
    获取上证指数历史日K数据 (Tushare)

    Parameters
    ----------
    start_date : str
        起始日期 YYYYMMDD
    end_date : str
        结束日期 YYYYMMDD，默认为今天

    Returns
    -------
    pd.DataFrame
        上证指数日K，DatetimeIndex
    """
    if end_date is None:
        from datetime import datetime
        end_date = datetime.now().strftime("%Y%m%d")

    token = os.environ.get("TUSHARE_TOKEN",
                           "23651a8611b00bf491c7378d81d0bc6265543153530194be989e6ada")
    import tushare as ts
    ts.set_token(token)
    pro = ts.pro_api()

    raw = pro.index_daily(ts_code="000001.SH", start_date=start_date, end_date=end_date)
    if raw is None or raw.empty:
        raise RuntimeError("无法获取上证指数数据，请检查Tushare连接")

    raw["trade_date"] = pd.to_datetime(raw["trade_date"], format="%Y%m%d")
    raw = raw.set_index("trade_date").sort_index()
    return raw[["open", "high", "low", "close"]]


def get_current_market_state(df: pd.DataFrame) -> dict:
    """
    获取最新一天的市场状态

    Parameters
    ----------
    df : pd.DataFrame
        classify_market_state 返回的 DataFrame

    Returns
    -------
    dict
        包含 date, close, bull_line, state 的字典
    """
    latest = df.iloc[-1]
    return {
        "date": str(df.index[-1].date()),
        "close": round(float(latest["close"]), 2),
        "bull_line": round(float(latest["bull_line"]), 2),
        "state": latest["market_state"],
        "above_pct": round(
            (latest["close"] - latest["bull_line"]) / latest["bull_line"] * 100, 2
        ),
    }
