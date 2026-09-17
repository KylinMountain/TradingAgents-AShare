"""Tests for rule-based decision extraction in signal_processing.py."""

from tradingagents.graph.signal_processing import _extract_decision_keyword


def test_negated_buy_phrase_is_not_buy():
    text = "最终建议: 不建议买入，维持观望"
    assert _extract_decision_keyword(text) == "HOLD"


def test_negated_build_position_is_not_buy():
    text = "风险大于收益，不宜建仓，建议持有观望"
    assert _extract_decision_keyword(text) == "HOLD"


def test_avoid_chasing_and_negated_build_position_is_sell():
    text = "核心定性：风险偏高，回避追高，暂不建仓"
    assert _extract_decision_keyword(text) == "SELL"


def test_plain_sell_is_sell():
    assert _extract_decision_keyword("最终建议：卖出") == "SELL"


def test_plain_hold_is_hold():
    assert _extract_decision_keyword("最终建议：观望为主") == "HOLD"


def test_plain_buy_is_buy():
    assert _extract_decision_keyword("最终建议：买入") == "BUY"


def test_cautious_bullish_with_unrelated_caveat_is_still_buy():
    text = "方向：看多，谨慎看多为主，但需回避短期回调风险"
    assert _extract_decision_keyword(text) == "BUY"


def test_issue_191_example_is_buy():
    text = "风控结论：买入 (需方案修正)"
    assert _extract_decision_keyword(text) == "BUY"
