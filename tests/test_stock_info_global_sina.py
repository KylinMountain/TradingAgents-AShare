"""测试 stock_info_global_sina 接口"""
import requests
import pandas as pd


def test_stock_info_global_sina_basic():
    """测试基本调用（akshare 封装）"""
    import akshare as ak

    print("=" * 60)
    print("测试 1: akshare 基本调用")
    print("=" * 60)

    try:
        df = ak.stock_info_global_sina()

        print(f"✅ 成功!")
        print(f"返回类型: {type(df)}")
        print(f"形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        print(f"\n前5条快讯:\n{df.head()}")

    except Exception as e:
        print(f"❌ 失败: {type(e).__name__}")
        print(f"错误信息: {str(e)[:200]}")


def test_stock_info_global_sina_with_params(page="1", page_size="20", zhibo_id="152", tag_id="0"):
    """测试扩展参数（直接调用 API）

    Args:
        page: 页码，默认 "1"
        page_size: 每页数量，默认 "20"
        zhibo_id: 直播ID，默认 "152"（财经）
        tag_id: 标签ID，默认 "0"（全部）
    """
    print("\n" + "=" * 60)
    print(f"测试 2: 扩展参数调用 (page={page}, page_size={page_size})")
    print("=" * 60)

    url = "https://zhibo.sina.com.cn/api/zhibo/feed"
    params = {
        "page": page,
        "page_size": page_size,
        "zhibo_id": zhibo_id,
        "tag_id": tag_id,
        "dire": "f",
        "dpc": "1",
        "pagesize": page_size,
        "type": "1",
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data_json = r.json()

        time_list = [
            item["create_time"] for item in data_json["result"]["data"]["feed"]["list"]
        ]
        text_list = [
            item["rich_text"] for item in data_json["result"]["data"]["feed"]["list"]
        ]
        temp_df = pd.DataFrame([time_list, text_list]).T
        temp_df.columns = ["时间", "内容"]

        print(f"✅ 成功!")
        print(f"返回形状: {temp_df.shape}")
        print(f"列名: {list(temp_df.columns)}")
        print(f"\n前3条快讯:\n{temp_df.head(3)}")

        return temp_df

    except Exception as e:
        print(f"❌ 失败: {type(e).__name__}")
        print(f"错误信息: {str(e)[:200]}")
        return None


def test_different_params():
    """测试不同参数组合"""
    print("\n" + "=" * 60)
    print("测试 3: 不同参数组合")
    print("=" * 60)

    # 测试不同页码
    test_cases = [
        # {"page": "1", "page_size": "10", "desc": "第1页，10条，tag_id=0（全部）", "tag_id": "0"},
        # {"page": "2", "page_size": "10", "desc": "第2页，10条，tag_id=0（全部）", "tag_id": "1"},
        {"page": "1", "page_size": "50", "desc": "第1页，50条，tag_id=1", "tag_id": "1,4,5"},
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {case['desc']}")
        print("-" * 60)
        df = test_stock_info_global_sina_with_params(
            page=case["page"],
            page_size=case["page_size"],
            tag_id=case["tag_id"],
        )
        if df is not None:
            print(f"实际返回: {len(df)} 条记录")


def test_get_global_news():
    """直接测试 CnAkshareProvider.get_global_news"""
    import datetime
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider

    print("\n" + "=" * 60)
    print("测试 4: CnAkshareProvider.get_global_news")
    print("=" * 60)

    provider = CnAkshareProvider()
    curr_date = datetime.date.today().strftime("%Y-%m-%d")
    print(f"调用参数: curr_date={curr_date}")

    try:
        result = provider.get_global_news(curr_date)
        print(f"返回类型: {type(result)}")
        print(f"字符数: {len(result)}")
        print(f"开头: {repr(result[:50])}")

        if result.startswith("## "):
            print("✅ 成功！返回正常新闻内容")
            print(f"\n前300字:\n{result[:300]}")
        else:
            print(f"❌ 返回异常内容: {result[:200]}")
    except Exception as e:
        print(f"❌ 异常: {type(e).__name__}: {e}")


if __name__ == "__main__":
    import sys
    _funcs = {
        "basic": test_stock_info_global_sina_basic,
        "params": test_stock_info_global_sina_with_params,
        "different": test_different_params,
        "global_news": test_get_global_news,
    }
    targets = sys.argv[1:]
    funcs = [_funcs[t] for t in targets if t in _funcs] or list(_funcs.values())
    for fn in funcs:
        fn()
