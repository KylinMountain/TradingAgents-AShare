"""测试牛熊线指标"""
import pandas as pd
import numpy as np
from tradingagents.indicators import (
    calculate_niuxiong_line,
    get_signal,
    niuxiong_analysis,
    plot_niuxiong_line,
    multi_indicator_analysis,
    format_analysis_report,
    fetch_realtime_data,
    fetch_realtime_quote,
)


def generate_test_data(n=200):
    """生成测试数据"""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=n, freq='B')

    # 模拟真实股价走势
    base = 100
    trend = np.concatenate([
        np.linspace(0, 15, n//4),      # 上涨
        np.linspace(15, -5, n//4),     # 下跌
        np.linspace(-5, 10, n//4),     # 反弹
        np.linspace(10, 0, n//4),      # 回落
    ])
    noise = np.cumsum(np.random.randn(n) * 0.3)
    close = base + trend + noise

    high = close + np.abs(np.random.randn(n) * 0.5)
    low = close - np.abs(np.random.randn(n) * 0.5)
    open_ = close + np.random.randn(n) * 0.3

    return pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000000, 5000000, n)
    }, index=dates)


def test_basic():
    """测试基础功能"""
    print("=== 测试基础功能 ===")
    df = generate_test_data()

    # 计算牛熊线指标
    result = calculate_niuxiong_line(df)

    # 打印分析报告
    print(niuxiong_analysis(df))

    # 获取最新信号
    signal = get_signal(result)
    print("\n最新信号详情:")
    print(f"日期: {signal['date']}")
    print(f"短期趋势: {signal['short_ema']['trend']}")
    print(f"长期趋势: {signal['long_ema']['trend']}")
    print(f"综合状态: {signal['signal']['status']}")
    print(f"交易建议: {signal['trading']['recommendation']}")

    # 统计买卖信号
    buy_count = result['buy_signal'].sum()
    sell_count = result['sell_signal'].sum()
    print(f"\n买入信号数: {buy_count}")
    print(f"卖出信号数: {sell_count}")


def test_plot():
    """测试绘图功能"""
    print("\n=== 测试绘图功能 ===")
    df = generate_test_data()

    # 基础图表
    print("生成基础图表...")
    plot_niuxiong_line(df, save_path='niuxiong_basic.png', show_signals=True)
    print("基础图表已保存为 niuxiong_basic.png")

    # 带MACD的图表
    print("生成带MACD的图表...")
    plot_niuxiong_line(df, save_path='niuxiong_with_macd.png',
                       show_signals=True, show_macd=True)
    print("MACD图表已保存为 niuxiong_with_macd.png")


def test_multi_indicator():
    """测试多指标分析"""
    print("\n=== 测试多指标分析 ===")
    df = generate_test_data()

    analysis = multi_indicator_analysis(df)
    print(format_analysis_report(analysis))


def test_realtime():
    """测试实时数据获取 (使用mootdx，不封IP)"""
    print("\n=== 测试实时数据获取 (mootdx) ===")
    try:
        # 获取实时行情
        quote = fetch_realtime_quote("000001")
        print(f"平安银行实时行情:")
        print(f"  最新价: {quote['price']}")
        print(f"  涨跌幅: {quote['change_pct']}%")
        print(f"  成交量: {quote['volume']}")

        # 获取历史数据并计算指标
        print("\n获取历史数据并计算牛熊线...")
        df = fetch_realtime_data("000001", days=120)
        print(f"获取到 {len(df)} 条数据")

        result = calculate_niuxiong_line(df)
        signal = get_signal(result)
        print(f"牛熊线状态: {signal['signal']['status']}")
        print(f"交易建议: {signal['trading']['recommendation']}")

        # 绘制真实数据图表
        plot_niuxiong_line(df, title="平安银行(000001) 牛熊线分析",
                          save_path='niuxiong_000001.png', show_signals=True, show_macd=True)
        print("真实数据图表已保存为 niuxiong_000001.png")

    except Exception as e:
        print(f"实时数据测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_basic()
    test_plot()
    test_multi_indicator()
    test_realtime()
