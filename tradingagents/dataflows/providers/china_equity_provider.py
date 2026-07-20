from .base import BaseMarketDataProvider


class CnStubProvider(BaseMarketDataProvider):
    """Placeholder provider for CN market data integrations."""

    is_placeholder = True

    @property
    def name(self) -> str:
        return "cn_stub"

    def _not_implemented(self) -> str:
        raise NotImplementedError(
            "Provider 'cn_stub' is a placeholder. "
            "Use concrete provider names like 'cn_akshare' or 'cn_tushare'."
        )

    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str:
        return self._not_implemented()

    def get_indicators(
        self, symbol: str, indicator: str, curr_date: str, look_back_days: int
    ) -> str:
        return self._not_implemented()

    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        return self._not_implemented()

    def get_balance_sheet(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return self._not_implemented()

    def get_cashflow(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return self._not_implemented()

    def get_income_statement(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return self._not_implemented()

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        return self._not_implemented()

    def get_global_news(
        self, curr_date: str, look_back_days: int = 7, limit: int = 50
    ) -> str:
        return self._not_implemented()

    def get_insider_transactions(self, symbol: str, curr_date: str = None) -> str:
        return self._not_implemented()
