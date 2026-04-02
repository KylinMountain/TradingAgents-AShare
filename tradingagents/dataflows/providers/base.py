from abc import ABC, abstractmethod


class BaseMarketDataProvider(ABC):
    """Abstract interface for market data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier used by config routing."""
        raise NotImplementedError

    @abstractmethod
    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_indicators(
        self, symbol: str, indicator: str, curr_date: str, look_back_days: int
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_balance_sheet(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_cashflow(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_income_statement(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_global_news(
        self, curr_date: str, look_back_days: int = 7, limit: int = 50
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_insider_transactions(self, symbol: str) -> str:
        raise NotImplementedError

    def get_realtime_quotes(self, symbols: list[str]) -> str:
        """Return real-time quotes for a list of symbols as a JSON string.

        Keys are original symbols (e.g. "600519.SH"), values are dicts with:
        price, open, high, low, previous_close, change, change_pct, volume, amount.
        """
        raise NotImplementedError

