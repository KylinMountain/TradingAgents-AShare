"""
CnTushareProvider — 基于 Tushare Pro 的 A 股资金数据 Provider
只实现 smart_money_analyst 需要的 8 个资金方法，其余方法不实现。
route_to_vendor 用 getattr 动态检测，未实现的方法自动 fallback 到 cn_akshare。
"""

import os
import pandas as pd
from .base import BaseMarketDataProvider

_TUSHARE_TOKEN = os.environ.get(
    "TUSHARE_TOKEN",
    "23651a8611b00bf491c7378d81d0bc6265543153530194be989e6ada",
)


def _get_pro():
    import tushare as ts
    ts.set_token(_TUSHARE_TOKEN)
    return ts.pro_api()


def _to_ts_code(symbol: str) -> str:
    """000001 → 000001.SZ, 600519.SH, 000001.SH 保持不变"""
    if "." in symbol:
        return symbol.upper()
    if symbol.startswith(("5", "6", "9")):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


class CnTushareProvider(BaseMarketDataProvider):
    """Tushare Pro 资金数据 provider，速度 0.08-0.13s/接口。"""

    @property
    def name(self) -> str:
        return "cn_tushare"

    # ── Abstract 方法 stub（交给 akshare fallback）──
    def get_stock_data(self, symbol, start_date, end_date):
        raise NotImplementedError("cn_tushare: use cn_akshare for stock_data")

    def get_indicators(self, symbol, indicator, curr_date, look_back_days):
        raise NotImplementedError("cn_tushare: use cn_akshare for indicators")

    def get_fundamentals(self, ticker, curr_date=None):
        raise NotImplementedError("cn_tushare: use cn_akshare for fundamentals")

    def get_balance_sheet(self, ticker, freq="quarterly", curr_date=None):
        raise NotImplementedError("cn_tushare: use cn_akshare for balance_sheet")

    def get_cashflow(self, ticker, freq="quarterly", curr_date=None):
        raise NotImplementedError("cn_tushare: use cn_akshare for cashflow")

    def get_income_statement(self, ticker, freq="quarterly", curr_date=None):
        raise NotImplementedError("cn_tushare: use cn_akshare for income_statement")

    def get_news(self, ticker, start_date, end_date):
        raise NotImplementedError("cn_tushare: use cn_akshare for news")

    def get_global_news(self, curr_date, look_back_days=7, limit=50):
        raise NotImplementedError("cn_tushare: use cn_akshare for global_news")

    def get_insider_transactions(self, symbol):
        raise NotImplementedError("cn_tushare: use cn_akshare for insider_transactions")

    # ── 以下 8 个方法供 smart_money_analyst 使用 ──

    def get_individual_fund_flow(self, symbol: str) -> str:
        """个股近5日分级资金流（小单/中单/大单/超大单）。"""
        ts_code = _to_ts_code(symbol)
        pro = _get_pro()
        df = pro.moneyflow(ts_code=ts_code)
        if df is None or df.empty:
            raise NotImplementedError(f"tushare moneyflow empty for {ts_code}")
        df = df.head(5).copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        # 选择关键列，与 akshare 输出对齐
        cols = ["trade_date"]
        for prefix, label in [("buy_sm", "小单买入"), ("sell_sm", "小单卖出"),
                               ("buy_md", "中单买入"), ("sell_md", "中单卖出"),
                               ("buy_lg", "大单买入"), ("sell_lg", "大单卖出"),
                               ("buy_elg", "超大单买入"), ("sell_elg", "超大单卖出"),
                               ("net_mf_amount", "主力净流入")]:
            if prefix in df.columns:
                cols.append(prefix)
        df = df[[c for c in cols if c in df.columns]]
        df.columns = [c.replace("buy_sm", "小单买入").replace("sell_sm", "小单卖出")
                       .replace("buy_md", "中单买入").replace("sell_md", "中单卖出")
                       .replace("buy_lg", "大单买入").replace("sell_lg", "大单卖出")
                       .replace("buy_elg", "超大单买入").replace("sell_elg", "超大单卖出")
                       .replace("net_mf_amount", "主力净流入")
                       .replace("trade_date", "日期") for c in df.columns]
        return f"{symbol} 近5日分级资金流向（Tushare）：\n{df.to_string(index=False)}"

    def get_lhb_detail(self, symbol: str, date: str) -> str:
        """龙虎榜明细。"""
        ts_code = _to_ts_code(symbol)
        date_str = date.replace("-", "")
        pro = _get_pro()
        df = pro.top_list(trade_date=date_str)
        if df is None or df.empty:
            return f"{symbol} 在 {date} 无龙虎榜数据（非异动日属正常）。"
        df = df[df["ts_code"] == ts_code]
        if df.empty:
            return f"{symbol} 在 {date} 无龙虎榜数据（非异动日属正常）。"
        # 选取关键列
        keep = [c for c in ["trade_date", "ts_code", "name", "close", "pct_change",
                             "turnover_rate", "amount", "l_buy", "l_sell", "l_amount",
                             "net_amount", "net_rate", "reason"] if c in df.columns]
        df = df[keep]
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        return f"{symbol} 龙虎榜明细（{date}，Tushare）：\n{df.head(20).to_string(index=False)}"

    def get_hsgt_individual(self, symbol: str) -> str:
        """个股北向资金持仓 — Tushare 当前积分不支持此接口，fallback 到 akshare。"""
        raise NotImplementedError("tushare hsgt_hold requires higher tier, fallback to akshare")

    def get_hsgt_flow(self) -> str:
        """北向资金整体净流入。"""
        from datetime import datetime, timedelta
        pro = _get_pro()
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        df = pro.moneyflow_hsgt(start_date=start, end_date=end)
        if df is None or df.empty:
            raise NotImplementedError("tushare moneyflow_hsgt empty")
        df = df.tail(5).copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        # 选取关键列
        keep = [c for c in ["trade_date", "north_money", "hgt", "sgt",
                             "south_money", "ggt_ss", "ggt_sz"] if c in df.columns]
        df = df[keep]
        df.columns = [c.replace("north_money", "北向合计").replace("hgt", "沪股通")
                       .replace("sgt", "深股通").replace("south_money", "南向合计")
                       .replace("ggt_ss", "港股通(沪)").replace("ggt_sz", "港股通(深)")
                       .replace("trade_date", "日期") for c in df.columns]
        return f"北向资金整体净流入（近5日，Tushare）：\n{df.to_string(index=False)}"

    def get_block_trades(self, symbol: str, start_date: str, end_date: str) -> str:
        """大宗交易明细。"""
        ts_code = _to_ts_code(symbol)
        sd = start_date.replace("-", "")
        ed = end_date.replace("-", "")
        pro = _get_pro()
        df = pro.block_trade(ts_code=ts_code, start_date=sd, end_date=ed)
        if df is None or df.empty:
            return f"{symbol} 在 {start_date}~{end_date} 无大宗交易数据。"
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        return f"{symbol} 大宗交易明细（{start_date}~{end_date}，Tushare）：\n{df.tail(10).to_string(index=False)}"

    def get_lhb_institution_stats(self, symbol: str, start_date: str, end_date: str) -> str:
        """龙虎榜机构买卖统计。"""
        ts_code = _to_ts_code(symbol)
        sd = start_date.replace("-", "")
        ed = end_date.replace("-", "")
        pro = _get_pro()
        # 逐日获取 top_inst，过滤该股票
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(sd, "%Y%m%d")
        end_dt = datetime.strptime(ed, "%Y%m%d")
        frames = []
        current = start_dt
        while current <= end_dt:
            day_str = current.strftime("%Y%m%d")
            try:
                df_day = pro.top_inst(trade_date=day_str)
                if df_day is not None and not df_day.empty:
                    df_day = df_day[df_day["ts_code"] == ts_code]
                    if not df_day.empty:
                        frames.append(df_day)
            except Exception:
                pass
            current += timedelta(days=1)
        if not frames:
            return f"{symbol} 在 {start_date}~{end_date} 无机构买卖统计数据。"
        combined = pd.concat(frames, ignore_index=True)
        if "trade_date" in combined.columns:
            combined["trade_date"] = pd.to_datetime(combined["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        return f"{symbol} 龙虎榜机构买卖统计（{start_date}~{end_date}，Tushare）：\n{combined.to_string(index=False)}"

    def get_lhb_active_seats(self, start_date: str, end_date: str) -> str:
        """龙虎榜活跃营业部排行（市场级）。"""
        sd = start_date.replace("-", "")
        ed = end_date.replace("-", "")
        pro = _get_pro()
        # 逐日获取 top_inst 汇总
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(sd, "%Y%m%d")
        end_dt = datetime.strptime(ed, "%Y%m%d")
        frames = []
        current = start_dt
        while current <= end_dt:
            day_str = current.strftime("%Y%m%d")
            try:
                df_day = pro.top_inst(trade_date=day_str)
                if df_day is not None and not df_day.empty:
                    frames.append(df_day)
            except Exception:
                pass
            current += timedelta(days=1)
        if not frames:
            return f"{start_date}~{end_date} 活跃营业部数据暂不可用。"
        combined = pd.concat(frames, ignore_index=True)
        # 按营业部汇总 net_buy
        if "exalter" in combined.columns and "net_buy" in combined.columns:
            grouped = combined.groupby("exalter").agg(
                total_net_buy=("net_buy", "sum"),
                trade_count=("trade_date", "count"),
            ).sort_values("total_net_buy", ascending=False).head(10)
            grouped = grouped.reset_index()
            return f"龙虎榜活跃营业部排行（{start_date}~{end_date}，Tushare，前10）：\n{grouped.to_string(index=False)}"
        return f"龙虎榜活跃营业部排行（{start_date}~{end_date}，Tushare）：\n{combined.head(10).to_string(index=False)}"

    def get_margin_detail(self, symbol: str, date: str) -> str:
        """个股融资融券明细。"""
        ts_code = _to_ts_code(symbol)
        date_str = date.replace("-", "")
        pro = _get_pro()
        df = pro.margin_detail(ts_code=ts_code, trade_date=date_str)
        if df is None or df.empty:
            return f"{symbol} 在 {date} 无融资融券记录。"
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        return f"{symbol} 融资融券明细（{date}，Tushare）：\n{df.head(5).to_string(index=False)}"
