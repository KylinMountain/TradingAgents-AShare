"""
同花顺牛熊线高阶指标 Python 实现
基于通达信公式源码转换 (TDX原版)

公式源码:
  X1:=(H+L+O+2*C)/5;
  决策线:EMA(X1,39);
  牛线:EMA(X1,99);
  熊线:IF(牛线>决策线,牛线,DRAWNULL);
  SG1:=EMA(H,5); XG1:=EMA(L,5);
  轨道线: 自适应 EMA(H,5) / EMA(L,5) (根据交叉方向切换)

指标组成:
- 决策线 (黄色虚线): EMA(X1, 39), X1=(H+L+O+2C)/5
- 牛线 (红色虚线): EMA(X1, 99)
- 熊线 (绿色虚线): 当牛线>决策线时显示牛线值
- 轨道线 (青色实线): EMA(H,5) 和 EMA(L,5) 的自适应切换

功能:
- 实时数据接入 (mootdx/腾讯财经)
- 买卖信号标记
- 多指标联动 (MACD/KDJ/RSI)
"""

import re
import os
import time
import threading
import pandas as pd
import numpy as np
from typing import Optional

# ---------- TTL 内存缓存 ----------
_kline_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_kline_cache_lock = threading.Lock()
_KLINE_CACHE_TTL = 60  # 秒

_quote_cache: dict[str, tuple[float, dict]] = {}
_quote_cache_lock = threading.Lock()
_QUOTE_CACHE_TTL = 30  # 秒


def _get_cached_kline(key: str) -> pd.DataFrame | None:
    with _kline_cache_lock:
        entry = _kline_cache.get(key)
        if entry and time.monotonic() - entry[0] < _KLINE_CACHE_TTL:
            return entry[1].copy()
        _kline_cache.pop(key, None)
    return None


def _set_cached_kline(key: str, df: pd.DataFrame) -> None:
    with _kline_cache_lock:
        _kline_cache[key] = (time.monotonic(), df.copy())
        # 清理过期条目，防止内存泄漏
        if len(_kline_cache) > 200:
            now = time.monotonic()
            expired = [k for k, (t, _) in _kline_cache.items() if now - t >= _KLINE_CACHE_TTL]
            for k in expired:
                _kline_cache.pop(k, None)


def _get_cached_quote(key: str) -> dict | None:
    with _quote_cache_lock:
        entry = _quote_cache.get(key)
        if entry and time.monotonic() - entry[0] < _QUOTE_CACHE_TTL:
            return dict(entry[1])
        _quote_cache.pop(key, None)
    return None


def _set_cached_quote(key: str, data: dict) -> None:
    with _quote_cache_lock:
        _quote_cache[key] = (time.monotonic(), dict(data))
        if len(_quote_cache) > 200:
            now = time.monotonic()
            expired = [k for k, (t, _) in _quote_cache.items() if now - t >= _QUOTE_CACHE_TTL]
            for k in expired:
                _quote_cache.pop(k, None)


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=period, adjust=False).mean()


def fetch_realtime_data(symbol: str, days: int = 120, period: str = "daily") -> pd.DataFrame:
    """
    获取A股历史K线数据 (前复权，Eastmoney → Sina → Tencent 三级回退)

    Parameters
    ----------
    symbol : str
        股票代码，如 '000001', '600519'
    days : int
        获取的历史天数
    period : str
        K线周期: "daily", "weekly", "monthly"

    Returns
    -------
    pd.DataFrame
        OHLCV 数据，日期索引，前复权价格
    """
    import akshare as ak
    from datetime import datetime, timedelta

    # 检查缓存（key 包含原始 symbol，因为 suffix 影响数据源选择）
    cache_key = f"{symbol}:{days}:{period}"
    cached = _get_cached_kline(cache_key)
    if cached is not None:
        return cached

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days + 150)).strftime("%Y%m%d")

    # 处理带后缀的代码：000001.SH → 000001, 市场前缀由后缀决定
    exchange = None
    if symbol.upper().endswith(".SH"):
        exchange = "sh"
        symbol = symbol[:-3]
    elif symbol.upper().endswith(".SZ"):
        exchange = "sz"
        symbol = symbol[:-3]
    elif symbol.upper().endswith(".BJ"):
        exchange = "bj"
        symbol = symbol[:-3]

    def _market_prefix(s):
        if exchange:
            return exchange
        return "sh" if s.startswith(("5", "6", "9")) else "sz"

    df = None
    last_exc = None

    # 构建 tushare ts_code
    _INDEX_CODES = {"000001", "399001", "399006", "000300", "000688", "000905", "000852", "899050"}
    is_index = symbol in _INDEX_CODES
    ts_suffix = f".{exchange.upper()}" if exchange else (".SH" if symbol.startswith(("5", "6", "9")) else ".SZ")
    ts_code = symbol + ts_suffix

    # 优先级: Tushare(最快) → AkShare 各源
    def _fetch_tushare():
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN", "23651a8611b00bf491c7378d81d0bc6265543153530194be989e6ada")
        ts.set_token(token)
        pro = ts.pro_api()
        if is_index:
            raw = pro.index_daily(ts_code=ts_code, start_date=start, end_date=end)
        else:
            # 个股用 pro_bar 获取前复权数据，pro.daily 返回的是未复权
            raw = ts.pro_bar(ts_code=ts_code, adj='qfq', start_date=start, end_date=end)
        if raw is None or raw.empty:
            return None
        raw = raw.rename(columns={"trade_date": "date", "vol": "volume"})
        raw["date"] = pd.to_datetime(raw["date"], format="%Y%m%d")
        raw = raw.set_index("date").sort_index()
        # 个股: daily_basic 补充换手率
        # Tushare返回百分比(0.2504=0.25%)，后端*100转百分比，所以这里除以100对齐
        if not is_index:
            try:
                basic = pro.daily_basic(ts_code=ts_code, start_date=start, end_date=end,
                                        fields="trade_date,turnover_rate")
                if basic is not None and not basic.empty:
                    basic["date"] = pd.to_datetime(basic["trade_date"], format="%Y%m%d")
                    basic = basic.set_index("date")
                    raw["turnover_rate"] = basic["turnover_rate"] / 100
            except Exception:
                pass
        return raw

    sources: list[tuple[str, callable]] = [("tushare", _fetch_tushare)]

    if is_index:
        vendor = f"{_market_prefix(symbol)}{symbol}"
        sources += [
            ("tencent_index", lambda: ak.stock_zh_a_hist_tx(symbol=vendor, start_date=start, end_date=end, adjust="qfq")),
            ("eastmoney_index", lambda: ak.stock_zh_index_daily_em(symbol=vendor, start_date=start, end_date=end)),
        ]
    else:
        sources += [
            ("eastmoney", lambda: ak.stock_zh_a_hist(symbol=symbol, period=period, start_date=start, end_date=end, adjust="qfq")),
            ("sina", lambda: ak.stock_zh_a_daily(symbol=f"{_market_prefix(symbol)}{symbol}", start_date=start, end_date=end, adjust="qfq")),
            ("tencent", lambda: ak.stock_zh_a_hist_tx(symbol=f"{_market_prefix(symbol)}{symbol}", start_date=start, end_date=end, adjust="qfq")),
        ]

    used_source = None
    for source_name, fetcher in sources:
        try:
            df = fetcher()
            if df is not None and not df.empty:
                used_source = source_name
                break
        except Exception as exc:
            last_exc = exc
            continue

    if df is None or df.empty:
        raise ValueError(f"未获取到 {symbol} 的K线数据 (all sources failed): {last_exc}")

    # Tushare 已返回标准格式，跳过后处理
    if used_source != "tushare":
        col_map = {"日期": "date", "开盘": "open", "收盘": "close",
                    "最高": "high", "最低": "low", "成交量": "volume",
                    "成交额": "amount", "换手率": "turnover_rate",
                    "涨跌幅": "pct_chg", "涨跌额": "change",
                    "turnover": "turnover_rate"}
        df = df.rename(columns=col_map)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

    keep_cols = [c for c in ["open", "close", "high", "low", "volume", "amount", "turnover_rate", "pre_close", "change", "pct_chg"] if c in df.columns]
    df = df[keep_cols]

    # 尝试追加当天实时行情
    df = _try_append_today_row(symbol, df, exchange=exchange)

    # 日线直接返回 days 行
    if period == "daily":
        result = df.tail(days)
        _set_cached_kline(cache_key, result)
        return result
    # 周线/月线返回更多数据确保聚合后点数足够（周线约5天/周，月线约22天/月）
    extra_factor = 6 if period == "weekly" else 25
    result = df.tail(days * extra_factor)
    _set_cached_kline(cache_key, result)
    return result


def _try_append_today_row(symbol: str, df: pd.DataFrame, exchange: str | None = None) -> pd.DataFrame:
    """尝试追加当天实时行情（Sina API）"""
    import urllib.request
    from datetime import datetime

    now = datetime.now()
    today = pd.Timestamp(now.date())
    if today in df.index.normalize():
        return df

    # 盘前（9:30前）不追加今日行，Sina会返回close=0导致画出异常K线
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now < market_open:
        return df

    if exchange:
        prefix = exchange
    else:
        prefix = "sh" if symbol.startswith(("5", "6", "9")) else "sz" if symbol.startswith(("0", "3", "2")) else "bj" if symbol.startswith(("4", "8")) else None
    if not prefix:
        return df
    sina_code = f"{prefix}{symbol}"

    try:
        req = urllib.request.Request(
            f"http://hq.sinajs.cn/list={sina_code}",
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("gbk")
    except Exception:
        return df

    m = re.search(r'hq_str_\w+="(.+)"', raw)
    if not m:
        return df
    parts = m.group(1).split(",")
    if len(parts) < 32:
        return df

    try:
        date_val = pd.to_datetime(parts[30], errors="coerce")
        if pd.isna(date_val):
            date_val = today
        close_val = float(parts[3])
        prev_close = float(parts[2])  # 昨收
        change = round(close_val - prev_close, 4)
        pct_chg = round(change / prev_close * 100, 4) if prev_close else None
        amount_val = float(parts[9]) if len(parts) > 9 and parts[9] else 0.0
        row = pd.DataFrame([{
            "open": float(parts[1]),
            "high": float(parts[4]),
            "low": float(parts[5]),
            "close": close_val,
            "volume": float(parts[8]) / 100,  # Sina返回股→手，对齐tushare/akshare
            "amount": amount_val,              # Sina返回元，对齐akshare amount单位
            "pre_close": prev_close,
            "change": change,
            "pct_chg": pct_chg,
        }], index=[pd.Timestamp(date_val).normalize()])
    except (ValueError, IndexError):
        return df

    if row.index[0] != today:
        return df

    return pd.concat([df, row]).sort_index()


def fetch_realtime_quote(symbol: str) -> dict:
    """
    获取股票实时行情 (使用腾讯财经API，不封IP)

    Parameters
    ----------
    symbol : str
        股票代码，支持带后缀 (000001.SH) 或不带 (000001)

    Returns
    -------
    dict
        实时行情数据
    """
    # 检查缓存
    cached = _get_cached_quote(symbol)
    if cached is not None:
        return cached

    import urllib.request

    # 保留后缀判断市场
    if symbol.endswith(".SH") or symbol.endswith(".sh"):
        code = f"sh{symbol[:-3]}"
    elif symbol.endswith(".SZ") or symbol.endswith(".sz"):
        code = f"sz{symbol[:-3]}"
    elif symbol.endswith(".BJ") or symbol.endswith(".bj"):
        code = f"bj{symbol[:-3]}"
    elif symbol.startswith(("6", "9")):
        code = f"sh{symbol}"
    elif symbol.startswith("8"):
        code = f"bj{symbol}"
    else:
        code = f"sz{symbol}"

    url = f"https://qt.gtimg.cn/q={code}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")

    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue

        result = {
            "symbol": symbol,
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "prev_close": float(vals[4]) if vals[4] else 0,
            "open": float(vals[5]) if vals[5] else 0,
            "change_amt": float(vals[31]) if vals[31] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "volume": float(vals[36]) if vals[36] else 0,
            "amount": float(vals[37]) if vals[37] else 0,
            "turnover": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "time": vals[30] if len(vals) > 30 and vals[30] else "",
        }
        _set_cached_quote(symbol, result)
        return result

    return {"error": f"未找到股票 {symbol}"}


def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """计算MACD指标"""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    macd = 2 * (dif - dea)
    return pd.DataFrame({'dif': dif, 'dea': dea, 'macd': macd})


def calculate_kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9) -> pd.DataFrame:
    """计算KDJ指标"""
    lowest_low = low.rolling(n).min()
    highest_high = high.rolling(n).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    return pd.DataFrame({'k': k, 'd': d, 'j': j})


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """计算RSI指标"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_niuxiong_line(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算同花顺牛熊线高阶指标 (匹配同花顺原版)

    Parameters
    ----------
    df : pd.DataFrame
        包含 OHLCV 数据的 DataFrame，必须包含 'close', 'high', 'low' 列

    Returns
    -------
    pd.DataFrame
        添加了牛熊线指标列的 DataFrame
    """
    result = df.copy()
    close = result['close']
    high = result['high']
    low = result['low']

    # 确保 volume 是 Series
    if 'volume' in result.columns:
        vol = result['volume']
        if isinstance(vol, pd.DataFrame):
            result['volume'] = vol.iloc[:, 0]

    # === 加权价 X1 = (H+L+O+2*C)/5 (同花顺原版) ===
    x1 = (high + low + result['open'] + 2 * close) / 5

    # === 决策线 (黄色虚线) - EMA(X1, 39) ===
    result['decision_line'] = ema(x1, 39)

    # === 牛线/熊线 (红色/绿色虚线) - EMA(X1, 99) ===
    bull = ema(x1, 99)
    # 熊线: 当牛线 > 决策线时显示牛线值，否则为空
    bear = bull.where(bull > result['decision_line'], np.nan)

    result['bear_line'] = bear  # 牛线(显示为熊线名，兼容前端)

    # === 轨道线 (青色实线) ===
    # 上轨: EMA(H, 5), 下轨: EMA(L, 5)
    # 自适应: 根据最近一次交叉决定显示上轨还是下轨
    sg1 = ema(high, 5)   # 上轨
    xg1 = ema(low, 5)    # 下轨

    # 判断方向: CS=上次close上穿上轨距今天数, CX=上次close下穿下轨距今天数
    # CROSS(close, sg1): close从下往上穿过sg1 (上穿)
    cross_up = (close > sg1) & (close.shift(1) <= sg1.shift(1))
    # CROSS(xg1, close): xg1从下往上穿过close = close从上往下穿过xg1 (下穿)
    cross_dn = (xg1 > close) & (xg1.shift(1) <= close.shift(1))

    # 用向量化方式计算方向
    cs = pd.Series(np.nan, index=df.index)
    cx = pd.Series(np.nan, index=df.index)
    last_cross_up = np.nan
    last_cross_dn = np.nan
    for i in range(len(df)):
        if cross_up.iloc[i]:
            last_cross_up = 0
        if cross_dn.iloc[i]:
            last_cross_dn = 0
        if not np.isnan(last_cross_up):
            cs.iloc[i] = last_cross_up
            last_cross_up += 1
        if not np.isnan(last_cross_dn):
            cx.iloc[i] = last_cross_dn
            last_cross_dn += 1

    # DQZT: 1=上穿(看多), -1=下穿(看空), 0=未定
    dqzt = pd.Series(0, index=df.index)
    valid = cs.notna() & cx.notna()
    dqzt[valid] = np.where(cs[valid] < cx[valid], 1, np.where(cx[valid] < cs[valid], -1, 0))
    dqzt[cs.notna() & cx.isna()] = 1
    dqzt[cx.notna() & cs.isna()] = -1

    # 轨道线: DQZT<0时显示上轨(SG1), 否则显示下轨(XG1)
    orbit = pd.Series(np.nan, index=df.index)
    orbit[dqzt < 0] = sg1[dqzt < 0]
    orbit[dqzt >= 0] = xg1[dqzt >= 0]

    result['orbit_line'] = orbit
    result['orbit_direction'] = dqzt  # 1=多头, -1=空头, 0=未定
    result['bull_line'] = bull  # 完整的EMA(X1,99)，始终有值

    # === 趋势判断 ===
    result['short_trend_up'] = result['decision_line'] > result['decision_line'].shift(1)
    result['long_trend_up'] = bull > bull.shift(1)

    # === 综合信号 ===
    result['bullish_alignment'] = result['short_trend_up'] & result['long_trend_up']
    result['bearish_alignment'] = (~result['short_trend_up']) & (~result['long_trend_up'])

    # === 买卖信号 ===
    result['buy_signal'] = generate_buy_signal(result)
    result['sell_signal'] = generate_sell_signal(result)

    return result


def generate_buy_signal(df: pd.DataFrame) -> pd.Series:
    """
    生成买入信号

    买入条件:
    1. 价格从下方站上轨道线
    2. 决策线金叉牛线
    """
    signals = pd.Series(False, index=df.index)

    # 条件1: 价格从下方站上轨道线
    cross_orbit_up = (df['close'] > df['orbit_line']) & (df['close'].shift(1) <= df['orbit_line'].shift(1))

    # 条件2: 决策线上穿牛线
    golden_cross = (df['decision_line'] > df['bear_line']) & (df['decision_line'].shift(1) <= df['bear_line'].shift(1))

    signals = cross_orbit_up | golden_cross
    return signals


def generate_sell_signal(df: pd.DataFrame) -> pd.Series:
    """
    生成卖出信号

    卖出条件:
    1. 价格从上方跌破轨道线
    2. 决策线死叉牛线
    """
    signals = pd.Series(False, index=df.index)

    # 条件1: 价格从上方跌破轨道线
    cross_orbit_down = (df['close'] < df['orbit_line']) & (df['close'].shift(1) >= df['orbit_line'].shift(1))

    # 条件2: 决策线下穿牛线
    death_cross = (df['decision_line'] < df['bear_line']) & (df['decision_line'].shift(1) >= df['bear_line'].shift(1))

    signals = cross_orbit_down | death_cross
    return signals


def get_signal(df: pd.DataFrame) -> dict:
    """
    获取最新一天的牛熊线信号

    Parameters
    ----------
    df : pd.DataFrame
        包含牛熊线指标的 DataFrame (由 calculate_niuxiong_line 计算)

    Returns
    -------
    dict
        信号字典，包含趋势、支撑位、压力位等信息
    """
    if len(df) < 2:
        return {"error": "数据不足"}

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    signal = {
        "date": df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else len(df) - 1,

        # 核心指标
        "decision_line": round(float(latest['decision_line']), 2),
        "bear_line": round(float(latest['bear_line']), 2) if not pd.isna(latest['bear_line']) else None,
        "orbit_line": round(float(latest['orbit_line']), 2) if not pd.isna(latest['orbit_line']) else None,

        # 趋势
        "short_trend": "上涨" if latest['short_trend_up'] else "下跌",
        "long_trend": "上涨" if latest['long_trend_up'] else "下跌",

        # 综合信号
        "signal": {
            "bullish": bool(latest['bullish_alignment']),
            "bearish": bool(latest['bearish_alignment']),
            "status": "多头排列" if latest['bullish_alignment'] else
                      "空头排列" if latest['bearish_alignment'] else "震荡",
        },

        # 买卖信号
        "trading": {
            "buy": bool(latest['buy_signal']),
            "sell": bool(latest['sell_signal']),
            "recommendation": "买入" if latest['buy_signal'] else
                             "卖出" if latest['sell_signal'] else "持有",
        },
    }

    return signal


# 便捷函数
def niuxiong_analysis(df: pd.DataFrame) -> str:
    """
    一键分析牛熊线指标

    Parameters
    ----------
    df : pd.DataFrame
        包含 OHLCV 数据的 DataFrame

    Returns
    -------
    str
        格式化的分析报告
    """
    result = calculate_niuxiong_line(df)
    signal = get_signal(result)

    bear_val = f"{signal['bear_line']}" if signal['bear_line'] else "N/A (牛线<=决策线)"
    report = f"""=== 同花顺牛熊线高阶指标分析 ===

【核心指标】
  决策线 (EMA39): {signal['decision_line']}
  牛线 (EMA99):   {bear_val}
  轨道线:          {signal['orbit_line'] if signal['orbit_line'] else 'N/A'}

【趋势】
  短期趋势: {signal['short_trend']}
  长期趋势: {signal['long_trend']}

【综合信号】
  状态: {signal['signal']['status']}
  多头排列: {'是' if signal['signal']['bullish'] else '否'}
  空头排列: {'是' if signal['signal']['bearish'] else '否'}

【交易建议】
  买入信号: {'是' if signal['trading']['buy'] else '否'}
  卖出信号: {'是' if signal['trading']['sell'] else '否'}
  建议: {signal['trading']['recommendation']}
"""

    return report


def multi_indicator_analysis(df: pd.DataFrame) -> dict:
    """
    多指标联动分析

    Parameters
    ----------
    df : pd.DataFrame
        包含 OHLCV 数据的 DataFrame

    Returns
    -------
    dict
        包含牛熊线、MACD、KDJ、RSI 的综合分析
    """
    result = calculate_niuxiong_line(df)
    signal = get_signal(result)

    # 计算其他指标
    macd = calculate_macd(df['close'])
    kdj = calculate_kdj(df['high'], df['low'], df['close'])
    rsi = calculate_rsi(df['close'])

    latest_idx = -1
    analysis = {
        "date": signal['date'],
        "niuxiong": signal,
        "macd": {
            "dif": round(macd['dif'].iloc[latest_idx], 2),
            "dea": round(macd['dea'].iloc[latest_idx], 2),
            "macd": round(macd['macd'].iloc[latest_idx], 2),
            "signal": "金叉" if macd['dif'].iloc[latest_idx] > macd['dea'].iloc[latest_idx] else "死叉",
        },
        "kdj": {
            "k": round(kdj['k'].iloc[latest_idx], 2),
            "d": round(kdj['d'].iloc[latest_idx], 2),
            "j": round(kdj['j'].iloc[latest_idx], 2),
            "signal": "超买" if kdj['j'].iloc[latest_idx] > 80 else
                     "超卖" if kdj['j'].iloc[latest_idx] < 20 else "中性",
        },
        "rsi": {
            "value": round(rsi.iloc[latest_idx], 2),
            "signal": "超买" if rsi.iloc[latest_idx] > 70 else
                     "超卖" if rsi.iloc[latest_idx] < 30 else "中性",
        },
    }

    # 综合建议
    buy_signals = 0
    sell_signals = 0

    if analysis['niuxiong']['trading']['buy']:
        buy_signals += 2
    if analysis['niuxiong']['trading']['sell']:
        sell_signals += 2
    if analysis['macd']['signal'] == '金叉':
        buy_signals += 1
    elif analysis['macd']['signal'] == '死叉':
        sell_signals += 1
    if analysis['kdj']['signal'] == '超卖':
        buy_signals += 1
    elif analysis['kdj']['signal'] == '超买':
        sell_signals += 1
    if analysis['rsi']['signal'] == '超卖':
        buy_signals += 1
    elif analysis['rsi']['signal'] == '超买':
        sell_signals += 1

    analysis['recommendation'] = {
        "buy_score": buy_signals,
        "sell_score": sell_signals,
        "action": "强烈买入" if buy_signals >= 4 else
                 "买入" if buy_signals >= 2 else
                 "强烈卖出" if sell_signals >= 4 else
                 "卖出" if sell_signals >= 2 else "观望",
    }

    return analysis


def format_analysis_report(analysis: dict) -> str:
    """
    格式化多指标分析报告

    Parameters
    ----------
    analysis : dict
        multi_indicator_analysis 返回的分析结果

    Returns
    -------
    str
        格式化的报告文本
    """
    nx = analysis['niuxiong']
    bear_val = f"{nx['bear_line']}" if nx.get('bear_line') else "N/A"
    report = f"""=== 多指标联动分析报告 ===
日期: {analysis['date']}

【牛熊线指标】
  状态: {nx['signal']['status']}
  短期趋势: {nx['short_trend']}
  长期趋势: {nx['long_trend']}
  决策线: {nx['decision_line']}
  牛线: {bear_val}
  轨道线: {nx['orbit_line'] if nx.get('orbit_line') else 'N/A'}
  交易建议: {nx['trading']['recommendation']}

【MACD】
  DIF: {analysis['macd']['dif']}
  DEA: {analysis['macd']['dea']}
  MACD: {analysis['macd']['macd']}
  信号: {analysis['macd']['signal']}

【KDJ】
  K: {analysis['kdj']['k']}
  D: {analysis['kdj']['d']}
  J: {analysis['kdj']['j']}
  信号: {analysis['kdj']['signal']}

【RSI】
  数值: {analysis['rsi']['value']}
  信号: {analysis['rsi']['signal']}

【综合建议】
  买入评分: {analysis['recommendation']['buy_score']}
  卖出评分: {analysis['recommendation']['sell_score']}
  操作建议: {analysis['recommendation']['action']}
"""

    return report


def plot_niuxiong_line(
    df: pd.DataFrame,
    title: str = "同花顺牛熊线高阶指标",
    figsize: tuple = (14, 8),
    save_path: str = None,
    show_signals: bool = True,
    show_volume: bool = True,
    show_macd: bool = False,
) -> None:
    """
    绘制牛熊线指标图表 (匹配同花顺原版风格)

    Parameters
    ----------
    df : pd.DataFrame
        包含 OHLCV 数据的 DataFrame
    title : str
        图表标题
    figsize : tuple
        图表尺寸
    save_path : str
        保存路径，为 None 则显示图表
    show_signals : bool
        是否显示买卖信号标记
    show_volume : bool
        是否显示成交量副图
    show_macd : bool
        是否显示MACD副图
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Patch

    # 计算指标
    result = calculate_niuxiong_line(df)

    # 设置子图数量
    n_subplots = 1 + (1 if show_volume else 0) + (1 if show_macd else 0)
    height_ratios = [4]
    if show_volume:
        height_ratios.append(1)
    if show_macd:
        height_ratios.append(1)

    fig, axes = plt.subplots(n_subplots, 1, figsize=figsize,
                             height_ratios=height_ratios,
                             gridspec_kw={'hspace': 0.08})

    if n_subplots == 1:
        axes = [axes]

    ax_idx = 0
    ax1 = axes[ax_idx]  # 主图
    ax_idx += 1

    # 设置深色背景 (匹配同花顺)
    fig.patch.set_facecolor('#1a1a2e')
    ax1.set_facecolor('#0d1117')

    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    dates = result.index

    # === 主图: K线 + 牛熊线轨道 ===

    # 绘制K线
    width = 0.6
    width2 = 0.05
    up = result['close'] >= result['open']
    down = ~up

    # 上涨K线 (红色空心)
    ax1.bar(dates[up], result['close'][up] - result['open'][up],
            width, bottom=result['open'][up], color='red', edgecolor='red', linewidth=0.5)
    ax1.bar(dates[up], result['high'][up] - result['close'][up],
            width2, bottom=result['close'][up], color='red', linewidth=0.5)
    ax1.bar(dates[up], result['low'][up] - result['open'][up],
            width2, bottom=result['open'][up], color='red', linewidth=0.5)

    # 下跌K线 (绿色实心)
    ax1.bar(dates[down], result['close'][down] - result['open'][down],
            width, bottom=result['open'][down], color='green', edgecolor='green', linewidth=0.5)
    ax1.bar(dates[down], result['high'][down] - result['open'][down],
            width2, bottom=result['open'][down], color='green', linewidth=0.5)
    ax1.bar(dates[down], result['low'][down] - result['close'][down],
            width2, bottom=result['close'][down], color='green', linewidth=0.5)

    # 决策线 (黄色虚线)
    ax1.plot(dates, result['decision_line'], color='#FFD700', linestyle='--',
             linewidth=1.2, label='决策线', zorder=6)

    # 熊线 (绿色虚线)
    ax1.plot(dates, result['bear_line'], color='#00FF00', linestyle='--',
             linewidth=1.2, label='熊线', zorder=6)

    # 轨道线 (青色实线)
    ax1.plot(dates, result['orbit_line'], color='#00CED1', linestyle='-',
             linewidth=1.5, label='轨道线', zorder=7)


    # === 买卖信号标记 ===
    if show_signals:
        buy_signals = result[result['buy_signal']]
        sell_signals = result[result['sell_signal']]

        if not buy_signals.empty:
            # 红色圆圈 B (匹配同花顺)
            ax1.scatter(buy_signals.index, buy_signals['close'] * 0.98,
                       marker='o', color='red', s=80, zorder=10,
                       edgecolors='yellow', linewidths=1.5)
            for idx in buy_signals.index:
                ax1.annotate('B', (idx, buy_signals.loc[idx, 'close'] * 0.96),
                           fontsize=10, color='yellow', ha='center', fontweight='bold',
                           zorder=11)

        if not sell_signals.empty:
            # 绿色圆圈 S (匹配同花顺)
            ax1.scatter(sell_signals.index, sell_signals['close'] * 1.02,
                       marker='o', color='green', s=80, zorder=10,
                       edgecolors='yellow', linewidths=1.5)
            for idx in sell_signals.index:
                ax1.annotate('S', (idx, sell_signals.loc[idx, 'close'] * 1.04),
                           fontsize=10, color='yellow', ha='center', fontweight='bold',
                           zorder=11)

    # 标题和图例
    ax1.set_title(title, fontsize=12, fontweight='bold', color='white')
    ax1.set_ylabel('价格', color='white')
    ax1.tick_params(colors='white')
    ax1.legend(loc='upper left', fontsize=9, facecolor='#1a1a2e', edgecolor='gray',
               labelcolor='white')
    ax1.grid(True, alpha=0.2, color='gray')
    ax1.set_facecolor('#0d1117')

    # === 成交量副图 ===
    if show_volume and 'volume' in result.columns:
        ax_vol = axes[ax_idx]
        ax_idx += 1
        ax_vol.set_facecolor('#0d1117')

        vol = result['volume']
        if isinstance(vol, pd.DataFrame):
            vol = vol.iloc[:, 0]

        colors = ['red' if c >= o else 'green'
                  for c, o in zip(result['close'], result['open'])]
        ax_vol.bar(dates, vol.values, color=colors, alpha=0.7, width=0.8)
        ax_vol.set_ylabel('成交量', color='white')
        ax_vol.tick_params(colors='white')
        ax_vol.grid(True, alpha=0.2, color='gray')

    # === MACD副图 ===
    if show_macd:
        ax_macd = axes[ax_idx]
        ax_macd.set_facecolor('#0d1117')

        macd = calculate_macd(result['close'])
        ax_macd.plot(dates, macd['dif'], color='blue', linewidth=0.8, label='DIF')
        ax_macd.plot(dates, macd['dea'], color='orange', linewidth=0.8, label='DEA')
        macd_colors = ['red' if v >= 0 else 'green' for v in macd['macd']]
        ax_macd.bar(dates, macd['macd'], color=macd_colors, alpha=0.7, width=0.8)
        ax_macd.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
        ax_macd.set_ylabel('MACD', color='white')
        ax_macd.tick_params(colors='white')
        ax_macd.legend(loc='upper left', fontsize=8, facecolor='#1a1a2e',
                      edgecolor='gray', labelcolor='white')
        ax_macd.grid(True, alpha=0.2, color='gray')

    # 格式化x轴
    last_ax = axes[-1]
    last_ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    last_ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(last_ax.xaxis.get_majorticklabels(), rotation=45, ha='right', color='white')

    for ax in axes[:-1]:
        ax.set_xticklabels([])

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"图表已保存至: {save_path}")
    else:
        plt.show()


# =============================================================================
# GS策略指标
# =============================================================================

def calculate_gs_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算GS策略指标 (基于通达信公式)

    Parameters
    ----------
    df : pd.DataFrame
        包含 OHLCV 数据的 DataFrame

    Returns
    -------
    pd.DataFrame
        添加了GS策略指标列的 DataFrame
    """
    result = df.copy()
    c = result['close']
    o = result['open']
    h = result['high']
    l = result['low']

    # === BB: 基准线 (4MA融合) ===
    bb0 = (c.rolling(3).mean() + c.rolling(7).mean() +
           c.rolling(13).mean() + c.rolling(27).mean()) / 4
    bb1 = ema(c, 5)
    bb = bb0.where(bb0.notna(), bb1)

    # === A0: 加权价 (Close权重60%) ===
    a0 = (h + l + 2 * o + 6 * c) / 10

    # === TK: 看跌形态过滤器 ===
    c_prev_h = c.shift(1)
    c_prev_l = c.shift(1)
    c_prev_c = c.shift(1)
    tk = (
        (c < o) |
        ((c < c_prev_h) & (c > o)) |
        ((c >= o) & ((h - c) >= (c - o)) & (c / c_prev_c < 1.02)) |
        ((c == o) & ((h - c) >= (c - l)) & (c / c_prev_c < 1.05))
    )

    # === TP: 看涨形态过滤器 ===
    tp = (
        ((c > o) & (c / c_prev_c > 0.94)) |
        ((c > c_prev_l) & (c < o)) |
        ((c <= o) & ((c - l) >= (o - c)) & (c / c_prev_c > 0.98)) |
        ((c == o) & ((c - l) >= (h - c)) & (c / c_prev_c > 0.95))
    )

    # === 10层迭代平滑信号线 A0→A9→A ===
    def _cross(a, b):
        return (a > b) & (a.shift(1) <= b.shift(1))

    a_prev = a0
    for i in range(10):
        c_up = _cross(a_prev, bb) & tk
        c_dn = _cross(bb, a_prev) & tp
        a_prev = pd.Series(
            np.where(c_up, bb * 0.98, np.where(c_dn, bb * 1.02, a_prev)),
            index=df.index
        )
    a_line = a_prev  # 最终A线

    # === 趋势状态 ===
    k = a_line >= bb  # 多头
    p = a_line < bb   # 空头

    # === 4种趋势分类 ===
    zf = (c / c_prev_c - 1) * 100  # 涨跌幅
    zj = (a_line / bb - 1) * 100   # 乖离率

    # TCY: 强势上涨
    tcy = k & (
        ((c >= c_prev_h) & ((h - c) < (c - o))) |
        (zf >= 7)
    )
    # TZK: 温和上涨
    tzk = k & ~tcy
    # TKC: 强势下跌
    tkc = p & (
        (c < c_prev_l) |
        ((c > c_prev_l) & (c > o) & (zf < 3) & (zj <= -10))
    )
    # TZD: 温和下跌
    tzd = p & ~tkc

    # === 支撑压力位 RBB ===
    rbb = (c.rolling(2).sum() / 3 + c.rolling(6).sum() / 7 +
           c.rolling(12).sum() / 13 + c.rolling(26).sum() / 27)
    rb1 = 4 * 1.01 - 1540 / 2457
    rb2 = 4 * 0.99 - 1540 / 2457
    ax1 = rbb / rb1  # 压力位
    ax2 = rbb / rb2  # 支撑位

    # === 买卖信号 ===
    buy_signal = _cross(a_line, bb)
    sell_signal = _cross(bb, a_line)

    # === K线染色标记 ===
    # 0=默认, 1=多头红, 2=空头绿, 3=涨停紫, 4=跌停灰, 5=一阳穿三线, 6=一阴穿三线
    kline_color = pd.Series(0, index=df.index, dtype=int)

    # 涨停/跌停
    limit_up = ((c - c_prev_c) * 100 / c_prev_c >= (10 - 0.01 * 100 / c_prev_c)) & (c == h)
    limit_down = c <= c_prev_c * 0.905
    kline_color[limit_up] = 3
    kline_color[limit_down] = 4

    # 一阳穿三线 / 一阴穿三线
    ma5 = c.rolling(5).mean()
    ma10 = c.rolling(10).mean()
    ma20 = c.rolling(20).mean()
    one_line_up = (l < pd.concat([ma5, ma10, ma20], axis=1).min(axis=1)) & (c > ma5) & (c > ma10) & (c > ma20)
    one_line_dn = (h > pd.concat([ma5, ma10, ma20], axis=1).max(axis=1)) & (c < ma5) & (c < ma10) & (c < ma20)
    kline_color[one_line_up & (kline_color == 0)] = 5
    kline_color[one_line_dn & (kline_color == 0)] = 6

    # 多头/空头染色 (非特殊K线)
    kline_color[k & (kline_color == 0)] = 1
    kline_color[p & (kline_color == 0)] = 2

    # === 写入结果 ===
    result['gs_bb'] = bb
    result['gs_a'] = a_line
    result['gs_k'] = k
    result['gs_p'] = p
    result['gs_tcy'] = tcy
    result['gs_tzk'] = tzk
    result['gs_tkc'] = tkc
    result['gs_tzd'] = tzd
    result['gs_rbb'] = rbb
    result['gs_ax1'] = ax1  # 压力位
    result['gs_ax2'] = ax2  # 支撑位
    result['gs_zj'] = zj    # 乖离率
    result['gs_zf'] = zf    # 涨跌幅
    result['gs_buy'] = buy_signal
    result['gs_sell'] = sell_signal
    result['gs_kline_color'] = kline_color

    return result


def get_gs_signal(df: pd.DataFrame) -> dict:
    """
    获取最新一天的GS策略信号

    Parameters
    ----------
    df : pd.DataFrame
        包含GS策略指标的 DataFrame (由 calculate_gs_strategy 计算)

    Returns
    -------
    dict
        信号字典
    """
    if len(df) < 2:
        return {"error": "数据不足"}

    latest = df.iloc[-1]

    # 趋势状态
    if latest['gs_tcy']:
        trend = "强势上涨"
    elif latest['gs_tzk']:
        trend = "温和上涨"
    elif latest['gs_tkc']:
        trend = "强势下跌"
    elif latest['gs_tzd']:
        trend = "温和下跌"
    else:
        trend = "未知"

    # K线颜色名
    color_map = {0: "默认", 1: "多头", 2: "空头", 3: "涨停", 4: "跌停", 5: "一阳穿三线", 6: "一阴穿三线"}

    signal = {
        "date": df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else len(df) - 1,
        "gs_bb": round(float(latest['gs_bb']), 2) if pd.notna(latest['gs_bb']) else None,
        "gs_a": round(float(latest['gs_a']), 2) if pd.notna(latest['gs_a']) else None,
        "trend": trend,
        "trend_state": "K(多头)" if latest['gs_k'] else "P(空头)",
        "zj_bias": round(float(latest['gs_zj']), 2) if pd.notna(latest['gs_zj']) else None,
        "zf": round(float(latest['gs_zf']), 2) if pd.notna(latest['gs_zf']) else None,
        "support": round(float(latest['gs_ax2']), 2) if pd.notna(latest['gs_ax2']) else None,
        "resistance": round(float(latest['gs_ax1']), 2) if pd.notna(latest['gs_ax1']) else None,
        "kline_color": color_map.get(int(latest['gs_kline_color']), "默认"),
        "trading": {
            "buy": bool(latest['gs_buy']),
            "sell": bool(latest['gs_sell']),
            "recommendation": "买入" if latest['gs_buy'] else
                             "卖出" if latest['gs_sell'] else "持有",
        },
    }

    return signal


# ============================================================
# 主力趋势雷达指标 (TDX公式转换)
# ============================================================

def _ema_np(arr: np.ndarray, period: int) -> np.ndarray:
    """numpy 版 EMA，避免 pandas 索引对齐问题"""
    alpha = 2.0 / (period + 1)
    out = np.empty_like(arr, dtype=float)
    out[0] = arr[0] if not np.isnan(arr[0]) else 0.0
    for i in range(1, len(arr)):
        if np.isnan(arr[i]):
            out[i] = out[i-1]
        else:
            out[i] = alpha * arr[i] + (1 - alpha) * out[i-1]
    return out

def calculate_radar_indicator(df: pd.DataFrame) -> pd.DataFrame:
    """
    主力趋势雷达指标计算

    公式源码 (通达信TDX):
        最小值:=LLV(LOW,10);
        最大值:=HHV(HIGH,25);
        波动线:=EMA((CLOSE-最小值)/(最大值-最小值)*4,4);
        平均线:EMA(波动线,3);

        信息:=平均线>=REF(平均线,1);
        走强:=CLOSE>MA(CLOSE,20) AND CLOSE>MA(CLOSE,5);
        走弱:=CLOSE<MA(CLOSE,10) AND CLOSE<MA(CLOSE,5);
        量:=VOL>MA(VOL,5);

        D(底): 信息由0→1 + 连续3日下降 + 平均线<0.5
        S(升): 信息由0→1 + 走强由0→1 + 放量
        DD(顶): 平均线>2 + 信息由1→0 + 连续2日上升
        TZ(下): 信息由1→0 + 连续2日上升 + 走弱 + 平均线>1

    Parameters
    ----------
    df : pd.DataFrame
        包含 open, high, low, close, volume 的 DataFrame

    Returns
    -------
    pd.DataFrame
        包含 radar_wave, radar_avg, radar_buy, radar_sell,
        radar_top, radar_down 的 DataFrame
    """
    # 重置索引避免重复日期索引导致 pandas align 错误
    df = df.reset_index(drop=True)

    # 使用 numpy 数组进行核心计算，避免 pandas 索引对齐问题
    h = np.array(df['high'], dtype=np.float64)
    l = np.array(df['low'], dtype=np.float64)
    c = np.array(df['close'], dtype=np.float64)
    # 指数数据可能没有 volume 列，用 amount 作为替代
    if 'volume' in df.columns:
        v = np.array(df['volume'], dtype=np.float64)
    elif 'amount' in df.columns:
        v = np.array(df['amount'], dtype=np.float64)
    else:
        v = np.ones(len(c), dtype=np.float64)  # fallback: 全1，不影响信号判断
    n = len(c)

    # 核心计算
    min_val = np.full(n, np.nan)
    max_val = np.full(n, np.nan)
    for i in range(9, n):
        min_val[i] = np.nanmin(l[i-9:i+1])
    for i in range(24, n):
        max_val[i] = np.nanmax(h[i-24:i+1])

    # 避免除零
    range_val = max_val - min_val
    range_val[range_val == 0] = np.nan

    # 波动线: 标准化价格到 0~4 区间
    raw_wave = ((c - min_val) / range_val) * 4
    wave = _ema_np(raw_wave, 4)

    # 平均线: 波动线的3日EMA
    avg = _ema_np(wave, 3)

    # 状态判断
    info = np.zeros(n, dtype=int)
    info[1:] = (avg[1:] >= avg[:-1]).astype(int)
    strong = np.zeros(n, dtype=int)
    weak = np.zeros(n, dtype=int)
    vol_up = np.zeros(n, dtype=int)
    for i in range(19, n):
        ci = float(c[i])
        strong[i] = 1 if ci > float(np.nanmean(c[i-19:i+1])) and ci > float(np.nanmean(c[i-4:i+1])) else 0
    for i in range(9, n):
        ci = float(c[i])
        weak[i] = 1 if ci < float(np.nanmean(c[i-9:i+1])) and ci < float(np.nanmean(c[i-4:i+1])) else 0
    for i in range(4, n):
        vol_up[i] = 1 if float(v[i]) > float(np.nanmean(v[i-4:i+1])) else 0

    # 信号计算
    info_prev1 = np.zeros(n, dtype=int); info_prev1[1:] = info[:-1]
    info_prev2 = np.zeros(n, dtype=int); info_prev2[2:] = info[:-2]
    info_prev3 = np.zeros(n, dtype=int); info_prev3[3:] = info[:-3]
    strong_prev1 = np.zeros(n, dtype=int); strong_prev1[1:] = strong[:-1]

    # 底(D): 信息由0→1 + 连续3日下降 + 平均线<0.5
    radar_buy = (
        (info == 1) & (info_prev1 == 0) &
        ((info_prev2 + info_prev3) == 0) &
        (avg < 0.5)
    )

    # 升(S): 信息由0→1 + 走强由0→1 + 放量
    radar_sell = (
        (info == 1) & (info_prev1 == 0) &
        ((info_prev2 + info_prev3) == 0) &
        (strong == 1) & (strong_prev1 == 0) &
        (vol_up == 1)
    )

    # 顶(DD): 平均线>2 + 信息由1→0 + 连续2日上升
    radar_top = (
        (avg > 2) &
        (info == 0) & (info_prev1 == 1) &
        (info_prev2 == 1)
    )

    # 下(TZ): 信息由1→0 + 连续2日上升 + 走弱 + 平均线>1
    radar_down = (
        (info == 0) & (info_prev1 == 1) &
        (info_prev2 == 1) &
        (weak == 1) &
        (avg > 1)
    )

    # 组装结果
    result = df.copy()
    result['radar_wave'] = wave
    result['radar_avg'] = avg
    result['radar_buy'] = radar_buy
    result['radar_sell'] = radar_sell
    result['radar_top'] = radar_top
    result['radar_down'] = radar_down

    return result


def get_radar_signal(df: pd.DataFrame) -> dict:
    """
    获取最新的主力趋势雷达信号

    Parameters
    ----------
    df : pd.DataFrame
        calculate_radar_indicator 返回的 DataFrame

    Returns
    -------
    dict
        信号字典
    """
    if len(df) < 2:
        return {"error": "数据不足"}

    latest = df.iloc[-1]

    signal = {
        "date": df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else len(df) - 1,
        "radar_wave": round(float(latest['radar_wave']), 2) if pd.notna(latest['radar_wave']) else None,
        "radar_avg": round(float(latest['radar_avg']), 2) if pd.notna(latest['radar_avg']) else None,
        "radar_buy": bool(latest['radar_buy']),
        "radar_sell": bool(latest['radar_sell']),
        "radar_top": bool(latest['radar_top']),
        "radar_down": bool(latest['radar_down']),
        "trend": "上升" if latest['radar_avg'] >= df['radar_avg'].iloc[-2] else "下降",
    }

    return signal


# ============================================================
# AI引力波指标 (基于同花顺公式移植，使用Level-1资金流数据)
# ============================================================

def fetch_fund_flow_data(symbol: str, days: int = 120) -> pd.DataFrame:
    """
    获取个股资金流向历史数据 (Tushare数据源，AkShare回退)

    Parameters
    ----------
    symbol : str
        股票代码，如 '000001', '600519'
    days : int
        获取的历史天数

    Returns
    -------
    pd.DataFrame
        包含 date, main_net (主力净流入) 列的 DataFrame
    """
    from datetime import datetime, timedelta

    # 方案1: Tushare (资金流数据更稳定)
    try:
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN", "23651a8611b00bf491c7378d81d0bc6265543153530194be989e6ada")
        ts.set_token(token)
        pro = ts.pro_api()

        # 转换代码格式: 000001 -> 000001.SZ
        if "." not in symbol:
            suffix = ".SH" if symbol.startswith(("5", "6", "9")) else ".SZ"
            ts_code = symbol + suffix
        else:
            ts_code = symbol

        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")

        df = pro.moneyflow(ts_code=ts_code, start_date=start, end_date=end)
        if df is not None and not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
            df = df.sort_values("trade_date").set_index("trade_date")
            # 主力净流入 = 超大单净买入 + 大单净买入 (单位: 万元)
            for col in ["buy_elg_amount", "sell_elg_amount", "buy_lg_amount", "sell_lg_amount"]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            df["main_net"] = (df["buy_elg_amount"] + df["buy_lg_amount"]) - (df["sell_elg_amount"] + df["sell_lg_amount"])
            df.index.name = "date"
            return df[["main_net"]].tail(days)
    except Exception:
        pass

    # 方案2: AkShare 回退
    try:
        import akshare as ak
        market = "sh" if symbol.startswith(("5", "6", "9")) else "sz"
        df = ak.stock_individual_fund_flow(stock=symbol, market=market)
        if df is not None and not df.empty:
            col_map = {"日期": "date", "主力净流入-净额": "main_net"}
            available = {k: v for k, v in col_map.items() if k in df.columns}
            df = df.rename(columns=available)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
                df["main_net"] = pd.to_numeric(df["main_net"], errors="coerce")
                return df[["main_net"]].tail(days)
    except Exception:
        pass

    return pd.DataFrame(columns=["main_net"])


def calculate_ai_gravity(symbol: str, days: int = 120) -> pd.DataFrame:
    """
    计算AI引力波指标

    基于同花顺AI引力波公式，使用东方财富资金流数据替代Level-2机构数据。
    核心逻辑：资金流意愿 + MA10趋势 → 买入信号

    Parameters
    ----------
    symbol : str
        股票代码
    days : int
        计算天数

    Returns
    -------
    pd.DataFrame
        包含引力波信号列的 DataFrame
    """
    # 获取K线数据
    kline = fetch_realtime_data(symbol, days=days)
    if kline is None or kline.empty:
        return pd.DataFrame()

    # 获取资金流数据
    fund_flow = fetch_fund_flow_data(symbol, days=days)

    # 对齐日期
    if not fund_flow.empty and "main_net" in fund_flow.columns:
        kline["main_net"] = fund_flow["main_net"].reindex(kline.index, method="ffill")
    else:
        kline["main_net"] = 0.0

    result = kline.copy()
    close = result["close"]

    # === MA10 ===
    ma10 = close.rolling(10).mean()
    result["ma10"] = ma10

    # === 资金流意愿 (替代同花顺的 jgjrda/jgrda) ===
    main_net = result["main_net"].fillna(0)

    # 去噪：连续多日资金流完全相同（数据未更新）时置零
    unchanged = (main_net == main_net.shift(1)) & (main_net == main_net.shift(2)) & (main_net == main_net.shift(3))
    willingness = pd.Series(0.0, index=result.index)
    willingness[~unchanged] = main_net[~unchanged]

    # 限制范围 [-100, 100]
    willingness = willingness.clip(-100, 100)
    result["willingness"] = willingness

    # === 持股规则：MA10上升 + 意愿累计≥0 ===
    ma10_rising = (ma10 >= ma10.shift(1))
    willingness_sum = willingness.rolling(10).sum()
    holding_rule = (ma10_rising.rolling(3).sum() >= 2) & (willingness_sum >= 0)

    result["holding_rule"] = holding_rule.astype(float)

    # === 买入信号 ===
    signal = holding_rule.astype(int)
    first_buy = (signal == 1) & (signal.shift(1) == 0)
    continue_hold = (signal == 1) & (signal.shift(1) == 1)
    buy_signal = first_buy | continue_hold

    result["buy_signal"] = buy_signal

    # === 资金深度 (信号强度) ===
    depth = willingness * 2
    depth = depth.clip(-100, 100)
    depth_ma = depth.rolling(3).mean()
    result["gravity_depth"] = depth_ma

    # === 最终输出：买入时显示资金深度，否则为0 ===
    result["ai_gravity"] = np.where(buy_signal, depth_ma, 0.0)

    return result


def get_ai_gravity_signal(df: pd.DataFrame) -> dict:
    """
    获取最新一天的AI引力波信号

    Parameters
    ----------
    df : pd.DataFrame
        calculate_ai_gravity 返回的 DataFrame

    Returns
    -------
    dict
        信号字典
    """
    if df.empty or len(df) < 2:
        return {"error": "数据不足"}

    latest = df.iloc[-1]

    return {
        "date": df.index[-1].strftime("%Y-%m-%d") if isinstance(df.index, pd.DatetimeIndex) else str(df.index[-1])[:10],
        "ai_gravity": round(float(latest["ai_gravity"]), 2) if pd.notna(latest["ai_gravity"]) else 0,
        "buy_signal": bool(latest["buy_signal"]),
        "willingness": round(float(latest["willingness"]), 2) if pd.notna(latest["willingness"]) else 0,
        "gravity_depth": round(float(latest["gravity_depth"]), 2) if pd.notna(latest["gravity_depth"]) else 0,
    }
