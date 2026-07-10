from typing import Dict

from .base import BaseMarketDataProvider
from .yfinance_provider import YFinanceProvider
from .alpha_vantage_provider import AlphaVantageProvider
from .china_equity_provider import CnStubProvider
from .cn_akshare_provider import CnAkshareProvider
from .cn_baostock_provider import CnBaoStockProvider
from .cn_investoday_provider import CnInvestodayProvider


class DataProviderRegistry:
    """Simple in-memory provider registry."""

    def __init__(self):
        self._providers: Dict[str, BaseMarketDataProvider] = {}

    def register(self, provider: BaseMarketDataProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, provider_name: str) -> BaseMarketDataProvider | None:
        return self._providers.get(provider_name)

    def list_names(self) -> list[str]:
        return list(self._providers.keys())


def build_default_registry() -> DataProviderRegistry:
    registry = DataProviderRegistry()
    registry.register(CnAkshareProvider())
    registry.register(CnBaoStockProvider())
    registry.register(CnInvestodayProvider())
    registry.register(YFinanceProvider())
    registry.register(AlphaVantageProvider())
    registry.register(CnStubProvider())
    return registry
