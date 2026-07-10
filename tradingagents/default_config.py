import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TA_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": os.getenv("TA_LLM_PROVIDER", "openai"),
    "deep_think_llm": os.getenv("TA_LLM_DEEP", "gpt-4o"),
    "quick_think_llm": os.getenv("TA_LLM_QUICK", "gpt-4o-mini"),
    "backend_url": os.getenv("TA_BASE_URL", "https://api.openai.com/v1"),
    "api_key": os.getenv("TA_API_KEY", ""),
    
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    
    # Debate and discussion settings
    "max_debate_rounds": int(os.getenv("TA_MAX_DEBATE") or "2"),
    "max_risk_discuss_rounds": int(os.getenv("TA_MAX_RISK") or "1"),
    "max_recur_limit": 100,
    
    # Prompt language control: zh, en, or auto
    "prompt_language": os.getenv("TA_LANGUAGE", "zh"),
    "prompt_language_by_provider": {},
    
    # Provider routing trace logs
    "provider_trace": os.getenv("TA_TRACE", "1").lower() in ("1", "true", "yes", "on"),
    
    # Data vendor configuration
    "investoday_api_key": os.getenv("INVESTODAY_API_KEY", "").strip(),
    "investoday_base_url": (
        os.getenv("INVESTODAY_BASE_URL", "https://data-api.investoday.net/data").strip()
    ),
    "data_vendors": {
        "core_stock_apis": "cn_akshare,cn_baostock,cn_investoday,yfinance",
        "technical_indicators": "cn_akshare,cn_baostock,cn_investoday,yfinance",
        "fundamental_data": "cn_akshare,cn_baostock,cn_investoday,yfinance",
        "news_data": "cn_akshare,cn_baostock,cn_investoday,yfinance",
        "realtime_data": "cn_akshare,cn_investoday",
    },
    "tool_vendors": {},
}
