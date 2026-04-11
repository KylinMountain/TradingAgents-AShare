"""测试 stock_fund_flow_industry 接口"""


def test_fund_flow_today():
    """测试今日数据"""
    import akshare as ak

    print("测试 stock_fund_flow_industry (今日)：\n")

    try:
        df = ak.stock_fund_flow_industry(symbol="今日")
        print(f"✅ 成功!")
        print(f"形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        print(f"\n前3行:\n{df.head(3)}")
    except Exception as e:
        print(f"❌ 失败: {type(e).__name__}")
        print(f"错误: {str(e)[:200]}")


def test_fund_flow_provider():
    """测试 provider 方法"""
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider

    print("\n\n测试 CnAkshareProvider.get_board_fund_flow()：\n")

    provider = CnAkshareProvider()
    result = provider.get_board_fund_flow()

    print(f"返回长度: {len(result)} 字符")
    print(f"结果:\n{result}")


if __name__ == "__main__":
    test_fund_flow_today()
    test_fund_flow_provider()
