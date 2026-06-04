"""
同花顺牛熊线高阶指标 Python 实现
基于通达信公式源码转换

指标组成:
- 短期轨道: EMA(C,10) 经过3次平滑形成5条轨道 (绿色/品红色)
- 长期轨道: EMA(C,45) 经过3次平滑形成5条轨道 (橙色/红色)
- 轨道线: 基于布林带原理的支撑/压力位

功能:
- 实时数据接入 (akshare)
- 买卖信号标记
- 多指标联动 (MACD/KDJ/RSI)
"""

import pandas as pd
import numpy as np
from typing import Optional


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=period, adjust=False).mean()


def fetch_realtime_data(symbol: str, days: int = 120) -> pd.DataFrame:
    """
    获取A股历史K线数据 (使用mootdx，不封IP)

    Parameters
    ----------
    symbol : str
        股票代码，如 '000001', '600519'
    days : int
        获取的历史天数

    Returns
    -------
    pd.DataFrame
        OHLCV 数据
    """
    from mootdx.quotes import Quotes

    client = Quotes.factory(market='std')

    # 获取日K线 (category=4)
    # mootdx 返回的是最近N条数据，需要多取一些确保覆盖
    klines = client.bars(symbol=symbol, category=4, offset=days + 50)

    if klines is None or klines.empty:
        raise ValueError(f"未获取到 {symbol} 的K线数据")

    # 转换为 DataFrame
    df = pd.DataFrame(klines)
    df = df.rename(columns={
        'open': 'open',
        'close': 'close',
        'high': 'high',
        'low': 'low',
        'vol': 'volume',
        'amount': 'amount',
        'datetime': 'date',
    })

    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.sort_index()

    return df.tail(days)


def fetch_realtime_quote(symbol: str) -> dict:
    """
    获取股票实时行情 (使用腾讯财经API，不封IP)

    Parameters
    ----------
    symbol : str
        股票代码

    Returns
    -------
    dict
        实时行情数据
    """
    import urllib.request

    # 判断市场前缀
    if symbol.startswith(("6", "9")):
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

        return {
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
        }

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

    # === 决策线 (黄色虚线) - 短期EMA ===
    result['decision_line'] = ema(close, 10)

    # === 熊线 (绿色虚线) - 长期EMA ===
    result['bear_line'] = ema(close, 45)

    # === 轨道线 (青色实线) ===
    # 同花顺牛熊线高阶的轨道线 = 典型价的10日移动平均
    # 典型价 TP = (HIGH + LOW + CLOSE) / 3
    typical_price = (high + low + close) / 3
    result['orbit_line'] = typical_price.rolling(10).mean()

    # === 支撑位/压力位 (红色水平线) ===
    lookback = 60  # 回看60日
    result['support'] = low.rolling(lookback).min()
    result['resistance'] = high.rolling(lookback).max()

    # === 趋势判断 ===
    result['short_trend_up'] = result['decision_line'] > result['decision_line'].shift(1)
    result['long_trend_up'] = result['bear_line'] > result['bear_line'].shift(1)

    # === 综合信号 ===
    result['bullish_alignment'] = result['short_trend_up'] & result['long_trend_up']
    result['bearish_alignment'] = (~result['short_trend_up']) & (~result['long_trend_up'])

    # === 买卖信号 ===
    result['buy_signal'] = generate_buy_signal(result)
    result['sell_signal'] = generate_sell_signal(result)

    return result


def generate_buy_signal(df: pd.DataFrame) -> pd.Series:
    """
    生成买入信号 (匹配同花顺原版)

    买入条件:
    1. 价格触及支撑位
    2. 价格站上轨道线
    3. 决策线金叉熊线
    """
    signals = pd.Series(False, index=df.index)

    # 条件1: 价格触及支撑位附近
    touch_support = df['close'] <= df['support'] * 1.02

    # 条件2: 价格从下方站上轨道线
    cross_orbit_up = (df['close'] > df['orbit_line']) & (df['close'].shift(1) <= df['orbit_line'].shift(1))

    # 条件3: 决策线上穿熊线
    golden_cross = (df['decision_line'] > df['bear_line']) & (df['decision_line'].shift(1) <= df['bear_line'].shift(1))

    # 综合信号
    signals = touch_support | cross_orbit_up | golden_cross

    return signals


def generate_sell_signal(df: pd.DataFrame) -> pd.Series:
    """
    生成卖出信号 (匹配同花顺原版)

    卖出条件:
    1. 价格触及压力位
    2. 价格跌破轨道线
    3. 决策线死叉熊线
    """
    signals = pd.Series(False, index=df.index)

    # 条件1: 价格触及压力位附近
    touch_resistance = df['close'] >= df['resistance'] * 0.98

    # 条件2: 价格从上方跌破轨道线
    cross_orbit_down = (df['close'] < df['orbit_line']) & (df['close'].shift(1) >= df['orbit_line'].shift(1))

    # 条件3: 决策线下穿熊线
    death_cross = (df['decision_line'] < df['bear_line']) & (df['decision_line'].shift(1) >= df['bear_line'].shift(1))

    # 综合信号
    signals = touch_resistance | cross_orbit_down | death_cross

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
        "decision_line": round(latest['decision_line'], 2),  # 决策线
        "bear_line": round(latest['bear_line'], 2),          # 熊线
        "orbit_line": round(latest['orbit_line'], 2),        # 轨道线
        "support": round(latest['support'], 2),              # 支撑位
        "resistance": round(latest['resistance'], 2),        # 压力位

        # 趋势
        "short_trend": "上涨" if latest['short_trend_up'] else "下跌",
        "long_trend": "上涨" if latest['long_trend_up'] else "下跌",

        # 综合信号
        "signal": {
            "bullish": latest['bullish_alignment'],
            "bearish": latest['bearish_alignment'],
            "status": "多头排列" if latest['bullish_alignment'] else
                      "空头排列" if latest['bearish_alignment'] else "震荡",
        },

        # 买卖信号
        "trading": {
            "buy": latest['buy_signal'],
            "sell": latest['sell_signal'],
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

    report = f"""=== 同花顺牛熊线高阶指标分析 ===

【短期轨道 (EMA10)】
  EMA1: {signal['short_ema']['ema1']} ({signal['short_ema']['trend']})
  EMA2: {signal['short_ema']['ema2']}
  EMA3: {signal['short_ema']['ema3']}
  EMA4: {signal['short_ema']['ema4']}
  EMA5: {signal['short_ema']['ema5']}

【长期轨道 (EMA45)】
  EMA1: {signal['long_ema']['ema1']} ({signal['long_ema']['trend']})
  EMA2: {signal['long_ema']['ema2']}
  EMA3: {signal['long_ema']['ema3']}
  EMA4: {signal['long_ema']['ema4']}
  EMA5: {signal['long_ema']['ema5']}

【轨道线】
  压力位: {signal['orbit']['upper']}
  中轨:   {signal['orbit']['middle']}
  支撑位: {signal['orbit']['lower']}

【综合信号】
  状态: {signal['signal']['status']}
  多头排列: {'是' if signal['signal']['bullish'] else '否'}
  空头排列: {'是' if signal['signal']['bearish'] else '否'}
  轨道收敛: {'是' if signal['signal']['converging'] else '否'}
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
    report = f"""=== 多指标联动分析报告 ===
日期: {analysis['date']}

【牛熊线指标】
  状态: {analysis['niuxiong']['signal']['status']}
  短期趋势: {analysis['niuxiong']['short_ema']['trend']}
  长期趋势: {analysis['niuxiong']['long_ema']['trend']}
  压力位: {analysis['niuxiong']['orbit']['upper']}
  支撑位: {analysis['niuxiong']['orbit']['lower']}
  交易建议: {analysis['niuxiong']['trading']['recommendation']}

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

    # 支撑位 (红色水平线)
    latest_support = result['support'].iloc[-1]
    ax1.axhline(y=latest_support, color='red', linestyle='-', linewidth=1.5,
                alpha=0.8, label=f'支撑位 {latest_support:.2f}')

    # 压力位 (红色水平线)
    latest_resistance = result['resistance'].iloc[-1]
    ax1.axhline(y=latest_resistance, color='red', linestyle='-', linewidth=1.5,
                alpha=0.8, label=f'压力位 {latest_resistance:.2f}')

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
