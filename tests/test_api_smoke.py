"""API smoke tests using FastAPI TestClient (no external server needed).

Covers:
1. AnalyzeRequest schema — query field exists, symbol optional
2. /v1/analyze dry_run — legacy single-horizon path works
3. /v1/analyze with query field — schema accepts it, dry_run still short-circuits
4. /v1/chat/completions — unrecognizable stock returns 400
5. /v1/chat/completions — valid stock dry_run completes job
6. /v1/jobs/{id}/result — completed job returns result
"""
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Schema-only test (no server needed)
# ---------------------------------------------------------------------------

class TestAnalyzeRequestSchema:
    def test_query_field_exists_and_optional(self):
        from api.main import AnalyzeRequest
        # query defaults to None
        req = AnalyzeRequest(symbol="600519.SH")
        assert req.query is None

    def test_query_field_accepts_string(self):
        from api.main import AnalyzeRequest
        req = AnalyzeRequest(symbol="600519.SH", query="分析贵州茅台短线机会")
        assert req.query == "分析贵州茅台短线机会"

    def test_symbol_is_optional(self):
        from api.main import AnalyzeRequest
        # should not raise
        req = AnalyzeRequest()
        assert req.symbol == ""

    def test_dry_run_defaults_false(self):
        from api.main import AnalyzeRequest
        req = AnalyzeRequest(symbol="600519.SH")
        assert req.dry_run is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client():
    """Create a TestClient for the FastAPI app."""
    from api.main import app
    return TestClient(app, raise_server_exceptions=False)


def _auth(client: TestClient) -> str:
    """Register a test user and return a valid JWT token."""
    r = client.post("/v1/auth/request-code", json={"email": "apitest@test.com"})
    code = r.json()["dev_code"]
    r2 = client.post("/v1/auth/verify-code", json={"email": "apitest@test.com", "code": code})
    return r2.json()["access_token"]


def _wait_job(client: TestClient, token: str, job_id: str, timeout: float = 5.0) -> dict:
    """Poll until job is no longer running, return result dict."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
        status = r.json().get("status")
        if status in ("completed", "failed"):
            break
        time.sleep(0.2)
    r2 = client.get(f"/v1/jobs/{job_id}/result", headers={"Authorization": f"Bearer {token}"})
    return r2.json()


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

class TestAnalyzeEndpoint:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = _get_client()
        self.token = _auth(self.client)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_dry_run_completes(self):
        """Legacy path: symbol + dry_run → completed immediately."""
        r = self.client.post("/v1/analyze", headers=self.headers, json={
            "symbol": "600519.SH",
            "trade_date": "2024-01-15",
            "dry_run": True,
        })
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        result = _wait_job(self.client, self.token, job_id)
        assert result["status"] == "completed"
        assert result["decision"] == "DRY_RUN"
        assert result["result"]["symbol"] == "600519.SH"

    def test_query_field_accepted_with_dry_run(self):
        """query field is accepted by schema; dry_run still short-circuits before LLM."""
        r = self.client.post("/v1/analyze", headers=self.headers, json={
            "symbol": "600519.SH",
            "trade_date": "2024-01-15",
            "query": "分析贵州茅台短线机会，关注量价关系",
            "dry_run": True,
        })
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        result = _wait_job(self.client, self.token, job_id)
        assert result["status"] == "completed"
        assert result["decision"] == "DRY_RUN"

    def test_missing_symbol_accepted_by_schema(self):
        """symbol is optional in schema; job is created (may fail later without LLM, but 200 on submit)."""
        r = self.client.post("/v1/analyze", headers=self.headers, json={
            "trade_date": "2024-01-15",
            "dry_run": True,
        })
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_requires_auth(self):
        """Unauthenticated request returns 401/403."""
        r = self.client.post("/v1/analyze", json={
            "symbol": "600519.SH", "dry_run": True,
        })
        assert r.status_code in (401, 403)

    def test_selected_analysts_field(self):
        """selected_analysts are echoed back in dry_run result."""
        r = self.client.post("/v1/analyze", headers=self.headers, json={
            "symbol": "600519.SH",
            "selected_analysts": ["market", "news"],
            "dry_run": True,
        })
        job_id = r.json()["job_id"]
        result = _wait_job(self.client, self.token, job_id)
        assert result["result"]["selected_analysts"] == ["market", "news"]


class TestChatCompletionsEndpoint:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = _get_client()
        self.token = _auth(self.client)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_unrecognizable_stock_returns_error(self):
        """Non-stock text returns 400 with Chinese error message."""
        # Mock the LLM used for stock extraction to return no stock
        with patch("api.main._ai_extract_symbol_and_date", return_value=(None, None, ["short"])):
            r = self.client.post("/v1/chat/completions", headers=self.headers, json={
                "messages": [{"role": "user", "content": "今天天气真好"}],
                "stream": False,
                "dry_run": True,
            })
        assert r.status_code == 400
        assert "识别" in r.json()["detail"]

    def test_valid_stock_dry_run_creates_job(self):
        """Valid stock message with dry_run creates and completes a job."""
        with patch("api.main._ai_extract_symbol_and_date", return_value=("600519.SH", "2024-01-15", ["short"])):
            r = self.client.post("/v1/chat/completions", headers=self.headers, json={
                "messages": [{"role": "user", "content": "分析600519短线机会"}],
                "stream": False,
                "dry_run": True,
            })
        assert r.status_code == 200
        body = r.json()
        # Non-stream returns OpenAI-compatible format with job_id embedded in content
        assert "choices" in body
        content = body["choices"][0]["message"]["content"]
        # Extract job_id from content (format: "已启动分析任务：<job_id>")
        job_id = body["id"].replace("chatcmpl-", "")
        result = _wait_job(self.client, self.token, job_id)
        assert result["status"] == "completed"
        assert result["decision"] == "DRY_RUN"

    def test_requires_auth(self):
        r = self.client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "分析600519"}],
            "stream": False,
        })
        assert r.status_code in (401, 403)


class TestOpenAPISchema:
    def test_analyze_request_has_query_field(self):
        client = _get_client()
        r = client.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()["components"]["schemas"]["AnalyzeRequest"]
        assert "query" in schema["properties"]

    def test_analyze_request_symbol_not_required(self):
        client = _get_client()
        r = client.get("/openapi.json")
        schema = r.json()["components"]["schemas"]["AnalyzeRequest"]
        assert "symbol" not in schema.get("required", [])

    def test_healthz(self):
        client = _get_client()
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
