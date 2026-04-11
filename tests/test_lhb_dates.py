"""测试 stock_lhb_detail_em 不同日期的返回情况"""
from datetime import datetime, timedelta


def test_different_dates():
    """测试不同日期是否能获取到数据"""
    import akshare as ak

    # 测试最近7天的数据
    today = datetime.now()

    print("测试最近7天的龙虎榜数据：\n")

    for i in range(7):
        test_date = today - timedelta(days=i)
        date_str = test_date.strftime("%Y%m%d")

        try:
            print(f"尝试日期: {test_date.strftime('%Y-%m-%d')} ({test_date.strftime('%A')})")
            df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)

            if df is not None and not df.empty:
                print(f"  ✅ 成功! 返回 {len(df)} 条记录")
                print(f"  列名: {list(df.columns)[:5]}...")
                break
            else:
                print(f"  ⚠️  返回空数据")

        except Exception as e:
            print(f"  ❌ 错误: {type(e).__name__}: {str(e)[:80]}")

        print()


def test_api_response():
    """直接查看 API 响应"""
    import requests

    print("\n直接测试东方财富 API：\n")

    # 这是 akshare 内部使用的 API 端点（需要查看源码确认）
    # 先尝试获取 akshare 的请求 URL

    try:
        import akshare as ak
        import inspect

        # 获取函数源码
        source = inspect.getsource(ak.stock_lhb_detail_em)

        # 查找 URL
        if "http" in source:
            print("找到 API URL:")
            for line in source.split('\n'):
                if 'http' in line.lower():
                    print(f"  {line.strip()}")

    except Exception as e:
        print(f"无法获取源码: {e}")


if __name__ == "__main__":
    test_different_dates()
    test_api_response()
