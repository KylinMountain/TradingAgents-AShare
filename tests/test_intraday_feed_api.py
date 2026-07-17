"""API tests for GET /v1/intraday/feed using FastAPI TestClient."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from api.database import IntradaySignalDB, get_db_ctx


def _get_client():
    from api.main import app
    return TestClient(app, raise_server_exceptions=False)


def _auth_unique(client: TestClient) -> str:
    """Same helper as tests/test_api_smoke.py — avoids the email/dev-code
    flow (flaky in sandboxes without SMTP) by creating the user directly."""
    from api.database import UserDB, get_db_ctx, init_db
    from api.services import auth_service

    init_db()
    email = auth_service.normalize_email(f"intraday-{uuid4().hex[:8]}@test.com")
    now = datetime.now(timezone.utc)
    with get_db_ctx() as db:
        user = auth_service.get_user_by_email(db, email)
        if not user:
            user = UserDB(id=str(uuid4()), email=email, is_active=True, created_at=now, updated_at=now, last_login_at=now)
            db.add(user)
            db.commit()
            db.refresh(user)
    return auth_service.create_access_token(user)


def _insert_signal(**overrides) -> IntradaySignalDB:
    defaults = dict(
        id=uuid4().hex,
        trade_date="2026-07-10",
        board_name="CRO概念",
        anomaly_case="A",
        change_pct=4.43,
        net_inflow=19.56,
        cause_summary="test cause",
        fund_source="机构",
        judgement="持续行情",
        llm_failed=False,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    with get_db_ctx() as db:
        row = IntradaySignalDB(**defaults)
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
    return row


def test_intraday_feed_requires_auth():
    client = _get_client()
    r = client.get("/v1/intraday/feed")
    assert r.status_code == 401


def test_intraday_feed_returns_items_newest_first():
    client = _get_client()
    token = _auth_unique(client)
    headers = {"Authorization": f"Bearer {token}"}

    now = datetime.now(timezone.utc)
    older = _insert_signal(board_name=f"旧板块-{uuid4().hex[:6]}", created_at=now - timedelta(minutes=10))
    newer = _insert_signal(board_name=f"新板块-{uuid4().hex[:6]}", created_at=now)

    r = client.get("/v1/intraday/feed", headers=headers)
    assert r.status_code == 200
    body = r.json()
    ids = [item["id"] for item in body["items"]]
    assert ids.index(newer.id) < ids.index(older.id)


def test_intraday_feed_created_at_includes_utc_offset():
    # Regression: IntradaySignalDB.created_at is a plain Column(DateTime),
    # which silently strips tzinfo on SQLite round-trip. A naive isoformat()
    # string (no 'Z'/offset) gets parsed as *local* time by the frontend's
    # `new Date(iso)`, displaying every signal's time 8h off in Beijing.
    client = _get_client()
    token = _auth_unique(client)
    headers = {"Authorization": f"Bearer {token}"}

    row = _insert_signal(board_name=f"时区板块-{uuid4().hex[:6]}")

    r = client.get("/v1/intraday/feed", headers=headers, params={"limit": 1})
    assert r.status_code == 200
    created_at = r.json()["items"][0]["created_at"]
    assert created_at.endswith("+00:00") or created_at.endswith("Z"), created_at
    assert datetime.fromisoformat(created_at).tzinfo is not None


def test_intraday_feed_llm_failed_signal_has_null_fund_source():
    client = _get_client()
    token = _auth_unique(client)
    headers = {"Authorization": f"Bearer {token}"}

    row = _insert_signal(
        board_name=f"降级板块-{uuid4().hex[:6]}", fund_source=None, judgement=None, llm_failed=True, cause_summary="仅原始异动"
    )

    r = client.get("/v1/intraday/feed", headers=headers, params={"limit": 1})
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["id"] == row.id
    assert item["llm_failed"] is True
    assert item["fund_source"] is None
