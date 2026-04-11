"""测试 Smart Money Analyst 使用的数据源"""
import asyncio
from datetime import datetime


async def _safe(tool, payload):
    """安全调用工具（容错）"""
    try:
        return await asyncio.to_thread(tool.invoke, payload)
    except Exception as exc:
        return f"调用失败：{exc}"


async def test_individual_fund_flow(ticker="600519"):
    """测试主力资金净流向"""
    from tradingagents.agents.utils.agent_utils import get_individual_fund_flow

    print(f"\n{'='*60}")
    print(f"测试 get_individual_fund_flow: {ticker}")
    print(f"{'='*60}\n")

    result = await _safe(get_individual_fund_flow, {"symbol": ticker})
    print(result)
    print(f"\n返回长度: {len(result)} 字符")


async def test_lhb_detail(ticker="600519", date=None):
    """测试龙虎榜数据"""
    from tradingagents.agents.utils.agent_utils import get_lhb_detail

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"测试 get_lhb_detail: {ticker} @ {date}")
    print(f"{'='*60}\n")

    result = await _safe(get_lhb_detail, {"symbol": ticker, "date": date})
    print(result)
    print(f"\n返回长度: {len(result)} 字符")


async def test_indicators_volume(ticker="600519", date=None, look_back_days=20):
    """测试成交量指标(vwma)"""
    from tradingagents.agents.utils.agent_utils import get_indicators

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"测试 get_indicators (volume): {ticker} @ {date}, 回溯{look_back_days}天")
    print(f"{'='*60}\n")

    result = await _safe(get_indicators, {
        "symbol": ticker,
        "indicator": "volume",
        "curr_date": date,
        "look_back_days": look_back_days,
    })
    print(result)
    print(f"\n返回长度: {len(result)} 字符")


async def test_all_parallel(ticker="600519", date=None):
    """并行测试所有3个数据源（模拟 Smart Money Analyst 实际调用）"""
    from tradingagents.agents.utils.agent_utils import (
        get_individual_fund_flow,
        get_lhb_detail,
        get_indicators,
    )

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"并行测试所有数据源: {ticker} @ {date}")
    print(f"{'='*60}\n")

    start = asyncio.get_event_loop().time()

    results = await asyncio.gather(
        _safe(get_individual_fund_flow, {"symbol": ticker}),
        _safe(get_lhb_detail, {"symbol": ticker, "date": date}),
        _safe(get_indicators, {
            "symbol": ticker,
            "indicator": "volume",
            "curr_date": date,
            "look_back_days": 20,
        })
    )

    elapsed = asyncio.get_event_loop().time() - start

    fund_flow, lhb, volume = results

    print(f"【近5日主力资金净流向】\n{fund_flow}\n")
    print(f"【龙虎榜数据】\n{lhb}\n")
    print(f"【成交量指标(vwma)】\n{volume}\n")
    print(f"⏱️  总耗时: {elapsed:.2f}秒")


async def main():
    """主测试入口"""
    import sys

    # 默认测试股票和日期
    ticker = "600519"  # 贵州茅台
    date = datetime.now().strftime("%Y-%m-%d")

    # 解析命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "fund_flow":
            ticker = sys.argv[2] if len(sys.argv) > 2 else ticker
            await test_individual_fund_flow(ticker)

        elif command == "lhb":
            ticker = sys.argv[2] if len(sys.argv) > 2 else ticker
            date = sys.argv[3] if len(sys.argv) > 3 else date
            await test_lhb_detail(ticker, date)

        elif command == "volume":
            ticker = sys.argv[2] if len(sys.argv) > 2 else ticker
            date = sys.argv[3] if len(sys.argv) > 3 else date
            look_back = int(sys.argv[4]) if len(sys.argv) > 4 else 20
            await test_indicators_volume(ticker, date, look_back)

        elif command == "all":
            ticker = sys.argv[2] if len(sys.argv) > 2 else ticker
            date = sys.argv[3] if len(sys.argv) > 3 else date
            await test_all_parallel(ticker, date)

        else:
            print(f"❌ 未知命令: {command}")
            print_usage()

    else:
        # 默认运行所有测试
        await test_individual_fund_flow(ticker)
        await test_lhb_detail(ticker, date)
        await test_indicators_volume(ticker, date)
        await test_all_parallel(ticker, date)


def print_usage():
    """打印使用说明"""
    print("""
使用方法:

1. 测试单个数据源:
   python tests/test_smart_money_data.py fund_flow [股票代码]
   python tests/test_smart_money_data.py lhb [股票代码] [日期]
   python tests/test_smart_money_data.py volume [股票代码] [日期] [回溯天数]

2. 并行测试所有数据源:
   python tests/test_smart_money_data.py all [股票代码] [日期]

3. 运行所有测试（默认）:
   python tests/test_smart_money_data.py

示例:
   python tests/test_smart_money_data.py fund_flow 000001
   python tests/test_smart_money_data.py lhb 600519 2026-04-10
   python tests/test_smart_money_data.py volume 600519 2026-04-10 30
   python tests/test_smart_money_data.py all 600519
""")


if __name__ == "__main__":
    print_usage()
    asyncio.run(main())
