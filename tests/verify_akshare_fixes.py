"""验证 akshare 接口修复效果"""
from datetime import datetime


def test_lhb_detail():
    """测试龙虎榜修复"""
    print("\n" + "=" * 60)
    print("测试 1: get_lhb_detail (龙虎榜)")
    print("=" * 60)

    try:
        from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider
        provider = CnAkshareProvider()

        today = datetime.now().strftime("%Y-%m-%d")
        result = provider.get_lhb_detail("600519", today)

        print(f"✅ 调用成功")
        print(f"返回长度: {len(result)} 字符")
        print(f"\n前 500 字符:\n{result[:500]}")

    except Exception as e:
        print(f"❌ 失败: {type(e).__name__}: {e}")


def test_board_fund_flow():
    """测试板块资金流向修复"""
    print("\n" + "=" * 60)
    print("测试 2: get_board_fund_flow (板块资金流向)")
    print("=" * 60)

    try:
        from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider
        provider = CnAkshareProvider()

        result = provider.get_board_fund_flow()

        print(f"✅ 调用成功")
        print(f"返回长度: {len(result)} 字符")
        print(f"\n结果:\n{result}")

    except Exception as e:
        print(f"❌ 失败: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("\n🔍 验证 AkShare 接口修复")
    print("=" * 60)

    test_lhb_detail()
    test_board_fund_flow()

    print("\n" + "=" * 60)
    print("✅ 验证完成")
    print("=" * 60)
