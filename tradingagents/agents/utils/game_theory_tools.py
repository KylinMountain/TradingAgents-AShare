from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_board_fund_flow() -> str:
    """获取今日行业板块资金流向排名，用于判断板块轮动信号和个股所在板块的资金吸引力。"""
    return route_to_vendor("get_board_fund_flow")


@tool
def get_individual_fund_flow(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股近5日主力资金净流向，判断机构资金进出方向。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_individual_fund_flow", symbol)


@tool
def get_lhb_detail(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
    date: Annotated[str, "日期，格式 YYYY-MM-DD"],
) -> str:
    """获取个股龙虎榜数据，非异动日无数据属正常。symbol 格式如 600519.SH，date 格式 YYYY-MM-DD。"""
    return route_to_vendor("get_lhb_detail", symbol, date)


@tool
def get_zt_pool(
    date: Annotated[str, "日期，格式 YYYY-MM-DD"],
) -> str:
    """获取市场涨停板情绪池，反映市场整体情绪温度，date 格式 YYYY-MM-DD。"""
    return route_to_vendor("get_zt_pool", date)


@tool
def get_hot_stocks_xq() -> str:
    """获取雪球热搜股票列表，反映散户当前关注热点。"""
    return route_to_vendor("get_hot_stocks_xq")


@tool
def get_hsgt_individual(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股北向资金（沪/深港通）持仓历史，判断外资增减仓方向。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_hsgt_individual", symbol)


@tool
def get_hsgt_flow() -> str:
    """获取沪/深股通近期整体净流入趋势，判断北向资金整体方向。"""
    return route_to_vendor("get_hsgt_flow")


@tool
def get_margin_detail(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
    date: Annotated[str, "日期，格式 YYYY-MM-DD"],
) -> str:
    """获取个股融资融券明细，判断杠杆资金多空方向。symbol 格式如 600519.SH，date 格式 YYYY-MM-DD。"""
    return route_to_vendor("get_margin_detail", symbol, date)


@tool
def get_block_trades(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
    start_date: Annotated[str, "开始日期，格式 YYYY-MM-DD"],
    end_date: Annotated[str, "结束日期，格式 YYYY-MM-DD"],
) -> str:
    """获取个股大宗交易明细，判断机构大资金场外交易行为。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_block_trades", symbol, start_date, end_date)


@tool
def get_lhb_institution_stats(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
    start_date: Annotated[str, "开始日期，格式 YYYY-MM-DD"],
    end_date: Annotated[str, "结束日期，格式 YYYY-MM-DD"],
) -> str:
    """获取龙虎榜机构买卖统计，判断机构在龙虎榜上的净买卖方向。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_lhb_institution_stats", symbol, start_date, end_date)


@tool
def get_lhb_active_seats(
    start_date: Annotated[str, "开始日期，格式 YYYY-MM-DD"],
    end_date: Annotated[str, "结束日期，格式 YYYY-MM-DD"],
) -> str:
    """获取龙虎榜活跃营业部排行，识别知名游资席位动向。"""
    return route_to_vendor("get_lhb_active_seats", start_date, end_date)


@tool
def get_research_reports(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股机构研报列表（含评级和盈利预测），判断机构观点。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_research_reports", symbol)


@tool
def get_shareholder_changes(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股股东增减持记录，判断内部人交易信号。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_shareholder_changes", symbol)


@tool
def get_restricted_release(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股限售解禁时间表，评估未来潜在抛压。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_restricted_release", symbol)


@tool
def get_pledge_ratio(
    date: Annotated[str, "日期，格式 YYYY-MM-DD"],
) -> str:
    """获取全市场股权质押比率数据，评估市场整体质押风险水平。date 格式 YYYY-MM-DD。"""
    return route_to_vendor("get_pledge_ratio", date)


# ── 新增：资金面/筹码/板块/公告（Phase 2）──

@tool
def get_shareholder_count(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股股东户数变化历史，判断筹码集中度趋势。股东户数减少意味着筹码集中。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_shareholder_count", symbol)


@tool
def get_dividend_history(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股分红送转历史（每股派息/送股/转增），评估股息回报。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_dividend_history", symbol)


@tool
def get_concept_board(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股所属概念/行业/地域板块归属，识别题材属性。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_concept_board", symbol)


@tool
def get_individual_fund_flow_120d(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股120日主力/大单/中单/小单资金净流向，判断中长期资金趋势。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_individual_fund_flow_120d", symbol)


@tool
def get_cninfo_announcements(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
    start_date: Annotated[str, "开始日期，格式 YYYY-MM-DD"],
    end_date: Annotated[str, "结束日期，格式 YYYY-MM-DD"],
) -> str:
    """获取个股巨潮公告全文检索（含链接），用于查阅公司公告原文。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_cninfo_announcements", symbol, start_date, end_date)


# ── 新增：盘口/F10/逐笔（mootdx，Phase 1）──

@tool
def get_five_level_orderbook(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
) -> str:
    """获取个股五档买卖盘口数据（买一~买五/卖一~卖五），判断短期供需。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_five_level_orderbook", symbol)


@tool
def get_f10_detail(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
    category: Annotated[int, "F10分类：0=最新提示 1=公司概况 2=财务分析 3=股东研究 4=主力追踪 5=行业分析 6=公司大事 7=经营分析 8=分红融资"],
) -> str:
    """获取个股F10公司资料（9大类），深入基本面研究。category 0-8 对应不同资料分类。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_f10_detail", symbol, category)


@tool
def get_level2_quotes(
    symbol: Annotated[str, "股票代码，格式如 600519.SH"],
    date: Annotated[str, "日期，格式 YYYYMMDD 如 20260623"],
) -> str:
    """获取个股逐笔成交数据（Level 2），分析盘中资金进出细节。非交易时间返回空。symbol 格式如 600519.SH。"""
    return route_to_vendor("get_level2_quotes", symbol, date)
