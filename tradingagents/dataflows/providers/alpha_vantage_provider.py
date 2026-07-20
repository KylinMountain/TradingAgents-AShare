from .base import BaseMarketDataProvider
from ..alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)


class AlphaVantageProvider(BaseMarketDataProvider):
    @property
    def name(self) -> str:
        return "alpha_vantage"

    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str:
        return get_alpha_vantage_stock(symbol, start_date, end_date)

    def get_indicators(
        self, symbol: str, indicator: str, curr_date: str, look_back_days: int
    ) -> str:
        return get_alpha_vantage_indicator(symbol, indicator, curr_date, look_back_days)

    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        return get_alpha_vantage_fundamentals(ticker, curr_date)

    def get_balance_sheet(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return get_alpha_vantage_balance_sheet(ticker, freq, curr_date)

    def get_cashflow(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return get_alpha_vantage_cashflow(ticker, freq, curr_date)

    def get_income_statement(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return get_alpha_vantage_income_statement(ticker, freq, curr_date)

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        return get_alpha_vantage_news(ticker, start_date, end_date)

    def get_global_news(
        self, curr_date: str, look_back_days: int = 7, limit: int = 50
    ) -> str:
        return get_alpha_vantage_global_news(curr_date, look_back_days, limit)

    def get_insider_transactions(self, symbol: str, curr_date: str = None) -> str:
        return get_alpha_vantage_insider_transactions(symbol)
