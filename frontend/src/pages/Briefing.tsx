import { useState, useEffect } from 'react'
import { Newspaper, RefreshCw, AlertCircle, Globe, Bell, Eye, Briefcase, Lightbulb } from 'lucide-react'
import { api } from '@/services/api'
import type { BriefingDetailResponse, BriefingMarketData, BriefingNewsItem, BriefingWatchlistItem, BriefingPortfolioItem, BriefingTradingAdvice } from '@/types'

function cnTodayStr(): string {
    const d = new Date()
    const bj = new Date(d.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }))
    return bj.toISOString().split('T')[0]
}

export default function Briefing() {
    const [selectedDate, setSelectedDate] = useState<string>(cnTodayStr())
    const [briefing, setBriefing] = useState<BriefingDetailResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [availableDates, setAvailableDates] = useState<string[]>([])

    useEffect(() => {
        api.listBriefings(60).then(res => {
            const dates = [...new Set(res.items
                .filter(it => it.status === 'completed')
                .map(it => it.date)
            )].sort().reverse()
            setAvailableDates(dates)
        }).catch(() => {})
    }, [])

    useEffect(() => {
        setLoading(true)
        setError(null)
        setBriefing(null)
        api.getBriefing(selectedDate)
            .then(setBriefing)
            .catch(err => setError(err.message))
            .finally(() => setLoading(false))
    }, [selectedDate])

    const handleRegenerate = async () => {
        setLoading(true)
        setError(null)
        try {
            const result = await api.generateBriefing(selectedDate)
            setBriefing(result)
            if (!availableDates.includes(selectedDate)) {
                setAvailableDates(prev => [selectedDate, ...prev].sort().reverse())
            }
        } catch (err: any) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">盘前速递</h1>
                    <p className="mt-1 text-slate-500">每日盘前市场简报，快速把握今日风向</p>
                </div>
            </div>

            {/* Date picker + actions */}
            <div className="flex items-center gap-3">
                <input
                    type="date"
                    value={selectedDate}
                    onChange={e => setSelectedDate(e.target.value)}
                    max={cnTodayStr()}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
                />
                <button
                    onClick={handleRegenerate}
                    disabled={loading}
                    className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
                >
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    重新生成
                </button>
            </div>

            {/* Available dates */}
            {availableDates.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {availableDates.slice(0, 10).map(d => (
                        <button
                            key={d}
                            onClick={() => setSelectedDate(d)}
                            className={`rounded-full px-3 py-1 text-xs transition-colors ${
                                d === selectedDate
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400'
                            }`}
                        >
                            {d}
                        </button>
                    ))}
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div className="flex items-center justify-center py-20">
                    <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
                    <span className="ml-3 text-slate-500">正在生成盘前速递，请稍候...</span>
                </div>
            )}

            {/* Error */}
            {error && !loading && (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30">
                    <AlertCircle className="mr-2 inline h-4 w-4" />
                    {error}
                </div>
            )}

            {/* Empty */}
            {!loading && !error && !briefing && (
                <div className="rounded-2xl border border-dashed border-slate-300 py-20 text-center dark:border-slate-600">
                    <Newspaper className="mx-auto h-12 w-12 text-slate-300 dark:text-slate-600" />
                    <p className="mt-4 text-slate-500">暂无 {selectedDate} 的盘前速递</p>
                </div>
            )}

            {/* Completed */}
            {!loading && briefing && briefing.status === 'completed' && (
                <div className="space-y-6">
                    <TradingPlanSection advice={briefing.trading_advice} />
                    <MarketOverview data={briefing.market_data} />
                    <TopNewsSection news={briefing.top_news} />
                    <details>
                        <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                            原始数据（自选股+持仓）
                        </summary>
                        <div className="mt-4 space-y-6">
                            <WatchlistSection data={briefing.watchlist_analysis} />
                            <PortfolioSection data={briefing.portfolio_analysis} />
                        </div>
                    </details>
                </div>
            )}

            {/* Failed */}
            {!loading && briefing && briefing.status === 'failed' && (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30">
                    <AlertCircle className="mr-2 inline h-4 w-4" />
                    简报生成失败: {briefing.error || '未知错误'}。请点击"重新生成"重试。
                </div>
            )}

            {/* Timestamp (stored as UTC, display as Beijing) */}
            {briefing?.generated_at && (
                <p className="text-xs text-slate-400">
                    生成时间: {new Date(briefing.generated_at + '+00:00').toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}
                </p>
            )}
        </div>
    )
}

// ─── Section Components ───────────────────────────────────────────

function SectionCard({ title, icon: Icon, children }: {
    title: string; icon: React.ComponentType<{ className?: string }>; children: React.ReactNode
}) {
    return (
        <div className="card">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
                <Icon className="h-5 w-5 text-blue-500" />
                {title}
            </h2>
            {children}
        </div>
    )
}

function PctBadge({ pct }: { pct?: number | null }) {
    if (pct == null) return <span className="text-slate-400">-</span>
    const color = pct >= 0 ? 'text-red-500' : 'text-green-500'
    const prefix = pct >= 0 ? '+' : ''
    return <span className={color}>{prefix}{pct.toFixed(2)}%</span>
}

function MarketOverview({ data }: { data?: BriefingMarketData | null }) {
    if (!data) return <SectionCard title="今日大势" icon={Globe}><p className="text-slate-500">暂无数据</p></SectionCard>

    return (
        <SectionCard title="今日大势" icon={Globe}>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {/* US Indices */}
                {data.us_indices && data.us_indices.length > 0 && (
                    <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50">
                        <h3 className="mb-2 text-sm font-medium text-slate-500">美股指数</h3>
                        <div className="space-y-2">
                            {data.us_indices.map(idx => (
                                <div key={idx.symbol} className="flex items-center justify-between">
                                    <span className="text-sm">{idx.name}</span>
                                    <span className="text-sm font-medium">{idx.close?.toFixed(2)}</span>
                                    <PctBadge pct={idx.change_pct} />
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* HK */}
                {data.hk_index && data.hk_index.length > 0 && (
                    <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50">
                        <h3 className="mb-2 text-sm font-medium text-slate-500">港股</h3>
                        <div className="space-y-2">
                            {data.hk_index.map(idx => (
                                <div key={idx.name} className="flex items-center justify-between">
                                    <span className="text-sm">{idx.name}</span>
                                    <span className="text-sm font-medium">{idx.close?.toFixed(2)}</span>
                                    <PctBadge pct={idx.change_pct} />
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* A50 */}
                {data.a50_futures && (
                    <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50">
                        <h3 className="mb-2 text-sm font-medium text-slate-500">A50期货</h3>
                        <div className="flex items-center justify-between">
                            <span className="text-sm">{data.a50_futures.name}</span>
                            <span className="text-sm font-medium">{data.a50_futures.close?.toFixed(2)}</span>
                            <PctBadge pct={data.a50_futures.change_pct} />
                        </div>
                    </div>
                )}

                {/* Commodities */}
                {data.commodities && data.commodities.length > 0 && (
                    <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50">
                        <h3 className="mb-2 text-sm font-medium text-slate-500">大宗商品</h3>
                        <div className="space-y-2">
                            {data.commodities.map(c => (
                                <div key={c.name} className="flex items-center justify-between">
                                    <span className="text-sm">{c.name}</span>
                                    <span className="text-sm font-medium">{c.close?.toFixed(2)}</span>
                                    <PctBadge pct={c.change_pct} />
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* FX */}
                {data.fx && data.fx.length > 0 && (
                    <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50">
                        <h3 className="mb-2 text-sm font-medium text-slate-500">汇率</h3>
                        <div className="space-y-2">
                            {data.fx.map(f => (
                                <div key={f.name} className="flex items-center justify-between">
                                    <span className="text-sm">{f.name}</span>
                                    <span className="text-sm font-medium">{f.close?.toFixed(4)}</span>
                                    <PctBadge pct={f.change_pct} />
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Fund Flow */}
                {data.fund_flow && (
                    <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50">
                        <h3 className="mb-2 text-sm font-medium text-slate-500">资金面</h3>
                        <div className="space-y-1 text-sm">
                            <div className="flex justify-between">
                                <span className="text-slate-500">主力净流入</span>
                                <span className={data.fund_flow.main_net >= 0 ? 'text-red-500' : 'text-green-500'}>
                                    {(data.fund_flow.main_net / 1e8).toFixed(2)}亿
                                </span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-slate-500">超大单净流入</span>
                                <span>{(data.fund_flow.super_large_net / 1e8).toFixed(2)}亿</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </SectionCard>
    )
}

function TopNewsSection({ news }: { news?: BriefingNewsItem[] | null }) {
    if (!news || news.length === 0) {
        return <SectionCard title="重大要闻" icon={Bell}><p className="text-slate-500">暂无要闻</p></SectionCard>
    }
    return (
        <SectionCard title="重大要闻" icon={Bell}>
            <div className="space-y-3">
                {news.map((item, i) => (
                    <div key={i} className="border-b border-slate-100 pb-3 last:border-0 dark:border-slate-700">
                        <p className="text-sm font-medium">{i + 1}. {item.title}</p>
                        {item.content_preview && (
                            <p className="mt-1 text-xs text-slate-500 line-clamp-2">{item.content_preview}</p>
                        )}
                        <p className="mt-1 text-xs text-slate-400">{item.source}</p>
                    </div>
                ))}
            </div>
        </SectionCard>
    )
}

function WatchlistSection({ data }: { data?: BriefingWatchlistItem[] | null }) {
    if (!data || data.length === 0) {
        return <SectionCard title="自选股分析" icon={Eye}><p className="text-slate-500">暂无自选股数据</p></SectionCard>
    }

    const withSignal = data.filter(w => w.signals.length > 0 || w.news_summary)
    const noSignal = data.filter(w => w.signals.length === 0 && !w.news_summary)

    return (
        <SectionCard title="自选股分析" icon={Eye}>
            {withSignal.length > 0 && (
                <div className="mb-4">
                    <h3 className="mb-2 text-sm font-medium text-orange-500">有事件/信号 ({withSignal.length})</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200 dark:border-slate-700">
                                    <th className="py-2 text-left">股票</th>
                                    <th className="py-2 text-right">最新价</th>
                                    <th className="py-2 text-right">涨跌幅</th>
                                    <th className="py-2 text-left">信号</th>
                                    <th className="py-2 text-left">消息</th>
                                </tr>
                            </thead>
                            <tbody>
                                {withSignal.map(item => (
                                    <tr key={item.symbol} className="border-b border-slate-100 dark:border-slate-800">
                                        <td className="py-2">
                                            <span className="font-medium">{item.name || item.symbol}</span>
                                            <span className="ml-1 text-xs text-slate-400">{item.symbol}</span>
                                        </td>
                                        <td className="py-2 text-right">{item.latest_price?.toFixed(2) ?? '-'}</td>
                                        <td className="py-2 text-right"><PctBadge pct={item.change_pct} /></td>
                                        <td className="py-2">
                                            <div className="flex flex-wrap gap-1">
                                                {item.signals.map((s, i) => (
                                                    <span key={i} className={`rounded px-1.5 py-0.5 text-xs ${
                                                        s.interpretation.includes('多') ? 'bg-red-50 text-red-600 dark:bg-red-950/30' :
                                                        s.interpretation.includes('空') ? 'bg-green-50 text-green-600 dark:bg-green-950/30' :
                                                        'bg-slate-100 text-slate-600 dark:bg-slate-800'
                                                    }`}>
                                                        {s.name}
                                                    </span>
                                                ))}
                                            </div>
                                        </td>
                                        <td className="py-2 max-w-[200px] truncate text-xs text-slate-500">
                                            {item.news_summary || '-'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {noSignal.length > 0 && (
                <details>
                    <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                        暂无信号 ({noSignal.length}只)
                    </summary>
                    <div className="mt-2 flex flex-wrap gap-1">
                        {noSignal.map(item => (
                            <span key={item.symbol} className="rounded bg-slate-50 px-2 py-1 text-xs text-slate-500 dark:bg-slate-800">
                                {item.name || item.symbol}
                            </span>
                        ))}
                    </div>
                </details>
            )}
        </SectionCard>
    )
}

function PortfolioSection({ data }: { data?: BriefingPortfolioItem[] | null }) {
    if (!data || data.length === 0) {
        return <SectionCard title="持仓股分析" icon={Briefcase}><p className="text-slate-500">暂无持仓数据</p></SectionCard>
    }

    const needsAttention = data.filter(p => (p.risk_signals && p.risk_signals.length > 0))
    const normal = data.filter(p => !p.risk_signals || p.risk_signals.length === 0)

    return (
        <SectionCard title="持仓股分析" icon={Briefcase}>
            {needsAttention.length > 0 && (
                <div className="mb-4">
                    <h3 className="mb-2 text-sm font-medium text-rose-500">需关注 ({needsAttention.length})</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200 dark:border-slate-700">
                                    <th className="py-2 text-left">股票</th>
                                    <th className="py-2 text-right">持仓</th>
                                    <th className="py-2 text-right">成本</th>
                                    <th className="py-2 text-right">现价</th>
                                    <th className="py-2 text-right">盈亏</th>
                                    <th className="py-2 text-left">风险信号</th>
                                </tr>
                            </thead>
                            <tbody>
                                {needsAttention.map(item => (
                                    <tr key={item.symbol} className="border-b border-slate-100 dark:border-slate-800">
                                        <td className="py-2">
                                            <span className="font-medium">{item.name || item.symbol}</span>
                                            <span className="ml-1 text-xs text-slate-400">{item.symbol}</span>
                                        </td>
                                        <td className="py-2 text-right">{item.position}</td>
                                        <td className="py-2 text-right">{item.avg_cost?.toFixed(2)}</td>
                                        <td className="py-2 text-right">{item.current_price?.toFixed(2) ?? '-'}</td>
                                        <td className={`py-2 text-right font-medium ${(item.pnl_pct ?? 0) >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                                            {item.pnl_pct != null ? `${item.pnl_pct >= 0 ? '+' : ''}${item.pnl_pct.toFixed(2)}%` : '-'}
                                        </td>
                                        <td className="py-2">
                                            <div className="flex flex-wrap gap-1">
                                                {item.risk_signals?.map((s, i) => (
                                                    <span key={i} className="rounded bg-rose-50 px-1.5 py-0.5 text-xs text-rose-600 dark:bg-rose-950/30">
                                                        {s}
                                                    </span>
                                                ))}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {normal.length > 0 && (
                <details>
                    <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                        正常持有 ({normal.length}只)
                    </summary>
                    <div className="mt-2 overflow-x-auto">
                        <table className="w-full text-sm opacity-60">
                            <thead>
                                <tr className="border-b border-slate-200 dark:border-slate-700">
                                    <th className="py-2 text-left">股票</th>
                                    <th className="py-2 text-right">持仓</th>
                                    <th className="py-2 text-right">盈亏</th>
                                </tr>
                            </thead>
                            <tbody>
                                {normal.map(item => (
                                    <tr key={item.symbol} className="border-b border-slate-100 dark:border-slate-800">
                                        <td className="py-2"><span className="font-medium">{item.name || item.symbol}</span></td>
                                        <td className="py-2 text-right">{item.position}</td>
                                        <td className={`py-2 text-right ${(item.pnl_pct ?? 0) >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                                            {item.pnl_pct != null ? `${item.pnl_pct >= 0 ? '+' : ''}${item.pnl_pct.toFixed(2)}%` : '-'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </details>
            )}
        </SectionCard>
    )
}

function TradingPlanSection({ advice }: { advice?: BriefingTradingAdvice | null }) {
    if (!advice) {
        return <SectionCard title="盘前交易计划" icon={Lightbulb}><p className="text-slate-500">暂无交易计划</p></SectionCard>
    }

    const { sentiment, watchlist_plan, portfolio_plan, error } = advice

    return (
        <SectionCard title="盘前交易计划" icon={Lightbulb}>
            {error && (
                <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-500 dark:border-rose-900/50 dark:bg-rose-950/30">
                    AI生成失败: {error}，以下为程序化分析数据仅供参考。
                </div>
            )}

            {/* 1. 今日情绪与主线 */}
            {sentiment && (
                <div className="mb-6 rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 p-4 dark:from-blue-950/30 dark:to-indigo-950/20">
                    <h3 className="mb-2 text-sm font-medium text-blue-700 dark:text-blue-300">1. 今日情绪与主线</h3>
                    <p className="text-sm leading-relaxed text-blue-900 dark:text-blue-200">{sentiment}</p>
                </div>
            )}

            {/* 2. 自选股低吸观察 */}
            {watchlist_plan && watchlist_plan.length > 0 && (
                <div className="mb-6">
                    <h3 className="mb-3 text-sm font-medium text-orange-600 dark:text-orange-400">2. 自选股低吸观察</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200 dark:border-slate-700">
                                    <th className="whitespace-nowrap py-2 text-left font-medium text-slate-500">股票</th>
                                    <th className="whitespace-nowrap py-2 text-left font-medium text-slate-500">策略类型</th>
                                    <th className="whitespace-nowrap py-2 text-left font-medium text-slate-500">入场条件</th>
                                    <th className="whitespace-nowrap py-2 text-left font-medium text-slate-500">理由</th>
                                </tr>
                            </thead>
                            <tbody>
                                {watchlist_plan.map((item, i) => (
                                    <tr key={i} className="border-b border-slate-100 dark:border-slate-800">
                                        <td className="whitespace-nowrap py-2 pr-3 font-medium">{item.股票}</td>
                                        <td className="whitespace-nowrap py-2 pr-3">
                                            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                                item.策略类型.includes('回踩') ? 'bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400' :
                                                item.策略类型.includes('半路') ? 'bg-orange-50 text-orange-600 dark:bg-orange-950/30 dark:text-orange-400' :
                                                item.策略类型.includes('突破') ? 'bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400' :
                                                'bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-400'
                                            }`}>{item.策略类型}</span>
                                        </td>
                                        <td className="py-2 pr-3 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{item.入场条件}</td>
                                        <td className="py-2 text-xs text-slate-500">{item.理由}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* 3. 持仓股处理 */}
            {portfolio_plan && portfolio_plan.length > 0 && (
                <div>
                    <h3 className="mb-3 text-sm font-medium text-rose-600 dark:text-rose-400">3. 持仓股处理</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200 dark:border-slate-700">
                                    <th className="whitespace-nowrap py-2 text-left font-medium text-slate-500">股票</th>
                                    <th className="whitespace-nowrap py-2 text-right font-medium text-slate-500">盈亏</th>
                                    <th className="whitespace-nowrap py-2 text-left font-medium text-slate-500">止盈条件</th>
                                    <th className="whitespace-nowrap py-2 text-left font-medium text-slate-500">止损条件</th>
                                    <th className="whitespace-nowrap py-2 text-left font-medium text-slate-500">建议</th>
                                </tr>
                            </thead>
                            <tbody>
                                {portfolio_plan.map((item, i) => {
                                    const isProfit = item.盈亏.startsWith('+')
                                    const action = item.建议
                                    return (
                                        <tr key={i} className="border-b border-slate-100 dark:border-slate-800">
                                            <td className="whitespace-nowrap py-2 pr-3 font-medium">{item.股票}</td>
                                            <td className={`whitespace-nowrap py-2 pr-3 text-right font-medium ${isProfit ? 'text-red-500' : 'text-green-500'}`}>
                                                {item.盈亏}
                                            </td>
                                            <td className="py-2 pr-3 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{item.止盈条件}</td>
                                            <td className="py-2 pr-3 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{item.止损条件}</td>
                                            <td className="whitespace-nowrap py-2">
                                                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                                    action.includes('持有') ? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400' :
                                                    action.includes('加仓') ? 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' :
                                                    'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'
                                                }`}>{action}</span>
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Empty state when LLM returns no plan items */}
            {!sentiment && !watchlist_plan?.length && !portfolio_plan?.length && !error && (
                <p className="text-sm text-slate-500">AI 交易计划尚未生成，请点击"重新生成"。</p>
            )}
        </SectionCard>
    )
}
