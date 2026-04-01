import asyncio
import sys
import types
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, UserDB
from api.services import scheduled_service


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _auth_unique(client: TestClient) -> str:
    from api.database import get_db_ctx, init_db
    from api.services import auth_service

    init_db()
    email = auth_service.normalize_email(f"qmt-import-{uuid4().hex[:8]}@test.com")
    now = datetime.now(timezone.utc)
    with get_db_ctx() as db:
        user = auth_service.get_user_by_email(db, email)
        if not user:
            user = UserDB(
                id=str(uuid4()),
                email=email,
                is_active=True,
                created_at=now,
                updated_at=now,
                last_login_at=now,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    return auth_service.create_access_token(user)


class _FakeXtPosition:
    def __init__(self, stock_code, volume, can_use_volume, open_price, market_value, instrument_name=None):
        self.stock_code = stock_code
        self.volume = volume
        self.can_use_volume = can_use_volume
        self.open_price = open_price
        self.market_value = market_value
        self.instrument_name = instrument_name


class _FakeXtQuantTrader:
    def __init__(self, path, session, callback=None):
        self.path = path
        self.session = session
        self.callback = callback
        self.started = False
        self.stopped = False
        self.connected = False

    def start(self):
        self.started = True

    def connect(self):
        self.connected = True
        return 0

    def query_stock_positions(self, account):
        assert account.account_id == "demo-account"
        return [
            _FakeXtPosition("600519.SH", 500, 500, 1700.0, 850000.0, "贵州茅台"),
            _FakeXtPosition("300750.SZ", 200, 180, 205.5, 41100.0, "宁德时代"),
        ]

    def stop(self):
        self.stopped = True


class _FakeStockAccount:
    def __init__(self, account_id, account_type="STOCK"):
        self.account_id = account_id
        self.account_type = account_type


@pytest.fixture
def fake_xtquant_modules(monkeypatch):
    xtquant_pkg = types.ModuleType("xtquant")
    xttrader_mod = types.ModuleType("xtquant.xttrader")
    xttype_mod = types.ModuleType("xtquant.xttype")
    xttrader_mod.XtQuantTrader = _FakeXtQuantTrader
    xttype_mod.StockAccount = _FakeStockAccount

    monkeypatch.setitem(sys.modules, "xtquant", xtquant_pkg)
    monkeypatch.setitem(sys.modules, "xtquant.xttrader", xttrader_mod)
    monkeypatch.setitem(sys.modules, "xtquant.xttype", xttype_mod)
    yield
    monkeypatch.delitem(sys.modules, "xtquant.xttype", raising=False)
    monkeypatch.delitem(sys.modules, "xtquant.xttrader", raising=False)
    monkeypatch.delitem(sys.modules, "xtquant", raising=False)


class TestQmtImportService:
    def test_sync_qmt_portfolio_reads_positions_via_xtquant(self, db, fake_xtquant_modules):
        from api.services import qmt_import_service

        result = qmt_import_service.sync_qmt_portfolio(
            db=db,
            user_id="user1",
            qmt_path="D:/QMT/userdata_mini",
            account_id="demo-account",
            account_type="STOCK",
            auto_apply_scheduled=True,
        )

        assert result["summary"]["positions"] == 2
        assert result["auto_apply_scheduled"] is True
        by_symbol = {item["symbol"]: item for item in result["positions"]}
        assert by_symbol["600519.SH"]["current_position"] == pytest.approx(500.0)
        assert by_symbol["600519.SH"]["average_cost"] == pytest.approx(1700.0)

    def test_sync_qmt_portfolio_auto_creates_scheduled_tasks_for_positions(self, db, fake_xtquant_modules):
        from api.services import qmt_import_service

        result = qmt_import_service.sync_qmt_portfolio(
            db=db,
            user_id="user-auto-scheduled",
            qmt_path="D:/QMT/userdata_mini",
            account_id="demo-account",
            account_type="STOCK",
            auto_apply_scheduled=True,
        )

        tasks = scheduled_service.list_scheduled(db, "user-auto-scheduled")
        assert [item["symbol"] for item in tasks] == ["600519.SH", "300750.SZ"]
        by_symbol = {item["symbol"]: item for item in result["positions"]}
        assert by_symbol["600519.SH"]["trade_points_count"] == 0

    def test_sync_qmt_portfolio_rejects_non_absolute_path(self, db, fake_xtquant_modules):
        from api.services import qmt_import_service

        with pytest.raises(ValueError, match="绝对路径"):
            qmt_import_service.sync_qmt_portfolio(
                db=db,
                user_id="user-invalid-path",
                qmt_path="../userdata_mini",
                account_id="demo-account",
                account_type="STOCK",
                auto_apply_scheduled=True,
            )

    def test_scheduled_job_uses_qmt_position_context(self, db, fake_xtquant_modules):
        from api.main import _run_scheduled_job
        from api.services import qmt_import_service

        qmt_import_service.sync_qmt_portfolio(
            db=db,
            user_id="user1",
            qmt_path="D:/QMT/userdata_mini",
            account_id="demo-account",
            account_type="STOCK",
            auto_apply_scheduled=True,
        )
        task = next(item for item in scheduled_service.list_scheduled(db, "user1") if item["symbol"] == "600519.SH")

        captured = {}

        async def fake_run_job(job_id, request, *args, **kwargs):
            captured["request"] = request

        class FakeDbCtx:
            def __enter__(self):
                return db

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    db.rollback()

        with patch("api.main._run_job", side_effect=fake_run_job), patch(
            "api.main.get_db_ctx",
            return_value=FakeDbCtx(),
        ), patch("tradingagents.dataflows.trade_calendar.is_cn_trading_day", return_value=True):
            asyncio.run(
                _run_scheduled_job(
                    {
                        "id": task["id"],
                        "user_id": "user1",
                        "symbol": "600519.SH",
                        "horizon": "short",
                    },
                    "2026-03-30",
                )
            )

        request = captured["request"]
        assert request.current_position == pytest.approx(500.0)
        assert request.average_cost == pytest.approx(1700.0)
        assert "QMT / xtquant" in (request.user_notes or "")

    def test_scheduled_job_marks_failed_when_underlying_job_fails(self, db):
        from api.main import _run_scheduled_job, _set_job

        item = scheduled_service.create_scheduled(db, "user-failed", "300750.SZ", "short")

        class FakeDbCtx:
            def __enter__(self):
                return db

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    db.rollback()

        async def fake_run_job(job_id, request, *args, **kwargs):
            _set_job(job_id, status="failed", error="ModuleNotFoundError: missing module")

        with patch("api.main._run_job", side_effect=fake_run_job), patch(
            "api.main.get_db_ctx",
            return_value=FakeDbCtx(),
        ), patch("tradingagents.dataflows.trade_calendar.is_cn_trading_day", return_value=True):
            asyncio.run(
                _run_scheduled_job(
                    {
                        "id": item["id"],
                        "user_id": "user-failed",
                        "symbol": "300750.SZ",
                        "horizon": "short",
                    },
                    "2026-03-30",
                )
            )

        scheduled = scheduled_service.get_scheduled(db, "user-failed", item["id"])
        assert scheduled["last_run_status"] == "failed"
        assert scheduled["consecutive_failures"] == 1


class TestQmtImportApi:
    def test_sync_endpoint_reads_qmt_positions(self, fake_xtquant_modules):
        from api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        token = _auth_unique(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/v1/portfolio/imports/qmt",
            headers=headers,
            json={
                "qmt_path": "D:/QMT/userdata_mini",
                "account_id": "demo-account",
                "account_type": "STOCK",
                "auto_apply_scheduled": True,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["positions"] == 2
        assert any(item["symbol"] == "600519.SH" for item in body["positions"])

        scheduled = client.get("/v1/scheduled", headers=headers)
        assert scheduled.status_code == 200
        scheduled_symbols = [item["symbol"] for item in scheduled.json()["items"]]
        assert scheduled_symbols == ["600519.SH", "300750.SZ"]
