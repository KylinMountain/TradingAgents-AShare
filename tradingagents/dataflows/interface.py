import os

from .alpha_vantage_common import AlphaVantageRateLimitError
from .config import get_config
from .providers import build_default_registry

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": ["get_stock_data"],
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": ["get_indicators"],
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
        ],
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ],
    },
    "realtime_data": {
        "description": "Real-time market quotes",
        "tools": ["get_realtime_quotes"],
    },
    "cn_market_data": {
        "description": "China A-share market sentiment and fund flow data",
        "tools": [
            "get_board_fund_flow",
            "get_individual_fund_flow",
            "get_lhb_detail",
            "get_zt_pool",
            "get_hot_stocks_xq",
        ],
    },
}

_registry = build_default_registry()

VENDOR_LIST = _registry.list_names()


def _is_trace_enabled() -> bool:
    env_value = os.getenv("TA_TRACE")
    if env_value is not None:
        return env_value.strip().lower() in ("1", "true", "yes", "on")

    config = get_config()
    return bool(config.get("provider_trace", True))


def _trace(msg: str) -> None:
    if _is_trace_enabled():
        print(f"[provider-trace] {msg}", flush=True)


_TRACE_KEYS = ("symbol", "ticker", "start_date", "end_date", "curr_date", "indicator")


def _summarize_args(args: tuple, kwargs: dict) -> str:
    """格式化首参数（通常是 symbol）和常见日期/指标键，用于 trace 日志定位。"""
    parts = []
    if args:
        # 约定：所有 provider 方法首参数为 symbol/ticker
        parts.append(f"symbol={args[0]!r}")
        if len(args) >= 2:
            parts.append(f"arg2={args[1]!r}")
        if len(args) >= 3:
            parts.append(f"arg3={args[2]!r}")
    for k, v in kwargs.items():
        if k in _TRACE_KEYS:
            parts.append(f"{k}={v!r}")
    return " ".join(parts)


def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")


def get_vendor(category: str, method: str = None) -> str:
    """Get configured vendor for category or tool method."""
    config = get_config()

    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    return config.get("data_vendors", {}).get(category, "yfinance")


def _resolve_vendor_chain(method: str, configured_vendor: str) -> list[str]:
    configured = [v.strip() for v in configured_vendor.split(",") if v.strip()]
    fallback = configured.copy()

    for provider_name in _registry.list_names():
        if provider_name in fallback:
            continue
        provider = _registry.get(provider_name)
        # 占位 provider（如 cn_stub）不自动追加进 fallback chain，
        # 避免污染日志和兜底链；用户显式配置仍可强制使用。
        if getattr(provider, "is_placeholder", False):
            continue
        fallback.append(provider_name)

    return fallback


def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to provider implementations with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    fallback_vendors = _resolve_vendor_chain(method, vendor_config)
    args_summary = _summarize_args(args, kwargs)
    last_exc = None
    _trace(
        f"method={method} {args_summary} category={category} "
        f"configured='{vendor_config}' chain={fallback_vendors}"
    )

    for vendor in fallback_vendors:
        provider = _registry.get(vendor)
        if provider is None:
            _trace(f"method={method} {args_summary} vendor={vendor} status=skip reason=not-registered")
            continue

        impl_func = getattr(provider, method, None)
        if impl_func is None:
            _trace(f"method={method} {args_summary} vendor={vendor} status=skip reason=not-implemented")
            continue

        try:
            result = impl_func(*args, **kwargs)
            _trace(f"method={method} {args_summary} vendor={vendor} status=hit")
            return result
        except (AlphaVantageRateLimitError, NotImplementedError) as exc:
            last_exc = exc
            # Try next provider for transient/routing issues or placeholder providers.
            _trace(
                f"method={method} {args_summary} vendor={vendor} status=fallback "
                f"reason={type(exc).__name__}: {exc}"
            )
            continue
        except Exception as exc:
            # Provider-specific runtime/parsing errors (e.g., schema changes, KeyError)
            # should not terminate the full chain; fall through to next vendor.
            last_exc = exc
            _trace(
                f"method={method} {args_summary} vendor={vendor} status=fallback "
                f"reason={type(exc).__name__}: {exc}"
            )
            continue

    _trace(f"method={method} {args_summary} status=failed reason=no-available-vendor")
    if last_exc is not None:
        raise RuntimeError(
            f"No available vendor for method '{method}'. "
            f"Configured chain: {fallback_vendors}. "
            f"Last error: {type(last_exc).__name__}: {last_exc}"
        ) from last_exc
    raise RuntimeError(
        f"No available vendor for method '{method}'. "
        f"Configured chain: {fallback_vendors}"
    )
