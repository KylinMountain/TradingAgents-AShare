"""查看昨天实际在龙虎榜上的股票"""


def show_actual_lhb_stocks():
    """显示昨天实际的龙虎榜股票"""
    import akshare as ak
    from datetime import datetime, timedelta

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    print(f"查看 {yesterday} 的龙虎榜股票：\n")

    df = ak.stock_lhb_detail_em(start_date=yesterday, end_date=yesterday)

    if df is not None and not df.empty:
        print(f"共 {len(df)} 只股票上榜\n")
        print("前 10 只股票：")
        print(df[['代码', '名称', '上榜日', '解读']].head(10).to_string(index=False))

        # 测试第一只股票
        first_code = df.iloc[0]['代码']
        print(f"\n\n现在测试第一只股票: {first_code}")

        from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider
        provider = CnAkshareProvider()

        yesterday_fmt = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = provider.get_lhb_detail(first_code, yesterday_fmt)

        print(f"\n返回结果:\n{result}")


if __name__ == "__main__":
    show_actual_lhb_stocks()
