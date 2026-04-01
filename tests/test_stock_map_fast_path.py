from unittest.mock import patch


def test_reverse_stock_map_cached_only_does_not_trigger_cold_load():
    from api import main as main_mod

    original_map = main_mod._cn_stock_map
    try:
        main_mod._cn_stock_map = None
        with patch.object(main_mod, "_load_cn_stock_map", side_effect=AssertionError("slow load should not run")):
            assert main_mod._get_reverse_stock_map_cached_only() == {}
    finally:
        main_mod._cn_stock_map = original_map


def test_reverse_stock_map_cached_only_uses_existing_cache():
    from api import main as main_mod

    original_map = main_mod._cn_stock_map
    try:
        main_mod._cn_stock_map = {
            "贵州茅台": "600519.SH",
            "宁德时代": "300750.SZ",
        }
        assert main_mod._get_reverse_stock_map_cached_only() == {
            "600519.SH": "贵州茅台",
            "300750.SZ": "宁德时代",
        }
    finally:
        main_mod._cn_stock_map = original_map
