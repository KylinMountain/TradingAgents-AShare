import { useState, useEffect } from 'react'
import { Newspaper, RefreshCw, AlertCircle, Globe, Bell, Eye, Briefcase, Lightbulb, TrendingUp, DollarSign, BarChart3, Activity, Zap, Landmark, Cpu, ShieldAlert, TrendingDown, Minus } from 'lucide-react'
import { api } from '@/services/api'
import type { BriefingDetailResponse, BriefingMarketData, BriefingSentiment, BriefingSectorFundFlow, BriefingAnnouncements, BriefingDragonTiger, BriefingIndustryRanking, BriefingHotStock, BriefingMacroData, BriefingNewsItem, BriefingWatchlistItem, BriefingPortfolioItem, BriefingTradingAdvice, YangYinHistoryPoint } from '@/types'

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
    const [yangYinHistory, setYangYinHistory] = useState<YangYinHistoryPoint[]>([])

    useEffect(() => {
        api.listBriefings(60).then(res => {
            const dates = [...new Set(res.items
                .filter(it => it.status === 'completed')
                .map(it => it.date)
            )].sort().reverse()
            setAvailableDates(dates)
        }).catch(() => {})
        api.getYangYinHistory(30).then(setYangYinHistory).catch(() => {})
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

            {/* 大盘点金 -- always shown, independent of briefing */}
            <DapanDianJin history={yangYinHistory} />

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
                    <USTechMappingSection
                        data={briefing.market_data?.us_tech_mapping}
                        adviceContent={briefing.trading_advice?.content}
                    />
                    <TradingPlanSection advice={briefing.trading_advice} />
                    <MarketOverview data={briefing.market_data} />

                    {/* LLM input data — collapsed for reference */}
                    <details className="group">
                        <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                            原始数据（信号源 · 共8组）
                        </summary>
                        <div className="mt-4 space-y-6">
                            <SentimentSection data={briefing.market_data?.market_sentiment} />
                            <SectorFundFlowSection data={briefing.market_data?.sector_fund_flow} />
                            <IndustrySection data={briefing.market_data?.industry_ranking} />
                            <HotStocksSection data={briefing.market_data?.hot_stocks} />
                            <DragonTigerSection data={briefing.market_data?.dragon_tiger} />
                            <AnnouncementSection data={briefing.market_data?.announcements} />
                            <MacroSection data={briefing.market_data?.macro_data} />
                            <TopNewsSection news={briefing.top_news} />
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

function DapanDianJin({ history }: { history?: YangYinHistoryPoint[] }) {
    if (!history || history.length < 2) return null
    const latest = history[history.length - 1]
    const prev = history[history.length - 2]
    const diff = latest.yang_pct - prev.yang_pct
    const recent = [...history].reverse()

    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 dark:border-slate-700/50 dark:bg-slate-900/50">
            <h2 className="mb-3 sm:mb-4 flex items-center gap-2 text-base sm:text-lg font-semibold">
                <Activity className="h-4 w-4 sm:h-5 sm:w-5 text-amber-400" />
                大盘点金
            </h2>
            <div className="flex items-center gap-3 sm:gap-4 mb-3 sm:mb-4">
                <div>
                    <div className="text-[10px] sm:text-xs text-slate-400">最新阳谱{latest.updated_at ? ` ${latest.updated_at}` : ''}</div>
                    <div className="text-2xl sm:text-3xl font-bold text-red-400 tabular-nums">{latest.yang_pct.toFixed(1)}%</div>
                </div>
                <div className="flex items-center gap-1 ml-2 sm:ml-4">
                    {diff > 0 ? (
                        <TrendingUp className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-red-400" />
                    ) : diff < 0 ? (
                        <TrendingDown className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-green-400" />
                    ) : (
                        <Minus className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-slate-400" />
                    )}
                    <span className={`text-xs sm:text-sm font-medium tabular-nums ${diff > 0 ? 'text-red-400' : diff < 0 ? 'text-green-400' : 'text-slate-400'}`}>
                        较前日 {diff > 0 ? '+' : ''}{diff.toFixed(1)}%
                    </span>
                </div>
            </div>
            <div className="overflow-x-auto -mx-4 sm:mx-0">
            <table className="text-xs sm:text-sm border-separate border-spacing-0">
                <thead>
                    <tr className="text-center text-[10px] sm:text-xs text-slate-400">
                        <th className="sticky left-0 z-10 bg-white dark:bg-slate-900/50 pb-2 sm:pb-3 pr-3 sm:pr-4 font-medium text-left">日期</th>
                        {recent.map(r => (
                            <th key={r.trade_date} className="pb-2 sm:pb-3 px-2 sm:px-4 font-medium min-w-[4.5rem] sm:min-w-[5rem]">{r.trade_date}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    <tr className="border-b border-slate-50 dark:border-slate-800/50">
                        <td className="sticky left-0 z-10 bg-white dark:bg-slate-900/50 py-1.5 sm:py-2 pr-3 sm:pr-4 font-medium text-black dark:text-white">阳谱</td>
                        {recent.map(r => (
                            <td key={r.trade_date} className="py-1.5 sm:py-2 px-2 sm:px-4 text-center text-black dark:text-white tabular-nums">{r.yang_pct.toFixed(1)}%</td>
                        ))}
                    </tr>
                    <tr>
                        <td className="sticky left-0 z-10 bg-white dark:bg-slate-900/50 py-1.5 sm:py-2 pr-3 sm:pr-4 font-medium text-black dark:text-white">阴谱</td>
                        {recent.map(r => (
                            <td key={r.trade_date} className="py-1.5 sm:py-2 px-2 sm:px-4 text-center text-black dark:text-white tabular-nums">{r.yin_pct.toFixed(1)}%</td>
                        ))}
                    </tr>
                </tbody>
            </table>
            </div>
        </div>
    )
}

function MarketOverview({ data }: { data?: BriefingMarketData | null }) {
    if (!data) return <SectionCard title="今日大势" icon={Globe}><p className="text-slate-500">暂无数据</p></SectionCard>

    return (
        <SectionCard title="今日大势" icon={Globe}>
            <div className="grid gap-3 sm:grid-cols-2">
                {/* US + HK + A50 — core external signals */}
                <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3 dark:border-slate-700/50 dark:bg-slate-800/30">
                    <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">美股</h3>
                    <div className="space-y-1.5">
                        {(data.us_indices || []).map(idx => (
                            <div key={idx.symbol} className="flex items-center justify-between text-sm">
                                <span className="text-slate-600 dark:text-slate-400">{idx.name}</span>
                                <span className="font-medium tabular-nums">{idx.close?.toFixed(2)}</span>
                                <PctBadge pct={idx.change_pct} />
                            </div>
                        ))}
                    </div>
                    {data.hk_index && data.hk_index.length > 0 && (
                        <>
                            <h3 className="mb-2 mt-3 text-xs font-medium uppercase tracking-wider text-slate-400">港股</h3>
                            <div className="space-y-1.5">
                                {data.hk_index.map(idx => (
                                    <div key={idx.name} className="flex items-center justify-between text-sm">
                                        <span className="text-slate-600 dark:text-slate-400">{idx.name}</span>
                                        <span className="font-medium tabular-nums">{idx.close?.toFixed(2)}</span>
                                        <PctBadge pct={idx.change_pct} />
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                    {data.a50_futures && (
                        <>
                            <h3 className="mb-2 mt-3 text-xs font-medium uppercase tracking-wider text-slate-400">A50期货</h3>
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-slate-600 dark:text-slate-400">{data.a50_futures.name}</span>
                                <span className="font-medium tabular-nums">{data.a50_futures.close?.toFixed(2)}</span>
                                <PctBadge pct={data.a50_futures.change_pct} />
                            </div>
                        </>
                    )}
                </div>

                {/* ADRs + Commodities + FX + Fund Flow — supporting */}
                <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3 dark:border-slate-700/50 dark:bg-slate-800/30">
                    {data.chinese_adrs && data.chinese_adrs.length > 0 && (
                        <>
                            <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">中概股龙头</h3>
                            <div className="space-y-1.5">
                                {data.chinese_adrs.slice(0, 6).map(a => (
                                    <div key={a.symbol} className="flex items-center justify-between text-sm">
                                        <span className="text-slate-600 dark:text-slate-400">{a.name}</span>
                                        <span className="font-medium tabular-nums">{a.close?.toFixed(2)}</span>
                                        <PctBadge pct={a.change_pct} />
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                    {data.commodities && data.commodities.length > 0 && (
                        <>
                            <h3 className="mb-2 mt-3 text-xs font-medium uppercase tracking-wider text-slate-400">大宗商品</h3>
                            <div className="space-y-1.5">
                                {data.commodities.map(c => (
                                    <div key={c.name} className="flex items-center justify-between text-sm">
                                        <span className="text-slate-600 dark:text-slate-400">{c.name}</span>
                                        <span className="font-medium tabular-nums">{c.close?.toFixed(2)}</span>
                                        <PctBadge pct={c.change_pct} />
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                    {data.fx && data.fx.length > 0 && (
                        <>
                            <h3 className="mb-2 mt-3 text-xs font-medium uppercase tracking-wider text-slate-400">汇率</h3>
                            <div className="space-y-1.5">
                                {data.fx.map(f => (
                                    <div key={f.name} className="flex items-center justify-between text-sm">
                                        <span className="text-slate-600 dark:text-slate-400">{f.name}</span>
                                        <span className="font-medium tabular-nums">{f.close?.toFixed(4)}</span>
                                        <PctBadge pct={f.change_pct} />
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                    {data.fund_flow && (
                        <>
                            <h3 className="mb-2 mt-3 text-xs font-medium uppercase tracking-wider text-slate-400">资金面</h3>
                            <div className="space-y-1.5 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-slate-500">主力净流入</span>
                                    <span className={data.fund_flow.main_net >= 0 ? 'text-red-500 font-medium' : 'text-green-500 font-medium'}>
                                        {(data.fund_flow.main_net / 1e8).toFixed(2)}亿
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">超大单净流入</span>
                                    <span>{(data.fund_flow.super_large_net / 1e8).toFixed(2)}亿</span>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </SectionCard>
    )
}

function USTechMappingSection({ data, adviceContent }: {
    data?: import('@/types').USTechMapping | null
    adviceContent?: string
}) {
    if (!data || !data.sectors || data.sectors.length === 0) return null

    const sentimentIcon = (s: string) => {
        if (s === 'bullish') return <TrendingUp className="h-4 w-4 text-red-500" />
        if (s === 'bearish') return <TrendingDown className="h-4 w-4 text-green-500" />
        return <Minus className="h-4 w-4 text-slate-400" />
    }

    const sentimentColor = (s: string) => {
        if (s === 'bullish') return 'border-red-200 bg-red-50/50 dark:border-red-900/30 dark:bg-red-950/20'
        if (s === 'bearish') return 'border-green-200 bg-green-50/50 dark:border-green-900/30 dark:bg-green-950/20'
        return 'border-slate-200 bg-slate-50/50 dark:border-slate-700/30 dark:bg-slate-800/20'
    }

    const sentimentLabel = (s: string) => {
        if (s === 'bullish') return '正面'
        if (s === 'bearish') return '利空'
        return '中性'
    }

    // Extract AI interpretation section from trading_advice content
    let aiInterpretation = ''
    if (adviceContent) {
        const match = adviceContent.match(/## 🔬 美股科技映射[\s\S]*?(?=## 📊|$)/)
        if (match) {
            aiInterpretation = match[0].replace('## 🔬 美股科技映射', '').trim()
        }
    }

    // Overall sentiment bar
    const overallLabel = (s: string) => {
        if (s === 'bullish') return '整体偏多'
        if (s === 'bearish') return '整体偏空'
        if (s === 'mixed') return '涨跌互现'
        return '信号中性'
    }
    const overallColor = (s: string) => {
        if (s === 'bullish') return 'text-red-600 bg-red-50 dark:bg-red-950/20'
        if (s === 'bearish') return 'text-green-600 bg-green-50 dark:bg-green-950/20'
        return 'text-slate-500 bg-slate-50 dark:bg-slate-800/20'
    }

    return (
        <SectionCard title="美股科技映射" icon={Cpu}>
            {/* AI interpretation */}
            {aiInterpretation && (
                <div className="mb-4 rounded-lg border-l-4 border-blue-400 bg-blue-50/50 px-4 py-3 text-sm leading-relaxed text-slate-700 dark:border-blue-500 dark:bg-blue-950/20 dark:text-slate-300">
                    {aiInterpretation.split('\n').filter(l => l.trim()).map((line, i) => {
                        const trimmed = line.replace(/^\*+|\*+$/g, '').trim()
                        if (!trimmed) return null
                        if (line.startsWith('**')) {
                            return <p key={i} className="mt-2 font-medium text-slate-800 dark:text-slate-200">{trimmed}</p>
                        }
                        return <p key={i} className="mt-1">{trimmed}</p>
                    })}
                </div>
            )}

            {/* Sector cards grid */}
            <div className="grid gap-3 sm:grid-cols-3">
                {data.sectors.map(sec => (
                    <div key={sec.name} className={`rounded-lg border p-3 ${sentimentColor(sec.sentiment)}`}>
                        <div className="mb-2 flex items-center justify-between">
                            <span className="text-sm font-semibold">{sec.name}</span>
                            <span className="flex items-center gap-1 text-xs">
                                {sentimentIcon(sec.sentiment)}
                                {sentimentLabel(sec.sentiment)}
                            </span>
                        </div>
                        <div className="space-y-1 mb-2">
                            {sec.stocks.map(s => (
                                <div key={s.symbol} className="flex items-center justify-between text-xs">
                                    <span className="flex items-center gap-1">
                                        <span className="text-slate-600 dark:text-slate-400">{s.name}</span>
                                        {s.is_stock ? (
                                            <span className="rounded bg-amber-100 px-1 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">龙头</span>
                                        ) : (
                                            <span className="rounded bg-slate-100 px-1 py-0.5 text-[10px] text-slate-400 dark:bg-slate-800">ETF</span>
                                        )}
                                    </span>
                                    <span className="tabular-nums font-medium">{(s.close ?? 0).toFixed(2)}</span>
                                    <PctBadge pct={s.change_pct} />
                                </div>
                            ))}
                        </div>
                        <p className="text-xs text-slate-400">→ {sec.a_mapping}</p>
                    </div>
                ))}
            </div>

            {/* Risk indicators bar */}
            {data.risk_indicators && Object.keys(data.risk_indicators).length > 0 && (
                <div className="mt-3 flex items-center gap-4 rounded-lg border border-slate-100 bg-slate-50/50 px-4 py-2 text-xs dark:border-slate-700/50 dark:bg-slate-800/30">
                    <ShieldAlert className="h-4 w-4 text-slate-400" />
                    <span className="text-slate-500">风险偏好</span>
                    {Object.entries(data.risk_indicators).map(([k, v]) => (
                        <span key={k} className="flex items-center gap-1">
                            <span className="text-slate-600 dark:text-slate-400">{v.name}</span>
                            <span className="tabular-nums font-medium">{(v.close ?? 0).toFixed(2)}</span>
                            <PctBadge pct={v.change_pct} />
                        </span>
                    ))}
                </div>
            )}

            {/* Overall sentiment tag */}
            <div className="mt-3 flex items-center gap-2 text-xs">
                <span className={`rounded-full px-2 py-0.5 font-medium ${overallColor(data.overall_sentiment)}`}>
                    {overallLabel(data.overall_sentiment)}
                </span>
                {data.error && <span className="text-slate-400">部分数据获取失败</span>}
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

    const { content, sentiment, watchlist_plan, portfolio_plan, error } = advice

    return (
        <div className="space-y-5">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
                <Lightbulb className="h-5 w-5 text-blue-500" />
                盘前交易计划
            </h2>
            {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-500 dark:border-rose-900/50 dark:bg-rose-950/30">
                    AI生成失败: {error}，以下为程序化分析数据仅供参考。
                </div>
            )}

            {/* Markdown content — split into styled section cards */}
            {content && <MarkdownSections content={content} />}

            {/* Old JSON format — fallback */}
            {!content && (
                <div className="card space-y-6">
                    {sentiment && (
                        <div className="rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 p-4 dark:from-blue-950/30 dark:to-indigo-950/20">
                            <h3 className="mb-2 text-sm font-medium text-blue-700 dark:text-blue-300">1. 今日情绪与主线</h3>
                            <p className="text-sm leading-relaxed text-blue-900 dark:text-blue-200">{sentiment}</p>
                        </div>
                    )}
                    {watchlist_plan && watchlist_plan.length > 0 && (
                        <div>
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
                </div>
            )}

            {!content && !sentiment && !watchlist_plan?.length && !portfolio_plan?.length && !error && (
                <p className="text-sm text-slate-500">AI 交易计划尚未生成，请点击"重新生成"。</p>
            )}
        </div>
    )
}

// ─── Markdown Section Parser ────────────────────────────────────────

const SECTION_STYLES: Record<string, { card: string; header: string }> = {
    '🧭': { card: 'border-l-blue-500 bg-gradient-to-r from-blue-50/60 to-white dark:from-blue-950/20 dark:to-slate-900', header: 'text-blue-700 dark:text-blue-300' },
    '📊': { card: 'border-l-emerald-500 bg-gradient-to-r from-emerald-50/60 to-white dark:from-emerald-950/20 dark:to-slate-900', header: 'text-emerald-700 dark:text-emerald-300' },
    '🎯': { card: 'border-l-amber-500 bg-gradient-to-r from-amber-50/60 to-white dark:from-amber-950/20 dark:to-slate-900', header: 'text-amber-700 dark:text-amber-300' },
    '🛡️': { card: 'border-l-rose-500 bg-gradient-to-r from-rose-50/60 to-white dark:from-rose-950/20 dark:to-slate-900', header: 'text-rose-700 dark:text-rose-300' },
    '⚠️': { card: 'border-l-red-500 bg-gradient-to-r from-red-50/60 to-white dark:from-red-950/20 dark:to-slate-900', header: 'text-red-700 dark:text-red-300' },
}

function mdToHtml(text: string): string {
    return text
        // Bold **key**：value lines
        .replace(/^- \*\*(.+?)\*\*(.*)$/gm, '<div class="flex gap-2 text-sm py-0.5"><span class="font-semibold text-slate-800 dark:text-slate-200 shrink-0">$1</span><span class="text-slate-600 dark:text-slate-400">$2</span></div>')
        // Bold within text
        .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-slate-800 dark:text-slate-200">$1</strong>')
        // Stock plan headers: * **[code.name] 战法：xxx**
        .replace(/^\* (.+)$/gm, '<div class="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 text-sm font-medium text-slate-800 dark:text-slate-200">$1</div>')
        // Plain list items (indented, non-bold)
        .replace(/^  - (.+)$/gm, '<div class="text-sm text-slate-600 dark:text-slate-400 ml-4 py-0.5">$1</div>')
        // Remaining list items
        .replace(/^- (.+)$/gm, '<li class="text-sm text-slate-600 dark:text-slate-400 ml-4">$1</li>')
        .replace(/\n\n/g, '<br/>')
}

function MarkdownSections({ content }: { content: string }) {
    // Split by ## headers, preserving the header text
    const sections = content.split(/^## /gm).filter(Boolean)

    return (
        <div className="space-y-4">
            {sections.map((section, i) => {
                const newlineIdx = section.indexOf('\n')
                const header = newlineIdx > 0 ? section.slice(0, newlineIdx).trim() : section.trim()
                const body = newlineIdx > 0 ? section.slice(newlineIdx + 1).trim() : ''

                // Determine style by emoji in header
                const emoji = Object.keys(SECTION_STYLES).find(e => header.includes(e))
                const style = emoji ? SECTION_STYLES[emoji] : { card: 'border-l-slate-400 bg-white dark:bg-slate-900', header: 'text-slate-700 dark:text-slate-300' }

                return (
                    <div key={i} className={`card border-l-4 ${style.card}`}>
                        <h3 className={`text-base font-semibold mb-3 ${style.header}`}>{header}</h3>
                        <div
                            className="space-y-1"
                            dangerouslySetInnerHTML={{ __html: mdToHtml(body) }}
                        />
                    </div>
                )
            })}
        </div>
    )
}

function SentimentSection({ data }: { data?: BriefingSentiment | null }) {
    if (!data) return null
    const { limit_up_count, limit_down_count, bust_rate_pct, max_streak, top_streak_stocks, volume_change_pct } = data

    return (
        <SectionCard title="市场情绪" icon={Activity}>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800/50">
                    <div className="text-2xl font-bold text-red-500">{limit_up_count}</div>
                    <div className="text-xs text-slate-500">涨停家数</div>
                </div>
                <div className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800/50">
                    <div className="text-2xl font-bold text-green-500">{limit_down_count}</div>
                    <div className="text-xs text-slate-500">跌停家数</div>
                </div>
                <div className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800/50">
                    <div className="text-2xl font-bold text-slate-700 dark:text-slate-300">{bust_rate_pct}%</div>
                    <div className="text-xs text-slate-500">炸板率</div>
                </div>
                <div className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800/50">
                    <div className="text-2xl font-bold text-amber-500">{max_streak}板</div>
                    <div className="text-xs text-slate-500">最高连板</div>
                </div>
            </div>
            {top_streak_stocks.length > 0 && (
                <div className="mt-3 space-y-2">
                    {top_streak_stocks.map((s, i) => {
                        const sealAmt = (s as any).seal_amount_wan
                        const firstSeal = (s as any).first_seal_time
                        const bustCnt = (s as any).bust_count
                        const cngPct = (s as any).change_pct
                        return (
                            <div key={i} className="rounded bg-amber-50 px-3 py-2 text-xs dark:bg-amber-950/30">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-medium text-amber-800 dark:text-amber-300">{s.name}</span>
                                    <span className="text-amber-600 dark:text-amber-400">{s.streak}连板</span>
                                    {cngPct != null && (
                                        <span className={cngPct >= 0 ? 'text-red-500' : 'text-green-500'}>
                                            {cngPct >= 0 ? '+' : ''}{cngPct.toFixed(1)}%
                                        </span>
                                    )}
                                    {sealAmt && (
                                        <span className="text-slate-500">封单{sealAmt >= 10000 ? `${(sealAmt/10000).toFixed(1)}亿` : `${sealAmt}万`}</span>
                                    )}
                                    {firstSeal && (
                                        <span className="text-slate-500">首封{firstSeal}</span>
                                    )}
                                    {bustCnt && bustCnt > 0 && (
                                        <span className="text-rose-500">炸{bustCnt}次</span>
                                    )}
                                </div>
                                {s.reason && <div className="mt-1 text-slate-400">{s.reason}</div>}
                            </div>
                        )
                    })}
                </div>
            )}
            {volume_change_pct != null && (
                <div className="mt-3 text-xs text-slate-500">
                    上证指数量能较前日{volume_change_pct >= 0 ? '放量' : '缩量'}{Math.abs(volume_change_pct).toFixed(1)}%
                </div>
            )}
        </SectionCard>
    )
}

function DragonTigerSection({ data }: { data?: BriefingDragonTiger | null }) {
    if (!data || (data.top_net_buy.length === 0 && data.institution_net == null)) return null
    return (
        <SectionCard title="龙虎榜" icon={Zap}>
            {data.institution_net != null && (
                <div className="mb-3 text-sm">
                    机构净买入: <span className={data.institution_net >= 0 ? 'text-red-500 font-medium' : 'text-green-500 font-medium'}>
                        {data.institution_net >= 0 ? '+' : ''}{data.institution_net.toFixed(2)}亿
                    </span>
                </div>
            )}
            {data.top_net_buy.length > 0 && (
                <div>
                    <h4 className="mb-2 text-xs font-medium text-slate-500">净买入 TOP</h4>
                    <div className="flex flex-wrap gap-2">
                        {data.top_net_buy.slice(0, 8).map((s, i) => (
                            <span key={i} className="rounded bg-red-50 px-2 py-1 text-xs dark:bg-red-950/30">
                                <span className="text-red-600 dark:text-red-400">{s.name}</span>
                                <span className="ml-1 text-slate-500">净买{s.net_buy_wan}万</span>
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </SectionCard>
    )
}

function IndustrySection({ data }: { data?: BriefingIndustryRanking | null }) {
    if (!data || data.top.length === 0) return null
    return (
        <SectionCard title="行业板块" icon={BarChart3}>
            <div className="grid gap-4 sm:grid-cols-2">
                <div>
                    <h4 className="mb-2 text-xs font-medium text-red-500">涨幅 TOP 10</h4>
                    <div className="space-y-1">
                        {data.top.slice(0, 10).map((r, i) => (
                            <div key={i} className="flex items-center justify-between rounded bg-slate-50 px-2 py-1 text-xs dark:bg-slate-800/50">
                                <span>{r.name}</span>
                                <span className="ml-2 text-red-500">+{r.change_pct.toFixed(2)}%</span>
                                <span className="ml-2 text-slate-400">{r.leader}</span>
                            </div>
                        ))}
                    </div>
                </div>
                <div>
                    <h4 className="mb-2 text-xs font-medium text-green-500">跌幅 TOP 10</h4>
                    <div className="space-y-1">
                        {data.bottom.slice(0, 10).map((r, i) => (
                            <div key={i} className="flex items-center justify-between rounded bg-slate-50 px-2 py-1 text-xs dark:bg-slate-800/50">
                                <span>{r.name}</span>
                                <span className="ml-2 text-green-500">{r.change_pct.toFixed(2)}%</span>
                                <span className="ml-2 text-slate-400">{r.leader}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </SectionCard>
    )
}

function HotStocksSection({ data }: { data?: BriefingHotStock[] | null }) {
    if (!data || data.length === 0) return null
    return (
        <SectionCard title="今日强势股" icon={TrendingUp}>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700">
                            <th className="py-2 text-left text-xs font-medium text-slate-500">股票</th>
                            <th className="py-2 text-right text-xs font-medium text-slate-500">涨幅</th>
                            <th className="py-2 text-right text-xs font-medium text-slate-500">换手</th>
                            <th className="py-2 text-left text-xs font-medium text-slate-500">题材归因</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.slice(0, 15).map((s, i) => (
                            <tr key={i} className="border-b border-slate-100 dark:border-slate-800">
                                <td className="whitespace-nowrap py-1.5 pr-3">
                                    <span className="font-medium">{s.name}</span>
                                    <span className="ml-1 text-xs text-slate-400">{s.code}</span>
                                </td>
                                <td className={`py-1.5 text-right font-medium ${s.change_pct >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                                    {s.change_pct >= 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
                                </td>
                                <td className="py-1.5 text-right text-slate-500">{s.turnover.toFixed(2)}%</td>
                                <td className="py-1.5 text-xs text-slate-600 dark:text-slate-400">{s.reason || '-'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </SectionCard>
    )
}

function MacroSection({ data }: { data?: BriefingMacroData | null }) {
    if (!data || (!data.pmi && !data.cpi && !data.social_financing)) return null
    return (
        <SectionCard title="宏观经济" icon={Landmark}>
            <div className="grid gap-4 sm:grid-cols-3">
                {data.pmi && (
                    <div className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800/50">
                        <div className="text-sm font-medium text-slate-500">PMI ({data.pmi.date})</div>
                        <div className="mt-1 text-lg font-bold">制造业 {data.pmi.manufacturing}</div>
                        {data.pmi.non_manufacturing && (
                            <div className="text-sm text-slate-500">非制造业 {data.pmi.non_manufacturing}</div>
                        )}
                    </div>
                )}
                {data.cpi && (
                    <div className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800/50">
                        <div className="text-sm font-medium text-slate-500">CPI ({data.cpi.date})</div>
                        <div className={`mt-1 text-lg font-bold ${data.cpi.national_yoy >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                            同比 {data.cpi.national_yoy >= 0 ? '+' : ''}{data.cpi.national_yoy}%
                        </div>
                    </div>
                )}
                {data.social_financing && (
                    <div className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800/50">
                        <div className="text-sm font-medium text-slate-500">社融 ({data.social_financing.date})</div>
                        <div className="mt-1 text-lg font-bold">{data.social_financing.value_yi}万亿</div>
                    </div>
                )}
            </div>
        </SectionCard>
    )
}

function SectorFundFlowSection({ data }: { data?: BriefingSectorFundFlow | null }) {
    if (!data || (!data.top_inflow?.length && !data.top_outflow?.length)) return null
    return (
        <SectionCard title="板块资金流向" icon={DollarSign}>
            <div className="grid gap-4 sm:grid-cols-2">
                <div>
                    <h4 className="mb-2 text-xs font-medium text-red-500">主力净流入 TOP5</h4>
                    <div className="space-y-1">
                        {data.top_inflow?.slice(0, 5).map((item, i) => (
                            <div key={i} className="flex justify-between rounded bg-red-50 px-3 py-1.5 text-xs dark:bg-red-950/20">
                                <span>{item.name}</span>
                                <span className="font-medium text-red-600 dark:text-red-400">+{item.net_inflow_yi}亿</span>
                            </div>
                        ))}
                    </div>
                </div>
                <div>
                    <h4 className="mb-2 text-xs font-medium text-green-500">主力净流出 TOP5</h4>
                    <div className="space-y-1">
                        {data.top_outflow?.slice(0, 5).map((item, i) => (
                            <div key={i} className="flex justify-between rounded bg-green-50 px-3 py-1.5 text-xs dark:bg-green-950/20">
                                <span>{item.name}</span>
                                <span className="font-medium text-green-600 dark:text-green-400">{item.net_inflow_yi}亿</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </SectionCard>
    )
}

function AnnouncementSection({ data }: { data?: BriefingAnnouncements | null }) {
    if (!data || (!data.major_events?.length && !data.shareholder_changes?.length)) return null
    return (
        <SectionCard title="重大公告" icon={Bell}>
            <div className="space-y-3">
                {data.major_events && data.major_events.length > 0 && (
                    <div>
                        <h4 className="mb-2 text-xs font-medium text-amber-500">重大事项</h4>
                        <div className="max-h-40 overflow-y-auto space-y-1">
                            {data.major_events.slice(0, 10).map((ev, i) => (
                                <div key={i} className="rounded bg-slate-50 px-3 py-1.5 text-xs dark:bg-slate-800/50">
                                    <span className="font-medium text-slate-700 dark:text-slate-300">{ev.name}({ev.code})</span>
                                    <span className="ml-2 text-slate-500">{ev.title}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {data.shareholder_changes && data.shareholder_changes.length > 0 && (
                    <div>
                        <h4 className="mb-2 text-xs font-medium text-rose-500">持股变动/减持预警</h4>
                        <div className="max-h-32 overflow-y-auto space-y-1">
                            {data.shareholder_changes.slice(0, 5).map((ev, i) => (
                                <div key={i} className="rounded border border-rose-100 bg-rose-50 px-3 py-1.5 text-xs dark:border-rose-900/30 dark:bg-rose-950/20">
                                    <span className="font-medium text-rose-700 dark:text-rose-300">{ev.name}({ev.code})</span>
                                    <span className="ml-2 text-rose-500">{ev.title}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </SectionCard>
    )
}
