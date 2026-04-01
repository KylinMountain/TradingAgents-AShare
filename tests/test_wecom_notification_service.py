"""Tests for api.services.wecom_notification_service."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _make_report(**overrides):
    defaults = dict(
        id="rpt-1",
        symbol="600519.SH",
        trade_date="2025-06-01",
        decision="BUY",
        direction="看多",
        confidence=85,
        final_trade_decision="结论：继续持有，等待量价共振后再考虑加仓。",
        trader_investment_plan=None,
        investment_plan=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


async def _noop_sleep(*args):
    pass


class TestBuildReportMessage:
    def test_contains_core_fields(self):
        from api.services.wecom_notification_service import build_report_message

        message = build_report_message(_make_report())

        assert "TradingAgents 定时分析完成" in message
        assert "标的：600519.SH" in message
        assert "交易日：2025-06-01" in message
        assert "决策：BUY" in message
        assert "方向：看多" in message
        assert "置信度：85%" in message
        assert "摘要：" in message

    def test_falls_back_to_investment_plan_summary(self):
        from api.services.wecom_notification_service import build_report_message

        message = build_report_message(
            _make_report(
                final_trade_decision="",
                trader_investment_plan="",
                investment_plan="控制仓位，等待回踩确认后再处理。",
            )
        )

        assert "控制仓位" in message

    def test_build_test_message_uses_default_copy(self):
        from api.services.wecom_notification_service import build_test_message

        message = build_test_message()

        assert "TradingAgents Webhook Warmup" in message
        assert "测试消息" in message


class TestSendMessage:
    @patch("api.services.wecom_notification_service.requests.post")
    def test_accepts_plain_key(self, mock_post):
        from api.services.wecom_notification_service import send_message

        response = MagicMock()
        response.json.return_value = {"errcode": 0}
        mock_post.return_value = response

        result = send_message("hello", "abc123")

        assert result is True
        called_url = mock_post.call_args.args[0]
        assert called_url == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc123"

    @patch("api.services.wecom_notification_service.requests.post")
    def test_returns_false_for_nonzero_errcode(self, mock_post):
        from api.services.wecom_notification_service import send_message

        response = MagicMock()
        response.json.return_value = {"errcode": 93000}
        mock_post.return_value = response

        assert send_message("hello", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc123") is False

    @patch("api.services.wecom_notification_service.requests.post")
    def test_rejects_non_wecom_domain(self, mock_post):
        from api.services.wecom_notification_service import send_message

        with pytest.raises(ValueError):
            send_message("hello", "https://example.com/webhook")

        mock_post.assert_not_called()

    @patch("api.services.wecom_notification_service.logger")
    @patch("api.services.wecom_notification_service.requests.post")
    def test_returns_false_for_non_json_response(self, mock_post, mock_logger):
        from api.services.wecom_notification_service import send_message

        response = MagicMock()
        response.text = "<html>bad gateway</html>"
        response.json.side_effect = ValueError("not json")
        mock_post.return_value = response

        assert send_message("hello", "abc123") is False
        mock_logger.warning.assert_called_once()


class TestSendReportMessageWithRetry:
    def test_success_first_try(self):
        from api.services.wecom_notification_service import send_report_message_with_retry

        with patch("api.services.wecom_notification_service.send_message", return_value=True) as mock_send, \
             patch("api.services.wecom_notification_service.asyncio.sleep", side_effect=_noop_sleep):
            result = asyncio.run(send_report_message_with_retry(_make_report(), "https://example.com"))
            assert result is True
            assert mock_send.call_count == 1

    def test_success_on_retry(self):
        from api.services.wecom_notification_service import send_report_message_with_retry

        with patch("api.services.wecom_notification_service.send_message", side_effect=[False, True]) as mock_send, \
             patch("api.services.wecom_notification_service.asyncio.sleep", side_effect=_noop_sleep):
            result = asyncio.run(send_report_message_with_retry(_make_report(), "https://example.com"))
            assert result is True
            assert mock_send.call_count == 2
