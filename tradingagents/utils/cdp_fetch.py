"""CDP bridge: route EastMoney API calls through local Chrome to bypass TLS fingerprinting.

Usage:
    from tradingagents.utils.cdp_fetch import cdp_fetch_json, is_cdp_available
    if is_cdp_available():
        data = cdp_fetch_json("https://push2.eastmoney.com/api/qt/clist/get?...")

Requires Chrome running with --remote-debugging-port=9222 --remote-allow-origins=*
"""

import json
import logging
import time
from http.client import HTTPConnection
from threading import Lock

import websocket

logger = logging.getLogger(__name__)

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222
_TIMEOUT = 20
_LOCK = Lock()
_CDP_AVAILABLE = None  # None = not checked, True/False = checked result


def _cdp(method: str, path: str) -> dict:
    conn = HTTPConnection(CDP_HOST, CDP_PORT, timeout=3)
    conn.request(method, path)
    resp = conn.getresponse()
    body = resp.read().decode()
    conn.close()
    return json.loads(body)


def is_cdp_available() -> bool:
    """Check if CDP Chrome is running and accessible."""
    global _CDP_AVAILABLE
    if _CDP_AVAILABLE is not None:
        return _CDP_AVAILABLE
    try:
        tabs = _cdp("GET", "/json/list")
        _CDP_AVAILABLE = isinstance(tabs, list) and len(tabs) > 0
    except Exception:
        _CDP_AVAILABLE = False
    return _CDP_AVAILABLE


def _create_dedicated_tab() -> str:
    """Create a dedicated hidden tab for CDP fetching. Never reuse user tabs."""
    new_tab = _cdp("PUT", "/json/new?url=about:blank")
    time.sleep(1)
    return new_tab["webSocketDebuggerUrl"]


def _close_tab(ws_url: str) -> None:
    """Close a CDP tab by its WebSocket URL."""
    try:
        tabs = _cdp("GET", "/json/list")
        for tab in tabs:
            if tab.get("webSocketDebuggerUrl") == ws_url:
                _cdp("GET", f"/json/close/{tab['id']}")
                return
    except Exception:
        pass


def _recv_msg(ws, deadline: float) -> dict | None:
    while time.time() < deadline:
        try:
            ws.settimeout(max(0.1, deadline - time.time()))
            return json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        except Exception:
            return None
    return None


def _wait_for(ws, check, deadline: float) -> dict | None:
    while time.time() < deadline:
        msg = _recv_msg(ws, deadline)
        if msg is None:
            return None
        if check(msg):
            return msg
    return None


def cdp_fetch_json(url: str, wait_ms: int = 3000) -> dict:
    """Fetch JSON from a URL through the browser's CDP connection.

    Creates a dedicated hidden tab for each request — never touches user tabs.
    The tab is closed after the fetch completes.
    Returns the parsed JSON response, or None if the response is not valid JSON.
    """
    with _LOCK:
        ws_url = _create_dedicated_tab()
        ws = websocket.create_connection(ws_url, timeout=_TIMEOUT)

        try:
            # Enable Page domain
            ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
            _recv_msg(ws, time.time() + 5)

            # Navigate
            ws.send(json.dumps({"id": 2, "method": "Page.navigate", "params": {"url": url}}))
            nav_resp = _wait_for(ws, lambda m: m.get("id") == 2, time.time() + 10)
            if nav_resp and nav_resp.get("result", {}).get("errorText"):
                return None

            # Wait for load
            load_resp = _wait_for(ws, lambda m: m.get("method") == "Page.loadEventFired", time.time() + _TIMEOUT)
            if not load_resp:
                return None

            time.sleep(wait_ms / 1000)

            # Extract JSON from body
            ws.send(json.dumps({
                "id": 3,
                "method": "Runtime.evaluate",
                "params": {"expression": "document.body.innerText", "returnByValue": True},
            }))
            eval_resp = _wait_for(ws, lambda m: m.get("id") == 3, time.time() + 10)
            if not eval_resp:
                return None

            text = eval_resp["result"]["result"]["value"]
            if not text:
                return None
            return json.loads(text)
        except Exception as e:
            logger.warning(f"CDP fetch failed for {url[:100]}: {e}")
            return None
        finally:
            ws.close()
            _close_tab(ws_url)
