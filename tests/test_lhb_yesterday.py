"""测试 get_lhb_detail 使用昨天的日期"""
## source .venv/bin/activate && python tests/test_lhb_yesterday.py global_news


def test_lhb_with_yesterday():
    """使用昨天（周五）的日期测试"""
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider
    from datetime import datetime, timedelta

    provider = CnAkshareProvider()

    # 使用昨天的日期（2026-04-03，周五）
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"测试日期: {yesterday} (周五)\n")

    # 测试一个可能在龙虎榜上的股票
    test_symbols = ["600519", "000001", "300750"]

    for symbol in test_symbols:
        print(f"测试股票: {symbol}")
        result = provider.get_lhb_detail(symbol, yesterday)

        print(f"返回长度: {len(result)} 字符")
        print(f"结果预览:\n{result[:300]}\n")
        print("-" * 60)


def test_get_stock_data_detail():
    """测试 get_stock_data 详细输出"""
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider
    from datetime import datetime, timedelta

    provider = CnAkshareProvider()
    today = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    test_symbols = ["600519", "000001", "300750"]
    for symbol in test_symbols:
        print(f"\n{'='*60}")
        print(f"股票: {symbol}，查询范围: {start} ~ {today}")
        print("=" * 60)
        result = provider.get_stock_data(symbol, start, today)
        print(result)


def test_get_global_news():
    """测试 get_global_news 方法"""
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider
    from datetime import datetime

    provider = CnAkshareProvider()
    curr_date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"测试 get_global_news，日期: {curr_date}")
    print("=" * 60)

    result = provider.get_global_news(curr_date)
    print(f"返回类型: {type(result)}")
    print(f"字符数: {len(result)}")
    print(f"开头: {repr(result[:50])}")

    if result.startswith("## "):
        print("✅ 成功！返回正常新闻内容")
        print(f"\n前500字:\n{result[:5000]}")
    else:
        print(f"❌ 返回异常内容: {result[:200]}")


if __name__ == "__main__":
    import sys
    _funcs = {
        "lhb": test_lhb_with_yesterday,
        "stock_data": test_get_stock_data_detail,
        "global_news": test_get_global_news,
    }
    targets = sys.argv[1:]
    funcs = [_funcs[t] for t in targets if t in _funcs] or [test_get_global_news]
    for fn in funcs:
        fn()

