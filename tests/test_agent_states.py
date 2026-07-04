import operator
from tradingagents.agents.utils.agent_states import UserIntent, TraceItem, extract_verdict

def test_user_intent_typeddict():
    intent: UserIntent = {
        "raw_query": "分析600519短线",
        "ticker": "600519",
        "horizons": ["short", "medium"],
        "focus_areas": ["量价关系"],
        "specific_questions": ["能否到目标位"],
    }
    assert intent["ticker"] == "600519"
    assert intent["horizons"] == ["short", "medium"]

def test_trace_item_typeddict():
    trace: TraceItem = {
        "agent": "market_analyst",
        "horizon": "short",
        "data_window": "14天",
        "key_finding": "RSI超买",
        "verdict": "看空",
        "confidence": "中",
    }
    assert trace["verdict"] == "看空"
    assert trace["confidence"] == "中"

def test_trace_list_accumulation():
    t1 = [{"agent": "market_analyst", "verdict": "看空"}]
    t2 = [{"agent": "fundamentals_analyst", "verdict": "看多"}]
    merged = operator.add(t1, t2)
    assert len(merged) == 2


def test_extract_verdict_valid():
    text = '分析结论 <!-- VERDICT: {"direction": "看多", "reason": "量价配合"} --> 结束'
    direction, confidence = extract_verdict(text)
    assert direction == "看多"
    assert confidence == "中"


def test_extract_verdict_missing():
    direction, confidence = extract_verdict("没有VERDICT标签的文本")
    assert direction == "中性"
    assert confidence == "低"


def test_extract_verdict_empty():
    direction, confidence = extract_verdict("")
    assert direction == "中性"
    assert confidence == "低"


def test_extract_verdict_confidence_int():
    text = '<!-- VERDICT: {"direction": "看多", "confidence": 80, "reason": "强支撑"} -->'
    direction, confidence = extract_verdict(text)
    assert direction == "看多"
    assert confidence == "高"


def test_extract_verdict_confidence_float():
    text = '<!-- VERDICT: {"direction": "偏空", "confidence": 0.55, "reason": "破位"} -->'
    direction, confidence = extract_verdict(text)
    assert direction == "偏空"
    assert confidence == "中"


def test_extract_verdict_confidence_low():
    text = '<!-- VERDICT: {"direction": "中性", "confidence": 25, "reason": "信号矛盾"} -->'
    direction, confidence = extract_verdict(text)
    assert direction == "中性"
    assert confidence == "低"


def test_extract_verdict_english_direction():
    text = '<!-- VERDICT: {"direction": "BULLISH", "confidence": 75, "reason": "breakout"} -->'
    direction, confidence = extract_verdict(text)
    assert direction == "看多"
    assert confidence == "高"


def test_extract_verdict_keyword_fallback():
    text = "综合来看，该股技术面偏多，资金面中性，建议谨慎参与"
    direction, confidence = extract_verdict(text)
    assert direction in ("看多", "偏多")
    assert confidence == "低"


def test_extract_verdict_no_keyword():
    text = "今日市场波动较大，关注后续走势"
    direction, confidence = extract_verdict(text)
    assert direction == "中性"
    assert confidence == "低"
