"""调试接口返回的实际数据结构"""
from datetime import datetime


def debug_lhb_detail():
    """调试龙虎榜接口"""
    print("\n" + "=" * 60)
    print("调试: stock_lhb_detail_em")
    print("=" * 60)

    try:
        import akshare as ak
        today = datetime.now().strftime("%Y%m%d")

        print(f"调用参数: start_date={today}, end_date={today}")
        df = ak.stock_lhb_detail_em(start_date=today, end_date=today)

        print(f"返回类型: {type(df)}")
        print(f"是否为 None: {df is None}")

        if df is not None:
            print(f"是否为空: {df.empty if hasattr(df, 'empty') else 'N/A'}")
            if hasattr(df, 'shape'):
                print(f"形状: {df.shape}")
            if hasattr(df, 'columns'):
                print(f"列名: {list(df.columns)}")
                if not df.empty and '代码' in df.columns:
                    print(f"\n前3个代码: {df['代码'].head(3).tolist()}")

    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def debug_board_fund_flow():
    """调试板块资金流向接口"""
    print("\n" + "=" * 60)
    print("调试: stock_fund_flow_industry")
    print("=" * 60)

    try:
        import akshare as ak

        print(f"调用参数: symbol='即时'")
        df = ak.stock_fund_flow_industry(symbol="即时")

        print(f"返回类型: {type(df)}")

        if df is not None:
            print(f"是否为空: {df.empty if hasattr(df, 'empty') else 'N/A'}")
            if hasattr(df, 'shape'):
                print(f"形状: {df.shape}")
            if hasattr(df, 'columns'):
                print(f"列名: {list(df.columns)}")
                print(f"列数: {len(df.columns)}")

    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def debug_global_ths():
    """调试同花顺全球财经直播接口"""
    print("\n" + "=" * 60)
    print("调试: stock_info_global_ths")
    print("=" * 60)

    try:
        import akshare as ak

        print("调用参数: 无")
        df = ak.stock_info_global_ths()

        print(f"返回类型: {type(df)}")

        if df is not None:
            print(f"是否为空: {df.empty if hasattr(df, 'empty') else 'N/A'}")
            if hasattr(df, 'shape'):
                print(f"形状: {df.shape}")
            if hasattr(df, 'columns'):
                print(f"列名: {list(df.columns)}")
                if not df.empty:
                    print(f"\n前3条数据:")
                    for _, row in df.head(50).iterrows():
                        print(f"  [{row.get('发布时间', 'N/A')}] {row.get('标题', 'N/A')}")
                        print(f"    内容: {str(row.get('内容', ''))[:100]}...")

    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def debug_stock_zh_a_hist_pre_min_em():
    """调试 A 股盘前分钟数据接口"""
    print("\n" + "=" * 60)
    print("调试: stock_zh_a_hist_pre_min_em")
    print("=" * 60)

    try:
        import akshare as ak

        symbol = "000001"
        print(f"调用参数: symbol={symbol}")
        df = ak.stock_zh_a_hist_pre_min_em(symbol=symbol)

        print(f"返回类型: {type(df)}")

        if df is not None:
            print(f"是否为空: {df.empty if hasattr(df, 'empty') else 'N/A'}")
            if hasattr(df, 'shape'):
                print(f"形状: {df.shape}")
            if hasattr(df, 'columns'):
                print(f"列名: {list(df.columns)}")
                if not df.empty:
                    print(f"\n前3条数据:\n{df.head(100).to_string(index=False)}")

    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


_FUNCS = {
    "lhb": debug_lhb_detail,
    "fund_flow": debug_board_fund_flow,
    "global_ths": debug_global_ths,
    "pre_min": debug_stock_zh_a_hist_pre_min_em,
}

if __name__ == "__main__":
    import sys
    print("\n🔍 调试 AkShare 接口返回数据")

    targets = sys.argv[1:]  # e.g. python debug_akshare_returns.py pre_min lhb
    funcs = [_FUNCS[t] for t in targets if t in _FUNCS] or list(_FUNCS.values())
    for fn in funcs:
        fn()

    print("\n" + "=" * 60)
    print("✅ 调试完成")
