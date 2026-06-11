from .base import BaseMarketDataProvider
from ..y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from ..yfinance_news import get_news_yfinance, get_global_news_yfinance


class YFinanceProvider(BaseMarketDataProvider):
    @property
    def name(self) -> str:
        return "yfinance"

    def _normalize_symbol(self, symbol: str) -> str:
        s = symbol.strip().upper()
        # yfinance uses .SS for Shanghai and .SZ for Shenzhen.
        if s.endswith(".SH"):
            return s[:-3] + ".SS"
        return s

    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str:
        return get_YFin_data_online(self._normalize_symbol(symbol), start_date, end_date)

    def get_indicators(
        self, symbol: str, indicator: str, curr_date: str, look_back_days: int
    ) -> str:
        return get_stock_stats_indicators_window(
            self._normalize_symbol(symbol), indicator, curr_date, look_back_days
        )

    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        return get_yfinance_fundamentals(self._normalize_symbol(ticker), curr_date)

    def get_balance_sheet(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return get_yfinance_balance_sheet(self._normalize_symbol(ticker), freq, curr_date)

    def get_cashflow(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return get_yfinance_cashflow(self._normalize_symbol(ticker), freq, curr_date)

    def get_income_statement(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return get_yfinance_income_statement(self._normalize_symbol(ticker), freq, curr_date)

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        return get_news_yfinance(self._normalize_symbol(ticker), start_date, end_date)

    def get_global_news(
        self, curr_date: str, look_back_days: int = 7, limit: int = 50
    ) -> str:
        return get_global_news_yfinance(curr_date, look_back_days, limit)

    def get_insider_transactions(self, symbol: str, curr_date: str = None) -> str:
        return get_yfinance_insider_transactions(self._normalize_symbol(symbol))
