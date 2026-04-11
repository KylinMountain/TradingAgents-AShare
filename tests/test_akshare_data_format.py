"""测试脚本：查看 akshare 各方法的返回数据格式

运行方式：
    python tests/test_akshare_data_format.py

注意：需要先安装 akshare: pip install akshare
"""
import sys
from datetime import datetime, timedelta


def print_section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def inspect_dataframe(df, method_name):
    """检查并打印 DataFrame 的结构"""
    if df is None:
        print(f"❌ {method_name} 返回 None")
        return

    if hasattr(df, 'empty') and df.empty:
        print(f"⚠️  {method_name} 返回空 DataFrame")
        return

    print(f"✅ {method_name} 返回数据:")
    print(f"   类型: {type(df)}")
    print(f"   形状: {df.shape if hasattr(df, 'shape') else 'N/A'}")

    if hasattr(df, 'columns'):
        print(f"   列名: {list(df.columns)}")
        print(f"\n前 3 行数据:")
        print(df.head(10).to_string())
    else:
        print(f"   数据: {df}")


def test_stock_news_em():
    """测试：东方财富个股新闻"""
    print_section("1. ak.stock_news_em() - 东方财富个股新闻")
    try:
        import akshare as ak
        df = ak.stock_news_em(symbol="600519")  # 贵州茅台
        inspect_dataframe(df, "stock_news_em")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")


def test_news_cctv():
    """测试：央视财经新闻"""
    print_section("2. ak.news_cctv() - 央视财经新闻")
    try:
        import akshare as ak
        today = datetime.now().strftime("%Y%m%d")
        df = ak.news_cctv(date=today)
        inspect_dataframe(df, "news_cctv")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")


def test_stock_main_stock_holder():
    """测试：主要股东"""
    print_section("3. ak.stock_main_stock_holder() - 主要股东")
    try:
        import akshare as ak
        df = ak.stock_main_stock_holder(stock="600519")
        inspect_dataframe(df, "stock_main_stock_holder")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")


def test_stock_zh_a_spot_em():
    """测试：A股实时行情"""
    print_section("4. ak.stock_zh_a_spot_em() - A股实时行情")
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            print(f"✅ stock_zh_a_spot_em 返回数据:")
            print(f"   类型: {type(df)}")
            print(f"   形状: {df.shape}")
            print(f"   列名: {list(df.columns)}")
            print(f"\n前 3 行数据:")
            print(df.head(3).to_string())
        else:
            print("⚠️  返回空数据")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")


def test_stock_individual_spot_xq():
    """测试：雪球个股实时数据"""
    print_section("5. ak.stock_individual_spot_xq() - 雪球个股实时数据")
    try:
        import akshare as ak
        df = ak.stock_individual_spot_xq(symbol="SH600519")
        inspect_dataframe(df, "stock_individual_spot_xq")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")


def test_stock_board_industry_fund_flow_em():
    """测试：板块资金流向"""
    print_section("6. ak.stock_fund_flow_industry() - 板块资金流向")
    try:
        import akshare as ak
        df = ak.stock_fund_flow_industry(symbol="即时")
        inspect_dataframe(df, "stock_fund_flow_industry")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")


def test_stock_lhb_detail_em():
    """测试：龙虎榜"""
    print_section("7. ak.stock_lhb_detail_em() - 龙虎榜")
    try:
        import akshare as ak
        today = '20260403'
        df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
        inspect_dataframe(df, "stock_lhb_detail_em")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")


def test_stock_zt_pool_em():
    """测试：涨停板池"""
    print_section("8. ak.stock_zt_pool_em() - 涨停板池")
    try:
        import akshare as ak
        today = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zt_pool_em(date=today)
        inspect_dataframe(df, "stock_zt_pool_em")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")


def test_stock_hot_follow_xq():
    """测试：雪球热搜"""
    print_section("9. ak.stock_hot_follow_xq() - 雪球热搜")
    try:
        import akshare as ak
        df = ak.stock_hot_follow_xq(symbol="本周新增")
        inspect_dataframe(df, "stock_hot_follow_xq")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("\n🔍 AkShare 数据格式测试")
    print("=" * 80)

    try:
        import akshare
        print(f"✅ akshare 版本: {akshare.__version__}")
    except ImportError:
        print("❌ 未安装 akshare，请运行: pip install akshare")
        sys.exit(1)

    # 运行所有测试
    test_stock_news_em()
    test_news_cctv()
    test_stock_main_stock_holder()
    test_stock_zh_a_spot_em()
    test_stock_individual_spot_xq()
    test_stock_board_industry_fund_flow_em()
    test_stock_lhb_detail_em()
    test_stock_zt_pool_em()
    test_stock_hot_follow_xq()

    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)
