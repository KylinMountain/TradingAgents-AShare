"""You.com Search and Research API integration."""

import requests

from tradingagents.dataflows.config import get_config


YOUCOM_SEARCH_URL = "https://ydc-index.io/v1/search"
YOUCOM_RESEARCH_URL = "https://ydc-index.io/v1/research"


def _get_api_key() -> str:
    return get_config().get("youcom_api_key", "").strip()


def _post(url: str, payload: dict, timeout: int = 30) -> requests.Response:
    api_key = _get_api_key()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["X-API-Key"] = api_key
    return requests.post(url, headers=headers, json=payload, timeout=timeout)


def search_news(query: str, count: int = 10) -> str:
    """
    Search news using You.com Search API.

    Args:
        query: Search query string
        count: Number of results (1-20)

    Returns:
        Formatted string of search results or error message
    """
    if not query or not query.strip():
        return "Search query cannot be empty"

    if not _get_api_key():
        return "You.com Search API requires YOUCOM_API_KEY environment variable"

    try:
        response = _post(
            YOUCOM_SEARCH_URL,
            {"query": query, "count": min(max(count, 1), 20)},
            timeout=30,
        )
    except Exception as e:
        return f"You.com Search request failed: {e}"

    if response.status_code == 429:
        return "You.com Search rate limit exceeded (429)"
    if response.status_code == 401:
        return "You.com API Key is invalid or expired"
    if response.status_code == 403:
        return "You.com API Key has insufficient permissions"
    if response.status_code != 200:
        return f"You.com Search request failed (Status {response.status_code})"

    try:
        data = response.json()
    except Exception:
        return "You.com Search returned non-JSON response"

    results = data.get("results", [])
    if not results:
        return f"No results found for: {query}"

    lines = []
    for i, item in enumerate(results[:count], 1):
        title = item.get("title", f"Result {i}")
        url = item.get("url", "")
        snippets = item.get("snippets", [])
        snippet = snippets[0] if isinstance(snippets, list) and snippets else item.get("description", "")
        lines.append(f"[{i}] {title}\n   URL: {url}\n   Summary: {snippet}")

    return "\n\n".join(lines)


def research_news(query: str, research_effort: str = "standard") -> str:
    """
    Perform deep research using You.com Research API.

    Args:
        query: Research topic or question
        research_effort: One of lite, standard, deep, exhaustive (default: standard)

    Returns:
        Markdown-formatted research report with citations or error message
    """
    if not query or not query.strip():
        return "Research query cannot be empty"

    if not _get_api_key():
        return "You.com Research API requires YOUCOM_API_KEY environment variable"

    allowed = {"lite", "standard", "deep", "exhaustive"}
    if research_effort not in allowed:
        research_effort = "standard"

    try:
        response = _post(
            YOUCOM_RESEARCH_URL,
            {"input": query, "research_effort": research_effort},
            timeout=120,
        )
    except Exception as e:
        return f"You.com Research request failed: {e}"

    if response.status_code == 429:
        return "You.com Research rate limit exceeded (429)"
    if response.status_code == 401:
        return "You.com API Key is invalid or expired"
    if response.status_code == 403:
        return "You.com API Key has insufficient permissions"
    if response.status_code != 200:
        return f"You.com Research request failed (Status {response.status_code})"

    try:
        data = response.json()
    except Exception:
        return "You.com Research returned non-JSON response"

    content = data.get("content", "")
    sources = data.get("sources", [])

    lines = []
    if content:
        lines.append(f"## Research Summary\n\n{content}")
    if sources:
        lines.append("\n## References\n")
        for i, source in enumerate(sources, 1):
            snippets = source.get("snippets", [])
            snippet = snippets[0] if isinstance(snippets, list) and snippets else ""
            title = source.get("title", "Unknown source")
            url = source.get("url", "")
            lines.append(f"[{i}] {title}\n   URL: {url}\n   Summary: {snippet}")

    return "\n".join(lines) if lines else "No research results returned"
