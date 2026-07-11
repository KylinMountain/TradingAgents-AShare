import pandas as pd
import pytest

from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider


class _FakeAkshareClient:
    def __init__(self, df):
        self._df = df

    def stock_fund_flow_concept(self, symbol="即时"):
        return self._df


class _StubProvider(CnAkshareProvider):
    def __init__(self, df):
        self._df = df

    def _ak(self):
        return _FakeAkshareClient(self._df)


def _sample_df():
    return pd.DataFrame(
        [
            {"序号": 1, "行业": "CRO概念", "行业-涨跌幅": 4.43, "流入资金": 159.65, "流出资金": 140.09, "净额": 19.56, "公司家数": 73},
            {"序号": 2, "行业": "减肥药", "行业-涨跌幅": 4.35, "流入资金": 155.02, "流出资金": 136.83, "净额": 18.19, "公司家数": 63},
        ]
    )


def test_get_concept_fund_flow_df_returns_raw_dataframe():
    provider = _StubProvider(_sample_df())
    df = provider.get_concept_fund_flow_df()
    assert list(df["行业"]) == ["CRO概念", "减肥药"]
    assert df.iloc[0]["净额"] == 19.56


def test_get_concept_fund_flow_df_empty_on_empty_response():
    provider = _StubProvider(pd.DataFrame())
    df = provider.get_concept_fund_flow_df()
    assert df.empty


def test_get_concept_fund_flow_df_propagates_exception():
    # Regression: this used to swallow the exception and return an empty
    # DataFrame, making a real akshare outage indistinguishable from a
    # legitimate no-data day for every caller (including the cause-
    # attribution LLM agent, which could then fabricate a plausible-but-
    # wrong conclusion instead of reporting the data source is broken).
    class _RaisingClient:
        def stock_fund_flow_concept(self, symbol="即时"):
            raise RuntimeError("boom")

    class _RaisingProvider(CnAkshareProvider):
        def _ak(self):
            return _RaisingClient()

    with pytest.raises(RuntimeError, match="boom"):
        _RaisingProvider().get_concept_fund_flow_df()


def test_get_concept_fund_flow_formats_sorted_text():
    provider = _StubProvider(_sample_df())
    text = provider.get_concept_fund_flow()
    assert "概念板块资金流向排名" in text
    assert "CRO概念" in text
    assert text.index("CRO概念") < text.index("减肥药")


def test_get_concept_fund_flow_empty_message():
    provider = _StubProvider(pd.DataFrame())
    text = provider.get_concept_fund_flow()
    assert "暂不可用" in text


def test_get_concept_fund_flow_surfaces_exception_detail():
    # The string-returning wrapper must still catch and report the real
    # error, rather than a generic "no data" message.
    class _RaisingClient:
        def stock_fund_flow_concept(self, symbol="即时"):
            raise RuntimeError("boom")

    class _RaisingProvider(CnAkshareProvider):
        def _ak(self):
            return _RaisingClient()

    text = _RaisingProvider().get_concept_fund_flow()
    assert "RuntimeError" in text
