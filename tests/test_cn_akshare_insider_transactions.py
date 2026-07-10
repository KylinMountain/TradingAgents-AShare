import pandas as pd

from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider


class _EmptyAkshareClient:
    def stock_main_stock_holder(self, stock):
        return pd.DataFrame()


class _NewsFallbackProvider(CnAkshareProvider):
    def __init__(self):
        self.news_calls = []

    def _ak(self):
        return _EmptyAkshareClient()

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        self.news_calls.append((ticker, start_date, end_date))
        return "fallback news"


def test_insider_transactions_fallback_uses_analysis_date_window():
    provider = _NewsFallbackProvider()

    result = provider.get_insider_transactions("600519.SH", curr_date="2024-01-15")

    assert "fallback news" in result
    assert provider.news_calls == [("600519.SH", "2024-01-01", "2024-01-15")]
