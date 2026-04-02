"""Tests for VLM-based position image parsing."""
import json
from unittest.mock import patch


def test_parse_position_image_returns_positions():
    """VLM parser extracts positions from mock LLM response."""
    from api.services.vlm_position_parser import parse_position_image

    mock_llm_response = json.dumps([
        {"symbol": "600519", "name": "贵州茅台", "current_position": 100, "average_cost": 1750.0, "market_value": 180000.0},
        {"symbol": "000001", "name": "平安银行", "current_position": 5000, "average_cost": 12.5, "market_value": 62500.0},
    ])

    with patch("api.services.vlm_position_parser._call_vlm") as mock_vlm, \
         patch("api.services.vlm_position_parser._get_vlm_config", return_value={"provider": "openai", "api_key": "test", "model": "glm-4v-flash", "base_url": ""}):
        mock_vlm.return_value = mock_llm_response
        result = parse_position_image(b"fake_image_bytes", "image/png")

    assert len(result) == 2
    assert result[0]["symbol"] == "600519"
    assert result[0]["name"] == "贵州茅台"
    assert result[0]["current_position"] == 100
    assert result[0]["average_cost"] == 1750.0
    assert result[1]["symbol"] == "000001"


def test_parse_position_image_empty_response():
    from api.services.vlm_position_parser import parse_position_image

    with patch("api.services.vlm_position_parser._call_vlm") as mock_vlm, \
         patch("api.services.vlm_position_parser._get_vlm_config", return_value={"provider": "openai", "api_key": "test", "model": "glm-4v-flash", "base_url": ""}):
        mock_vlm.return_value = "[]"
        result = parse_position_image(b"fake_image_bytes", "image/png")

    assert result == []


def test_parse_response_handles_markdown_fences():
    from api.services.vlm_position_parser import _parse_response

    raw = '```json\n[{"symbol": "600519", "name": "贵州茅台", "current_position": 100}]\n```'
    result = _parse_response(raw)
    assert len(result) == 1
    assert result[0]["symbol"] == "600519"


def test_parse_response_handles_invalid_json():
    from api.services.vlm_position_parser import _parse_response

    result = _parse_response("This is not JSON at all")
    assert result == []


def test_parse_response_skips_items_without_symbol():
    from api.services.vlm_position_parser import _parse_response

    raw = json.dumps([
        {"symbol": "600519", "name": "茅台"},
        {"name": "无代码"},
        {"symbol": "", "name": "空代码"},
    ])
    result = _parse_response(raw)
    assert len(result) == 1
    assert result[0]["symbol"] == "600519"
