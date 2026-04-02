from datetime import datetime, timezone
import time
from uuid import uuid4

from fastapi.testclient import TestClient
import requests

from api.database import ImportedPortfolioPositionDB, ReportDB, UserDB, get_db_ctx, init_db
from api.services import auth_service, report_service


def _auth_with_user(client: TestClient) -> tuple[str, str]:
    init_db()
    email = auth_service.normalize_email(f"dashboard-{uuid4().hex[:8]}@test.com")
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
    return user.id, auth_service.create_access_token(user)


class TestDashboardTrackingApi:
    def test_tracking_board_merges_positions_quotes_and_previous_trade_day_report(self, monkeypatch):
        from api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        user_id, token = _auth_with_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        now = datetime.now(timezone.utc)

        with get_db_ctx() as db:
            db.add_all([
                ImportedPortfolioPositionDB(
                    id=uuid4().hex,
                    user_id=user_id,
                    source="manual",
                    symbol="600519.SH",
                    security_name="贵州茅台",
                    current_position=500.0,
                    available_position=480.0,
                    average_cost=1700.0,
                    market_value=850000.0,
                    current_position_pct=95.3996,
                    trade_points_json=[],
                    trade_points_count=0,
                    last_imported_at=now,
                ),
                ImportedPortfolioPositionDB(
                    id=uuid4().hex,
                    user_id=user_id,
                    source="manual",
                    symbol="300750.SZ",
                    security_name="宁德时代",
                    current_position=200.0,
                    available_position=180.0,
                    average_cost=205.5,
                    market_value=41100.0,
                    current_position_pct=4.6004,
                    trade_points_json=[],
                    trade_points_count=0,
                    last_imported_at=now,
                ),
            ])
            report_service.create_report(
                db=db,
                symbol="600519.SH",
                trade_date="2026-03-30",
                decision="HOLD",
                user_id=user_id,
                result_data={
                    "trader_investment_plan": (
                        "结论：持有\n"
                        "目标价：1750\n"
                        "止损价：1650\n"
                        "最终交易建议：持有，等待放量确认。"
                    ),
                    "final_trade_decision": "结论：持有\n目标价：1750\n止损价：1650",
                },
            )
            report_service.create_report(
                db=db,
                symbol="300750.SZ",
                trade_date="2026-03-28",
                decision="BUY",
                user_id=user_id,
                result_data={
                    "trader_investment_plan": "结论：分批增持\n目标价：220\n止损价：198",
                    "final_trade_decision": "结论：增持\n目标价：220\n止损价：198",
                },
            )

        monkeypatch.setattr("api.services.tracking_board_service.cn_today_str", lambda: "2026-03-31")
        monkeypatch.setattr("api.services.tracking_board_service.previous_cn_trading_day", lambda _: "2026-03-30")
        monkeypatch.setattr(
            "api.services.tracking_board_service._fetch_live_quotes",
            lambda symbols, **kwargs: {
                "600519.SH": {
                    "price": 1723.5,
                    "open": 1708.0,
                    "change": 23.5,
                    "change_pct": 1.38,
                    "high": 1728.0,
                    "low": 1698.0,
                    "previous_close": 1700.0,
                    "volume": 200000.0,
                    "amount": 635000000.0,
                    "quote_time": "2026-03-31T10:15:00+08:00",
                    "source": "test_quote",
                },
                "300750.SZ": {
                    "price": 208.8,
                    "open": 206.1,
                    "change": 1.1,
                    "change_pct": 0.53,
                    "high": 209.2,
                    "low": 204.8,
                    "previous_close": 207.7,
                    "volume": 10000.0,
                    "amount": 49530000.0,
                    "quote_time": "2026-03-31T10:15:00+08:00",
                    "source": "test_quote",
                },
            },
        )

        response = client.get("/v1/dashboard/tracking-board", headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert body["previous_trade_date"] == "2026-03-30"
        assert body["refresh_interval_seconds"] > 0
        assert len(body["items"]) == 2

        by_symbol = {item["symbol"]: item for item in body["items"]}

        mt = by_symbol["600519.SH"]
        assert mt["live_price"] == 1723.5
        assert mt["day_open"] == 1708.0
        assert mt["volume"] == 200000.0
        assert mt["amount"] == 635000000.0
        assert mt["floating_pnl"] == 11750.0
        assert mt["floating_pnl_pct"] == 1.38
        assert mt["analysis"]["trade_date"] == "2026-03-30"
        assert mt["analysis"]["is_previous_trade_day"] is True
        assert mt["analysis"]["high_price"] == 1750.0
        assert mt["analysis"]["low_price"] == 1650.0
        assert "持有" in (mt["analysis"]["trader_advice_summary"] or "")

        catl = by_symbol["300750.SZ"]
        assert catl["day_open"] == 206.1
        assert catl["analysis"]["trade_date"] == "2026-03-28"
        assert catl["analysis"]["is_previous_trade_day"] is False
        assert catl["analysis"]["high_price"] == 220.0
        assert catl["analysis"]["low_price"] == 198.0

    def test_tracking_board_handles_positions_without_quotes_or_reports(self, monkeypatch):
        from api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        user_id, token = _auth_with_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        now = datetime.now(timezone.utc)

        with get_db_ctx() as db:
            db.add(
                ImportedPortfolioPositionDB(
                    id=uuid4().hex,
                    user_id=user_id,
                    source="manual",
                    symbol="601318.SH",
                    security_name="中国平安",
                    current_position=300.0,
                    available_position=300.0,
                    average_cost=52.3,
                    market_value=15690.0,
                    current_position_pct=100.0,
                    trade_points_json=[],
                    trade_points_count=0,
                    last_imported_at=now,
                )
            )
            db.commit()

        monkeypatch.setattr("api.services.tracking_board_service.cn_today_str", lambda: "2026-03-31")
        monkeypatch.setattr("api.services.tracking_board_service.previous_cn_trading_day", lambda _: "2026-03-30")
        monkeypatch.setattr("api.services.tracking_board_service._fetch_live_quotes", lambda symbols, **kwargs: {})

        response = client.get("/v1/dashboard/tracking-board", headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert body["previous_trade_date"] == "2026-03-30"
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert item["symbol"] == "601318.SH"
        assert item["live_price"] is None
        assert item["volume"] is None
        assert item["amount"] is None
        assert item["quote_source"] is None
        assert item["analysis"] is None


def test_fetch_live_quotes_returns_empty_when_batch_request_times_out(monkeypatch):
    from api.services import tracking_board_service

    monkeypatch.setattr(tracking_board_service, "ENABLE_SINGLE_QUOTE_FALLBACK", False)
    def _timeout(*args, **kwargs):
        raise requests.ReadTimeout("timed out")

    monkeypatch.setattr("api.services.tracking_board_service.requests.get", _timeout)

    quotes = tracking_board_service._fetch_live_quotes(["600519.SH"])
    assert quotes == {}


def test_parse_sina_quote_line_extracts_expected_fields():
    from api.services import tracking_board_service

    line = (
        'var hq_str_sh600519="贵州茅台,1464.490,1450.000,1459.440,1469.990,1452.880,1459.440,1459.800,2912514,'
        '4256185472.000,124,1459.440,200,1459.380,600,1459.370,400,1459.360,100,1459.290,300,1459.800,'
        '400,1459.820,100,1459.980,300,1459.990,200,1460.000,2026-04-01,15:00:03,00,";'
    )

    symbol, quote = tracking_board_service._parse_sina_quote_line(line)

    assert symbol == "sh600519"
    assert quote is not None
    assert quote["price"] == 1459.44
    assert quote["open"] == 1464.49
    assert quote["high"] == 1469.99
    assert quote["low"] == 1452.88
    assert quote["previous_close"] == 1450.0
    assert quote["change"] == 9.44
    assert quote["source"] == "sina_hq"
