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
