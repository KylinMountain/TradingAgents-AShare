"""Tests for api.services.email_report_service."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures: lightweight stand-ins for ReportDB / UserDB
# ---------------------------------------------------------------------------

def _make_report(**overrides):
    defaults = dict(
        id="rpt-1",
        user_id="u1",
        symbol="600519",
        trade_date="2025-06-01",
        decision="BUY",
        direction="看多",
        confidence=85,
        target_price=1800.0,
        stop_loss_price=1650.0,
        market_report="Market looks good.",
        sentiment_report="Positive sentiment.",
        news_report=None,
        fundamentals_report="Strong fundamentals.",
        macro_report=None,
        smart_money_report=None,
        game_theory_report=None,
        risk_items=[
            {"name": "政策风险", "level": "high", "description": "Regulatory changes"},
            {"name": "流动性风险", "level": "low", "description": "Normal liquidity"},
        ],
        final_trade_decision="Buy at open with 50% position.",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_user(**overrides):
    defaults = dict(id="u1", email="test@example.com", email_report_enabled=True)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# render_report_html tests
# ---------------------------------------------------------------------------

class TestRenderReportHtml:
    def test_contains_symbol_and_date(self):
        from api.services.email_report_service import render_report_html
        html = render_report_html(_make_report())
        assert "600519" in html
        assert "2025-06-01" in html

    def test_contains_decision_info(self):
        from api.services.email_report_service import render_report_html
        html = render_report_html(_make_report())
        assert "BUY" in html
        assert "看多" in html
        assert "85%" in html
        assert "1800" in html
        assert "1650" in html

    def test_contains_analysis_sections(self):
        from api.services.email_report_service import render_report_html
        html = render_report_html(_make_report())
        assert "Market looks good." in html
        assert "Positive sentiment." in html
        assert "Strong fundamentals." in html

    def test_skips_none_sections(self):
        from api.services.email_report_service import render_report_html
        html = render_report_html(_make_report())
        # news_report is None, so its section title should not appear
        # unless another section uses the same heading; check that
        # "新闻分析" heading is absent
        assert "新闻分析" not in html

    def test_contains_risk_items(self):
        from api.services.email_report_service import render_report_html
        html = render_report_html(_make_report())
        assert "政策风险" in html
        assert "流动性风险" in html
        assert "Regulatory changes" in html

    def test_contains_final_trade_decision(self):
        from api.services.email_report_service import render_report_html
        html = render_report_html(_make_report())
        assert "Buy at open with 50% position." in html

    def test_returns_valid_html(self):
        from api.services.email_report_service import render_report_html
        html = render_report_html(_make_report())
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_html_escapes_special_chars(self):
        from api.services.email_report_service import render_report_html
        report = _make_report(symbol="<script>alert(1)</script>")
        html = render_report_html(report)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# send_report_email tests
# ---------------------------------------------------------------------------

class TestSendReportEmail:
    @patch.dict("os.environ", {
        "MAIL_HOST": "smtp.test.com",
        "MAIL_PORT": "587",
        "MAIL_USER": "user@test.com",
        "MAIL_PASS": "secret",
    })
    @patch("api.services.email_report_service.smtplib")
    def test_success_with_mocked_smtp(self, mock_smtplib):
        from api.services.email_report_service import send_report_email
        mock_server = MagicMock()
        mock_smtplib.SMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtplib.SMTP.return_value.__exit__ = MagicMock(return_value=False)

        result = send_report_email(_make_user(), _make_report())
        assert result is True
        mock_server.send_message.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_false_when_no_smtp_config(self):
        from api.services.email_report_service import send_report_email
        result = send_report_email(_make_user(), _make_report())
        assert result is False

    @patch.dict("os.environ", {
        "MAIL_HOST": "smtp.test.com",
        "MAIL_PORT": "587",
        "MAIL_USER": "user@test.com",
        "MAIL_PASS": "secret",
    })
    @patch("api.services.email_report_service.smtplib")
    def test_returns_false_on_smtp_error(self, mock_smtplib):
        from api.services.email_report_service import send_report_email
        mock_smtplib.SMTP.side_effect = Exception("Connection refused")

        result = send_report_email(_make_user(), _make_report())
        assert result is False


# ---------------------------------------------------------------------------
# send_report_email_with_retry tests
# ---------------------------------------------------------------------------

async def _noop_sleep(*args):
    """Replacement for asyncio.sleep that returns immediately."""
    pass


class TestSendReportEmailWithRetry:
    def test_success_first_try(self):
        from api.services.email_report_service import send_report_email_with_retry
        with patch("api.services.email_report_service.send_report_email", return_value=True) as mock_send, \
             patch("api.services.email_report_service.asyncio.sleep", side_effect=_noop_sleep):
            result = asyncio.run(
                send_report_email_with_retry(_make_user(), _make_report())
            )
            assert result is True
            assert mock_send.call_count == 1

    def test_success_on_retry(self):
        from api.services.email_report_service import send_report_email_with_retry
        with patch("api.services.email_report_service.send_report_email", side_effect=[False, True]) as mock_send, \
             patch("api.services.email_report_service.asyncio.sleep", side_effect=_noop_sleep):
            result = asyncio.run(
                send_report_email_with_retry(_make_user(), _make_report())
            )
            assert result is True
            assert mock_send.call_count == 2

    def test_both_fail(self):
        from api.services.email_report_service import send_report_email_with_retry
        with patch("api.services.email_report_service.send_report_email", return_value=False) as mock_send, \
             patch("api.services.email_report_service.asyncio.sleep", side_effect=_noop_sleep):
            result = asyncio.run(
                send_report_email_with_retry(_make_user(), _make_report())
            )
            assert result is False
            assert mock_send.call_count == 2
