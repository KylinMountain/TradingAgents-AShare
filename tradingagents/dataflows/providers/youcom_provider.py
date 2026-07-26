from .base import BaseMarketDataProvider
from .. import youcom_news


class YoucomProvider(BaseMarketDataProvider):
    """You.com data provider using You.com Search and Research APIs."""

    @property
    def name(self) -> str:
        return "youcom"

    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str:
        # Not implemented — use You.com Search for news, not stock price data
        raise NotImplementedError("YoucomProvider does not support stock price data")

    def get_indicators(
        self, symbol: str, indicator: str, curr_date: str, look_back_days: int
    ) -> str:
        raise NotImplementedError("YoucomProvider does not support technical indicators")

    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        raise NotImplementedError("YoucomProvider does not support fundamental data")

    def get_balance_sheet(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        raise NotImplementedError("YoucomProvider does not support balance sheet data")

    def get_cashflow(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        raise NotImplementedError("YoucomProvider does not support cashflow data")

    def get_income_statement(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        raise NotImplementedError("YoucomProvider does not support income statement data")

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        query = f"{ticker} stock news {start_date} to {end_date}"
        return youcom_news.search_news(query, count=10)

    def get_global_news(
        self, curr_date: str, look_back_days: int = 7, limit: int = 10
    ) -> str:
        from datetime import datetime, timedelta
        try:
            end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=look_back_days)
        start_str = start_dt.strftime("%Y-%m-%d")

        query = f"global markets economy Federal Reserve inflation {start_str} to {curr_date}"
        return youcom_news.search_news(query, count=limit)

    def get_insider_transactions(self, symbol: str, curr_date: str = None) -> str:
        raise NotImplementedError("YoucomProvider does not support insider transactions")

    def get_realtime_quotes(self, symbols: list[str]) -> str:
        raise NotImplementedError("YoucomProvider does not support realtime quotes")

    # ── Extended methods not in BaseMarketDataProvider ──

    def get_research(self, query: str, research_effort: str = "standard") -> str:
        """
        Perform deep research using You.com Research API.

        Args:
            query: Research topic or question
            research_effort: lite, standard, deep, or exhaustive

        Returns:
            Markdown-formatted research report with citations
        """
        return youcom_news.research_news(query, research_effort)
