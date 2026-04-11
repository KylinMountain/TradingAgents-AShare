"""诊断 akshare 接口问题

检测失败的接口，判断是接口变化、参数错误还是网络问题
"""
import sys
import time


def print_section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def diagnose_stock_zh_a_spot_em():
    """诊断：A股实时行情"""
    print_section("1. 诊断 stock_zh_a_spot_em (A股实时行情)")

    try:
        import akshare as ak
        print("✓ akshare 已导入")

        # 检查方法是否存在
        if not hasattr(ak, 'stock_zh_a_spot_em'):
            print("❌ 方法不存在")
            return

        print("✓ 方法存在")
        print("⏳ 尝试调用（可能较慢）...")

        # 尝试多次调用
        for attempt in range(3):
            try:
                df = ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    print(f"✅ 第 {attempt + 1} 次调用成功")
                    print(f"   返回数据: {df.shape[0]} 行 × {df.shape[1]} 列")
                    print(f"   列名: {list(df.columns)[:10]}")
                    return
                else:
                    print(f"⚠️  第 {attempt + 1} 次调用返回空数据")
            except Exception as e:
                print(f"❌ 第 {attempt + 1} 次调用失败: {type(e).__name__}: {str(e)[:100]}")
                if attempt < 2:
                    time.sleep(2)

        print("\n💡 建议: 东方财富接口可能限流，使用 Sina 降级方案")

    except Exception as e:
        print(f"❌ 诊断失败: {type(e).__name__}: {e}")


def diagnose_stock_individual_spot_xq():
    """诊断：雪球个股实时数据"""
    print_section("2. 诊断 stock_individual_spot_xq (雪球个股实时)")

    try:
        import akshare as ak

        if not hasattr(ak, 'stock_individual_spot_xq'):
            print("❌ 方法不存在")
            return

        print("✓ 方法存在")

        # 测试不同的股票代码格式
        test_symbols = ["SH600519", "600519", "sh600519"]

        for symbol in test_symbols:
            try:
                print(f"\n⏳ 测试代码: {symbol}")
                df = ak.stock_individual_spot_xq(symbol=symbol)
                print(f"✅ 成功! 返回类型: {type(df)}")
                if hasattr(df, 'shape'):
                    print(f"   形状: {df.shape}")
                    print(f"   列名: {list(df.columns) if hasattr(df, 'columns') else 'N/A'}")
                    print(f"   前3行:\n{df.head(3)}")
                return
            except KeyError as e:
                print(f"❌ KeyError: {e}")
                print("   可能原因: 雪球 API 返回格式变化")
            except Exception as e:
                print(f"❌ {type(e).__name__}: {str(e)[:100]}")

        print("\n💡 建议: 雪球接口可能已变化，考虑移除或使用其他数据源")

    except Exception as e:
        print(f"❌ 诊断失败: {type(e).__name__}: {e}")


def diagnose_stock_board_industry_fund_flow():
    """诊断：板块资金流向"""
    print_section("3. 诊断 stock_board_industry_fund_flow_em (板块资金流向)")

    try:
        import akshare as ak

        # 搜索可能的方法名
        possible_names = [
            'stock_board_industry_fund_flow_em',
            'stock_board_industry_fund_flow',
            'stock_sector_fund_flow_em',
            'stock_sector_fund_flow_rank_em',
            'stock_board_concept_fund_flow_em',
        ]

        print("🔍 搜索可能的方法名...")
        found_methods = []
        for name in possible_names:
            if hasattr(ak, name):
                found_methods.append(name)
                print(f"✓ 找到: {name}")

        if not found_methods:
            print("❌ 未找到任何相关方法")
            print("\n🔍 搜索包含 'fund_flow' 的所有方法:")
            all_methods = [m for m in dir(ak) if 'fund_flow' in m.lower()]
            for m in all_methods[:10]:
                print(f"   - {m}")
            return

        # 测试找到的方法
        for method_name in found_methods:
            try:
                print(f"\n⏳ 测试方法: {method_name}")
                method = getattr(ak, method_name)
                df = method(symbol="即时")
                print(f"✅ 成功! 返回: {df.shape if hasattr(df, 'shape') else type(df)}")
                if hasattr(df, 'columns'):
                    print(f"   列名: {list(df.columns)[:10]}")
                return
            except TypeError as e:
                # 尝试不带参数
                try:
                    df = method()
                    print(f"✅ 成功(无参数)! 返回: {df.shape if hasattr(df, 'shape') else type(df)}")
                    return
                except Exception as e2:
                    print(f"❌ {type(e2).__name__}: {str(e2)[:100]}")
            except Exception as e:
                print(f"❌ {type(e).__name__}: {str(e)[:100]}")

    except Exception as e:
        print(f"❌ 诊断失败: {type(e).__name__}: {e}")


def diagnose_stock_lhb_detail_em():
    """诊断：龙虎榜"""
    print_section("4. 诊断 stock_lhb_detail_em (龙虎榜)")

    try:
        import akshare as ak
        from datetime import datetime

        if not hasattr(ak, 'stock_lhb_detail_em'):
            print("❌ 方法不存在")
            return

        print("✓ 方法存在")

        # 检查方法签名
        import inspect
        sig = inspect.signature(ak.stock_lhb_detail_em)
        print(f"📋 方法签名: {sig}")

        # 测试不同的参数组合
        today = datetime.now().strftime("%Y%m%d")
        test_cases = [
            {"symbol": "600519", "start_date": today, "end_date": today},
            {"stock": "600519", "start_date": today, "end_date": today},
            {"symbol": "600519"},
            {},  # 无参数
        ]

        for i, params in enumerate(test_cases, 1):
            try:
                print(f"\n⏳ 测试参数组合 {i}: {params}")
                df = ak.stock_lhb_detail_em(**params)
                print(f"✅ 成功! 返回: {df.shape if hasattr(df, 'shape') else type(df)}")
                if hasattr(df, 'columns'):
                    print(f"   列名: {list(df.columns)[:10]}")
                return
            except Exception as e:
                print(f"❌ {type(e).__name__}: {str(e)[:100]}")

        print("\n💡 建议: 检查 akshare 文档获取正确的参数名")

    except Exception as e:
        print(f"❌ 诊断失败: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("\n🔍 AkShare 接口问题诊断")
    print("=" * 80)

    try:
        import akshare
        print(f"✅ akshare 版本: {akshare.__version__}")
    except ImportError:
        print("❌ 未安装 akshare")
        sys.exit(1)

    # 运行诊断
    diagnose_stock_zh_a_spot_em()
    diagnose_stock_individual_spot_xq()
    diagnose_stock_board_industry_fund_flow()
    diagnose_stock_lhb_detail_em()

    print("\n" + "=" * 80)
    print("✅ 诊断完成")
    print("=" * 80)
