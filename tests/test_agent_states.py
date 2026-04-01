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
