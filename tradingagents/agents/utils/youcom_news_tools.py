from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.providers.registry import _registry


@tool
def get_deep_research(
    query: Annotated[str, "Research topic or question — be specific about what to investigate"],
    research_effort: Annotated[
        str,
        "Research depth: lite (quick), standard (balanced), deep (thorough), exhaustive (most comprehensive)"
    ] = "standard",
) -> str:
    """
    Perform deep research on a topic using You.com Research API, returning a comprehensive
    markdown report with citations. Use this when you need in-depth analysis of a company,
    industry trend, market event, or any topic requiring synthesis from multiple sources.

    This tool is particularly useful for fundamental analysis, industry research,
    and investigating specific events or developments affecting a stock.
    """
    provider = _registry.get("youcom")
    if provider is None:
        return "You.com provider is not registered. Please ensure YOUCOM_API_KEY is configured."

    try:
        return provider.get_research(query, research_effort)
    except NotImplementedError:
        return "You.com deep research is not available. Please check YOUCOM_API_KEY configuration."
    except Exception as e:
        return f"You.com Research failed: {e}"
