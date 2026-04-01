import {
    ArrowDownRight,
    ArrowUpRight,
    Loader2,
    RefreshCw,
    ShieldAlert,
    Target,
    TrendingUp,
    Wallet,
} from 'lucide-react'
import { type CSSProperties, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import type { TrackingBoardItem, TrackingBoardResponse } from '@/types'

const CLAMP_TWO_LINES_STYLE: CSSProperties = {
    display: '-webkit-box',
    WebkitLineClamp: 2,
    WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
}

type BoardViewMode = 'simple' | 'detailed'
type BoardTone = 'blue' | 'emerald' | 'rose' | 'amber'

export default function TrackingBoardPanel() {
    const { user } = useAuthStore()
    const [trackingBoard, setTrackingBoard] = useState<TrackingBoardResponse | null>(null)
    const [trackingLoading, setTrackingLoading] = useState(true)
    const [trackingRefreshing, setTrackingRefreshing] = useState(false)
    const [trackingError, setTrackingError] = useState<string | null>(null)
    const [viewMode, setViewMode] = useState<BoardViewMode>(() => {
        try {
            const stored = localStorage.getItem('ta-tracking-board-view')
            return stored === 'simple' || stored === 'detailed' ? stored : 'simple'
        } catch {
            return 'simple'
        }
    })
    const navigate = useNavigate()

    const trackingItems = trackingBoard?.items || []
    const trackingRefreshSeconds = trackingBoard?.refresh_interval_seconds || 20
    const liveMarketValueTotal = trackingItems.reduce(
        (sum, item) => sum + (item.live_market_value ?? item.market_value ?? 0),
        0,
    )
    const floatingPnlTotal = trackingItems.reduce(
        (sum, item) => sum + (item.floating_pnl ?? 0),
        0,
    )
    const lastQuoteTime = useMemo(() => {
        const values = trackingItems
            .map(item => item.quote_time)
            .filter((value): value is string => Boolean(value))
        return values.length > 0 ? values[0] : null
    }, [trackingItems])

    useEffect(() => {
        try {
            localStorage.setItem('ta-tracking-board-view', viewMode)
        } catch {}
    }, [viewMode])

    useEffect(() => {
        if (!user?.id) return
        let cancelled = false

        const loadTrackingBoard = async (silent: boolean) => {
            if (silent) {
                setTrackingRefreshing(true)
            } else {
                setTrackingLoading(true)
            }

            try {
                const response = await api.getDashboardTrackingBoard()
                if (cancelled) return
                setTrackingBoard(response)
                setTrackingError(null)
            } catch (error) {
                if (cancelled) return
                setTrackingError(error instanceof Error ? error.message : '跟踪看板加载失败')
            } finally {
                if (!cancelled) {
                    setTrackingLoading(false)
                    setTrackingRefreshing(false)
                }
            }
        }

        void loadTrackingBoard(false)
        const intervalId = window.setInterval(() => {
            void loadTrackingBoard(true)
        }, trackingRefreshSeconds * 1000)

        return () => {
            cancelled = true
            window.clearInterval(intervalId)
        }
    }, [trackingRefreshSeconds, user?.id])

    return (
        <div className="card overflow-hidden">
            <div className="flex flex-col gap-4 border-b border-slate-200 pb-4 dark:border-slate-700 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <Wallet className="h-5 w-5 text-emerald-500" />
                        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">QMT 跟踪看板</h2>
                    </div>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                        最新价优先使用 QMT / xtquant，简洁版聚焦展示当日 K 线与成本价标记。
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-700/70">
                        账户：{trackingBoard?.account_id || '--'}
                    </span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-700/70">
                        自动刷新：{trackingRefreshSeconds}s
                    </span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-700/70">
                        上一交易日：{trackingBoard?.previous_trade_date || '--'}
                    </span>
                    <ViewModeSwitch value={viewMode} onChange={setViewMode} />
                </div>
            </div>

            {trackingLoading && !trackingBoard ? (
                <div className="flex items-center justify-center py-12 text-slate-500 dark:text-slate-400">
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    正在加载跟踪看板...
                </div>
            ) : trackingItems.length === 0 ? (
                <div className="py-10 text-center">
                    <Wallet className="mx-auto mb-3 h-12 w-12 text-slate-300 dark:text-slate-600" />
                    <p className="text-slate-600 dark:text-slate-300">当前还没有可展示的 QMT 持仓</p>
                    <p className="mt-1 text-sm text-slate-400 dark:text-slate-500">
                        到设置页完成 QMT 同步后，这里会自动出现实时跟踪卡片。
                    </p>
                </div>
            ) : viewMode === 'simple' ? (
                <SimpleBoardView
                    items={trackingItems}
                    trackingRefreshing={trackingRefreshing}
                    trackingError={trackingError}
                    lastQuoteTime={lastQuoteTime}
                />
            ) : (
                <DetailedBoardView
                    items={trackingItems}
                    trackingBoard={trackingBoard}
                    trackingRefreshing={trackingRefreshing}
                    trackingError={trackingError}
                    liveMarketValueTotal={liveMarketValueTotal}
                    floatingPnlTotal={floatingPnlTotal}
                    onAnalyze={symbol => navigate(`/analysis?symbol=${symbol}`)}
                    onOpenReport={reportId => navigate(`/reports?report=${reportId}`)}
                />
            )}
        </div>
    )
}

function ViewModeSwitch({
    value,
    onChange,
}: {
    value: BoardViewMode
    onChange: (mode: BoardViewMode) => void
}) {
    return (
        <div className="inline-flex rounded-full bg-slate-100 p-1 dark:bg-slate-800">
            {([
                { id: 'detailed', label: '详细版' },
                { id: 'simple', label: '简洁版' },
            ] as const).map(option => (
                <button
                    key={option.id}
                    type="button"
                    onClick={() => onChange(option.id)}
                    className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                        value === option.id
                            ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-slate-100'
                            : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                    }`}
                >
                    {option.label}
                </button>
            ))}
        </div>
    )
}

function SimpleBoardView({
    items,
    trackingRefreshing,
    trackingError,
    lastQuoteTime,
}: {
    items: TrackingBoardItem[]
    trackingRefreshing: boolean
    trackingError: string | null
    lastQuoteTime: string | null
}) {
    return (
        <div className="overflow-hidden rounded-[24px] border border-slate-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
                <div className="min-w-[1180px]">
                    <div className="grid grid-cols-[1.36fr_0.88fr_0.74fr_0.78fr_1.28fr_0.86fr_0.96fr] gap-4 border-b border-slate-200 bg-slate-50 px-5 py-3 text-xs font-medium tracking-[0.12em] text-slate-500">
                        <div>标的</div>
                        <div>当日 K 线</div>
                        <div>最新价</div>
                        <div>涨跌幅</div>
                        <div className="flex items-center gap-1">
                            <span>当日区间</span>
                            <RangeInfoTooltip variant="simple" />
                        </div>
                        <div>持仓盈亏%</div>
                        <div>成交量 / 成交额</div>
                    </div>

                    {items.map(item => (
                        <SimpleTrackingRow key={item.symbol} item={item} />
                    ))}
                </div>
            </div>

            <div className="flex flex-col gap-2 border-t border-slate-200 px-5 py-4 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-2">
                    <span className={`inline-flex h-2.5 w-2.5 rounded-full ${trackingError ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                    <span>{trackingError ? `最近刷新异常：${trackingError}` : '实时监控中'}</span>
                    {trackingRefreshing && <RefreshCw className="h-3.5 w-3.5 animate-spin text-slate-400" />}
                </div>
                <div className="text-slate-400">更新：{formatFooterTime(lastQuoteTime)}</div>
            </div>
        </div>
    )
}

function SimpleTrackingRow({ item }: { item: TrackingBoardItem }) {
    const priceChangePct = item.price_change_pct ?? null
    const isUp = (priceChangePct ?? 0) >= 0
    const costToneClass = item.average_cost != null && item.live_price != null && item.average_cost > item.live_price
        ? 'bg-emerald-500'
        : 'bg-rose-500'
    const holdingChangePct = item.floating_pnl_pct ?? null
    const priceColor = priceChangePct == null
        ? 'text-slate-800'
        : isUp
            ? 'text-rose-600'
            : 'text-emerald-600'
    const rangeAlert = getModelRangeAlert(item)

    return (
        <div className="grid grid-cols-[1.36fr_0.88fr_0.74fr_0.78fr_1.28fr_0.86fr_0.96fr] gap-4 border-b border-slate-200 px-5 py-5 last:border-b-0">
            <div className="min-w-0">
                <div className="truncate text-[18px] font-semibold text-slate-900">{item.name}</div>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
                    <span>{item.symbol}</span>
                    <span>成本 {formatPlainPrice(item.average_cost)}</span>
                    <span>持仓 {formatShares(item.current_position)}</span>
                </div>
            </div>

            <SimpleDayCandle item={item} />

            <div className={`self-center text-[22px] font-semibold ${priceColor}`}>
                {formatPlainPrice(item.live_price)}
            </div>

            <div className="self-center">
                <span className={`inline-flex min-w-[96px] items-center justify-center rounded-full px-3 py-2 text-[18px] font-semibold ${
                    priceChangePct == null
                        ? 'bg-slate-100 text-slate-400'
                        : isUp
                            ? 'bg-rose-50 text-rose-600'
                            : 'bg-emerald-50 text-emerald-600'
                }`}>
                    {formatSignedPercent(priceChangePct)}
                </span>
            </div>

            <div className="space-y-2 self-center">
                <div className="flex items-center gap-3">
                    <span className="w-14 text-right text-sm text-slate-400">{formatPlainPrice(item.day_low)}</span>
                    <SimpleRangeTrack item={item} />
                    <span className="w-14 text-sm text-slate-400">{formatPlainPrice(item.day_high)}</span>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
                    <span className="inline-flex items-center gap-1">
                        <span className="h-2.5 w-0.5 rounded-full bg-slate-700" />
                        现价 {formatPlainPrice(item.live_price)}
                    </span>
                    <span className="inline-flex items-center gap-1">
                        <span className={`h-2.5 w-0.5 rounded-full ${costToneClass}`} />
                        成本 {formatPlainPrice(item.average_cost)}
                    </span>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2 text-[11px] text-slate-500">
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                        <span>模型低位 {formatPlainPrice(item.analysis?.low_price)}</span>
                        <span>模型高位 {formatPlainPrice(item.analysis?.high_price)}</span>
                    </div>
                    {rangeAlert && (
                        <div className={`mt-1 font-medium ${rangeAlert.tone === 'danger' ? 'text-rose-600' : 'text-amber-600'}`}>
                            {rangeAlert.message}
                        </div>
                    )}
                </div>
            </div>

            <div className="self-center">
                <span className={`inline-flex min-w-[96px] items-center justify-center rounded-full px-3 py-2 text-[16px] font-semibold ${
                    holdingChangePct == null
                        ? 'bg-slate-100 text-slate-400'
                        : holdingChangePct >= 0
                            ? 'bg-rose-50 text-rose-600'
                            : 'bg-emerald-50 text-emerald-600'
                }`}>
                    {formatSignedPercent(holdingChangePct)}
                </span>
            </div>

            <div className="self-center space-y-1 text-[15px] text-slate-700">
                <div>{formatVolume(item.volume)}</div>
                <div className="text-[14px] text-slate-500">{formatAmount(item.amount)}</div>
            </div>
        </div>
    )
}

function SimpleDayCandle({ item }: { item: TrackingBoardItem }) {
    const open = item.day_open ?? item.previous_close ?? null
    const close = item.live_price ?? null
    const high = item.day_high ?? null
    const low = item.day_low ?? null

    if (open == null || close == null || high == null || low == null) {
        return (
            <div className="flex h-[56px] items-center text-sm text-slate-400">
                暂无数据
            </div>
        )
    }

    const maxPrice = Math.max(high, low, open, close)
    const minPrice = Math.min(high, low, open, close)
    const range = maxPrice - minPrice || Math.max(maxPrice * 0.01, 0.01)
    const chartTop = 4
    const chartBottom = 44
    const chartHeight = chartBottom - chartTop
    const toY = (value: number) => chartTop + ((maxPrice - value) / range) * chartHeight

    const wickTop = toY(high)
    const wickBottom = toY(low)
    const openY = toY(open)
    const closeY = toY(close)
    const bodyTop = Math.min(openY, closeY)
    const bodyHeight = Math.max(Math.abs(closeY - openY), 2)
    const isUp = close >= open
    const candleColor = isUp ? '#e11d48' : '#059669'

    const previousClose = item.previous_close
    const previousCloseY = previousClose == null
        ? null
        : previousClose > maxPrice || previousClose < minPrice
            ? null
            : toY(previousClose)

    return (
        <div className="flex items-center gap-3">
            <svg width="44" height="48" viewBox="0 0 44 48" className="shrink-0 overflow-visible">
                <rect x="0.5" y="0.5" width="43" height="47" rx="11.5" fill="#f8fafc" stroke="#e2e8f0" />
                {previousCloseY != null && (
                    <line
                        x1="8"
                        y1={previousCloseY}
                        x2="36"
                        y2={previousCloseY}
                        stroke="#cbd5e1"
                        strokeDasharray="2 2"
                        strokeWidth="1"
                    />
                )}
                <line x1="22" y1={wickTop} x2="22" y2={wickBottom} stroke={candleColor} strokeWidth="2" strokeLinecap="round" />
                <rect
                    x="15"
                    y={bodyTop}
                    width="14"
                    height={bodyHeight}
                    rx="3"
                    fill={isUp ? '#ffe4e6' : '#dcfce7'}
                    stroke={candleColor}
                    strokeWidth="1.5"
                />
            </svg>
            <div className="space-y-1 text-[11px] text-slate-500">
                <div>开 {formatPlainPrice(open)}</div>
                <div className={isUp ? 'text-rose-600' : 'text-emerald-600'}>现 {formatPlainPrice(close)}</div>
            </div>
        </div>
    )
}

function DetailedBoardView({
    items,
    trackingBoard,
    trackingRefreshing,
    trackingError,
    liveMarketValueTotal,
    floatingPnlTotal,
    onAnalyze,
    onOpenReport,
}: {
    items: TrackingBoardItem[]
    trackingBoard: TrackingBoardResponse | null
    trackingRefreshing: boolean
    trackingError: string | null
    liveMarketValueTotal: number
    floatingPnlTotal: number
    onAnalyze: (symbol: string) => void
    onOpenReport: (reportId: string) => void
}) {
    return (
        <div className="space-y-4 pt-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <BoardStatChip
                    label="持仓标的"
                    value={`${items.length} 只`}
                    subValue={trackingBoard?.last_synced_at ? `QMT 同步于 ${formatDateTime(trackingBoard.last_synced_at)}` : '等待首次同步'}
                    tone="blue"
                />
                <BoardStatChip
                    label="动态市值"
                    value={formatMoney(liveMarketValueTotal)}
                    subValue="优先使用 QMT 实盘价估算"
                    tone="emerald"
                />
                <BoardStatChip
                    label="浮动盈亏"
                    value={formatSignedMoney(floatingPnlTotal)}
                    subValue={trackingError ? `最近刷新异常：${trackingError}` : `价格源：${items.filter(item => item.quote_source).length}/${items.length} 已更新`}
                    tone={floatingPnlTotal >= 0 ? 'rose' : 'amber'}
                    loading={trackingRefreshing}
                />
            </div>

            <div className="space-y-3">
                {items.map(item => (
                    <DetailedTrackingRow
                        key={item.symbol}
                        item={item}
                        onAnalyze={() => onAnalyze(item.symbol)}
                        onOpenReport={() => {
                            if (item.analysis?.report_id) {
                                onOpenReport(item.analysis.report_id)
                            }
                        }}
                    />
                ))}
            </div>
        </div>
    )
}

function DetailedTrackingRow({
    item,
    onAnalyze,
    onOpenReport,
}: {
    item: TrackingBoardItem
    onAnalyze: () => void
    onOpenReport: () => void
}) {
    const priceChangePct = item.price_change_pct ?? null
    const floatingPnl = item.floating_pnl ?? null
    const analysis = item.analysis
    const rangeAlert = getModelRangeAlert(item)
    const rangeLabel = analysis?.is_previous_trade_day ? '昨日报告高低位' : `最近报告高低位 · ${analysis?.trade_date || '--'}`
    const decisionText = analysis?.decision?.toUpperCase() ?? ''
    const directionText = analysis?.direction ?? ''

    let decisionToneClass = 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300'
    if (decisionText.includes('BUY') || directionText.includes('增持')) {
        decisionToneClass = 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-300'
    } else if (decisionText.includes('SELL') || directionText.includes('减持')) {
        decisionToneClass = 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300'
    }

    let floatingClass = 'text-slate-900 dark:text-slate-100'
    if (floatingPnl != null) {
        floatingClass = floatingPnl >= 0 ? 'text-rose-600 dark:text-rose-300' : 'text-emerald-600 dark:text-emerald-300'
    }

    return (
        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/40">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center">
                <div className="min-w-0 xl:w-[220px]">
                    <div className="flex items-center gap-2">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300">
                            <TrendingUp className="h-4 w-4" />
                        </div>
                        <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{item.name}</p>
                            <p className="text-xs text-slate-400">{item.symbol}</p>
                        </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500 dark:text-slate-400">
                        <MetricPill label="持仓" value={formatShares(item.current_position)} />
                        <MetricPill label="可用" value={formatShares(item.available_position)} />
                        <MetricPill label="成本" value={formatPrice(item.average_cost)} />
                        <MetricPill label="仓位" value={formatWeight(item.current_position_pct)} />
                    </div>
                </div>

                <div className="grid flex-1 grid-cols-1 gap-3 lg:grid-cols-3">
                    <div className="rounded-2xl border border-slate-200 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-800/60">
                        <div className="flex items-start justify-between">
                            <div>
                                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">实时价格</p>
                                <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
                                    {formatPrice(item.live_price)}
                                </p>
                            </div>
                            <div className={`flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ${
                                priceChangePct == null
                                    ? 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300'
                                    : priceChangePct >= 0
                                        ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-300'
                                        : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300'
                            }`}>
                                {priceChangePct == null ? (
                                    <RefreshCw className="h-3.5 w-3.5" />
                                ) : priceChangePct >= 0 ? (
                                    <ArrowUpRight className="h-3.5 w-3.5" />
                                ) : (
                                    <ArrowDownRight className="h-3.5 w-3.5" />
                                )}
                                {formatSignedPercent(priceChangePct)}
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500 dark:text-slate-400">
                            <MetricPill label="今开" value={formatPrice(item.day_open)} />
                            <MetricPill label="昨收" value={formatPrice(item.previous_close)} />
                            <MetricPill label="日高" value={formatPrice(item.day_high)} />
                            <MetricPill label="日低" value={formatPrice(item.day_low)} />
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-500 dark:text-slate-400">
                            <MetricPill label="成交量" value={formatVolume(item.volume)} />
                            <MetricPill label="更新时间" value={formatDateTime(item.quote_time)} />
                        </div>
                        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                            <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-1">
                                    <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">
                                        涨跌停 / 日内 / 模型区间
                                    </p>
                                    <RangeInfoTooltip variant="detailed" />
                                </div>
                                {rangeAlert && (
                                    <span className={`rounded-full px-2 py-1 text-[10px] font-medium ${
                                        rangeAlert.tone === 'danger'
                                            ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-300'
                                            : 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300'
                                    }`}>
                                        {rangeAlert.message}
                                    </span>
                                )}
                            </div>
                            <div className="mt-3 flex items-center gap-3">
                                <span className="w-16 text-right text-[11px] text-slate-400">
                                    <span className="block">{formatSignedPercent(-getDailyLimitPercent(item))}</span>
                                    <span className="mt-1 block">{formatPlainPrice(item.day_low)}</span>
                                </span>
                                <CombinedRangeTrack item={item} />
                                <span className="w-16 text-[11px] text-slate-400">
                                    <span className="block">{formatSignedPercent(getDailyLimitPercent(item))}</span>
                                    <span className="mt-1 block">{formatPlainPrice(item.day_high)}</span>
                                </span>
                            </div>
                            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500 dark:text-slate-400">
                                <span className="inline-flex items-center gap-1">
                                    <span className="h-2.5 w-1 rounded-full bg-indigo-500" />
                                    当前涨跌 {formatSignedPercent(item.price_change_pct)}
                                </span>
                                <span className="inline-flex items-center gap-1">
                                    <span className="h-2.5 w-0.5 rounded-full bg-sky-500" />
                                    现价 {formatPlainPrice(item.live_price)}
                                </span>
                                <span className="inline-flex items-center gap-1">
                                    <span className="h-2.5 w-0.5 rounded-full bg-amber-400" />
                                    成本 {formatPlainPrice(item.average_cost)}
                                </span>
                                <span className="inline-flex items-center gap-1">
                                    <span className="h-2.5 w-2.5 rounded-full border border-emerald-600 bg-white" />
                                    模型低位 {formatPlainPrice(item.analysis?.low_price)}
                                </span>
                                <span className="inline-flex items-center gap-1">
                                    <span className="h-2.5 w-2.5 rounded-full border border-rose-600 bg-white" />
                                    模型高位 {formatPlainPrice(item.analysis?.high_price)}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-800/60">
                        <div className="flex items-start justify-between">
                            <div>
                                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">持仓表现</p>
                                <p className={`mt-1 text-2xl font-semibold ${floatingClass}`}>
                                    {formatSignedMoney(floatingPnl)}
                                </p>
                            </div>
                            <div className={`rounded-full px-2 py-1 text-xs font-semibold ${
                                floatingPnl == null
                                    ? 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300'
                                    : floatingPnl >= 0
                                        ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-300'
                                        : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300'
                            }`}>
                                {formatSignedPercent(item.floating_pnl_pct)}
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500 dark:text-slate-400">
                            <MetricPill label="动态市值" value={formatMoney(item.live_market_value ?? item.market_value)} />
                            <MetricPill label="静态市值" value={formatMoney(item.market_value)} />
                            <MetricPill label="成交额" value={formatAmount(item.amount)} />
                            <MetricPill label="价格源" value={formatQuoteSource(item.quote_source)} />
                        </div>
                        <div className="mt-2">
                            <MetricPill label="导入时间" value={formatDateTime(item.last_imported_at)} />
                        </div>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-800/60">
                        <div className="flex items-center gap-2">
                            <Target className="h-4 w-4 text-sky-500" />
                            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{rangeLabel}</p>
                        </div>
                        {analysis ? (
                            <>
                                <div className="mt-3 flex items-center gap-2 text-xs">
                                    <span className={`rounded-full px-2 py-1 font-semibold ${decisionToneClass}`}>
                                        {analysis.direction || analysis.decision || '待定'}
                                    </span>
                                    <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-500 dark:bg-slate-700 dark:text-slate-300">
                                        {analysis.trade_date}
                                    </span>
                                </div>

                                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500 dark:text-slate-400">
                                    <MetricPill label="高位" value={formatPrice(analysis.high_price)} />
                                    <MetricPill label="低位" value={formatPrice(analysis.low_price)} />
                                </div>
                            </>
                        ) : (
                            <div className="mt-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-400">
                                还没有找到可绑定到这只股票的分析结果。
                            </div>
                        )}
                    </div>
                </div>

                <div className="xl:w-[290px]">
                    <div className="rounded-2xl border border-slate-200 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-800/60">
                        <div className="flex items-center gap-2">
                            <ShieldAlert className="h-4 w-4 text-amber-500" />
                            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">交易员建议</p>
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-700 dark:text-slate-200" style={CLAMP_TWO_LINES_STYLE}>
                            {analysis?.trader_advice_summary || '暂未提取到建议摘要，可进入报告查看完整内容。'}
                        </p>
                        <div className="mt-4 flex flex-wrap gap-2">
                            {analysis?.report_id && (
                                <button
                                    type="button"
                                    onClick={onOpenReport}
                                    className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 transition-colors hover:border-blue-400 hover:text-blue-600 dark:border-slate-700 dark:text-slate-200 dark:hover:border-blue-500 dark:hover:text-blue-400"
                                >
                                    查看报告
                                </button>
                            )}
                            <button
                                type="button"
                                onClick={onAnalyze}
                                className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
                            >
                                重新分析
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

function RangeInfoTooltip({ variant }: { variant: 'simple' | 'detailed' }) {
    const text = variant === 'simple'
        ? '短条表示当日最低价到最高价，蓝线是现价，黄线是成本价；下方补充模型低位、高位和破位预警。'
        : '外层细条表示跌停到涨停，内层短条表示当日最低价到最高价；图中同时标出当前涨跌、现价、成本价和模型区间。'

    return (
        <div className="group relative">
            <button
                type="button"
                aria-label="当日区间说明"
                className="flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 bg-white text-[10px] font-semibold tracking-normal text-slate-500 transition-colors hover:border-sky-300 hover:text-sky-600 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-400 dark:hover:border-sky-500/40 dark:hover:text-sky-300"
            >
                i
            </button>
            <div className="pointer-events-none absolute left-1/2 top-5 z-20 w-64 -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-3 text-left text-[11px] normal-case tracking-normal text-slate-600 opacity-0 shadow-xl transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
                {text}
            </div>
        </div>
    )
}

function SimpleRangeTrack({ item }: { item: TrackingBoardItem }) {
    const low = item.day_low
    const high = item.day_high
    const live = item.live_price
    const cost = item.average_cost
    const liveProgress = getRangeMarkerProgress(low, high, live)
    const costProgress = getRangeMarkerProgress(low, high, cost)
    const costAboveLive = cost != null && live != null && Number.isFinite(cost) && Number.isFinite(live) && cost > live
    const costToneClass = costAboveLive ? 'bg-emerald-500' : 'bg-rose-500'

    return (
        <div className="relative h-6 flex-1">
            <div className="absolute inset-y-0 left-0 right-0 my-auto h-1 rounded-full bg-slate-300" />
            {costProgress != null && (
                <div
                    className={`absolute top-1/2 h-4 w-1 -translate-y-1/2 rounded-full shadow-sm ${costToneClass}`}
                    style={{ left: `calc(${costProgress}% - 2px)` }}
                />
            )}
            {liveProgress != null && (
                <div
                    className="absolute top-1/2 h-4 w-1.5 -translate-y-1/2 rounded-full bg-slate-700 shadow-sm"
                    style={{ left: `calc(${liveProgress}% - 3px)` }}
                />
            )}
        </div>
    )
}

function CombinedRangeTrack({ item }: { item: TrackingBoardItem }) {
    const limitPct = getDailyLimitPercent(item)
    const lowPct = -limitPct
    const highPct = limitPct
    const currentPct = item.price_change_pct
    const currentProgress = getRangeMarkerProgress(lowPct, highPct, currentPct)
    const low = item.day_low
    const high = item.day_high
    const live = item.live_price
    const cost = item.average_cost
    const analysisLow = item.analysis?.low_price
    const analysisHigh = item.analysis?.high_price
    const liveProgress = getRangeMarkerProgress(low, high, live)
    const costProgress = getRangeMarkerProgress(low, high, cost)
    const analysisLowProgress = getRangeMarkerProgress(low, high, analysisLow)
    const analysisHighProgress = getRangeMarkerProgress(low, high, analysisHigh)

    return (
        <div className="relative h-7 flex-1">
            <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-gradient-to-r from-emerald-100 via-slate-200 to-rose-100" />
            <div className="absolute inset-y-0 left-0 w-px bg-slate-300" />
            <div className="absolute inset-y-0 right-0 w-px bg-slate-300" />
            {currentProgress != null && (
                <div
                    className="absolute top-1/2 h-5 w-1.5 -translate-y-1/2 rounded-full bg-indigo-500 shadow-sm"
                    style={{ left: `calc(${currentProgress}% - 3px)` }}
                />
            )}
            <div className="absolute left-[16%] right-[16%] top-1/2 h-2 -translate-y-1/2 rounded-full bg-slate-300" />
            {analysisLowProgress != null && (
                <div
                    className="absolute top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full border border-emerald-600 bg-white shadow-sm"
                    style={{ left: `calc(16% + ${analysisLowProgress * 0.68}% - 5px)` }}
                />
            )}
            {analysisHighProgress != null && (
                <div
                    className="absolute top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full border border-rose-600 bg-white shadow-sm"
                    style={{ left: `calc(16% + ${analysisHighProgress * 0.68}% - 5px)` }}
                />
            )}
            {costProgress != null && (
                <div
                    className="absolute top-1/2 h-4 w-1 -translate-y-1/2 rounded-full bg-amber-400 shadow-sm"
                    style={{ left: `calc(16% + ${costProgress * 0.68}% - 2px)` }}
                />
            )}
            {liveProgress != null && (
                <div
                    className="absolute top-1/2 h-4 w-1.5 -translate-y-1/2 rounded-full bg-sky-500 shadow-sm"
                    style={{ left: `calc(16% + ${liveProgress * 0.68}% - 3px)` }}
                />
            )}
        </div>
    )
}

function BoardStatChip({
    label,
    value,
    subValue,
    tone,
    loading = false,
}: {
    label: string
    value: string
    subValue: string
    tone: BoardTone
    loading?: boolean
}) {
    const toneClasses: Record<BoardTone, string> = {
        blue: 'from-blue-500/12 to-sky-500/10 border-blue-200/70 dark:border-blue-500/20',
        emerald: 'from-emerald-500/12 to-teal-500/10 border-emerald-200/70 dark:border-emerald-500/20',
        rose: 'from-rose-500/12 to-orange-500/10 border-rose-200/70 dark:border-rose-500/20',
        amber: 'from-amber-500/12 to-orange-500/10 border-amber-200/70 dark:border-amber-500/20',
    }

    return (
        <div className={`rounded-2xl border bg-gradient-to-br px-4 py-3 ${toneClasses[tone]}`}>
            <div className="flex items-center justify-between">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{label}</p>
                {loading && <RefreshCw className="h-3.5 w-3.5 animate-spin text-slate-400" />}
            </div>
            <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{subValue}</p>
        </div>
    )
}

function MetricPill({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-xl bg-slate-100/90 px-2.5 py-2 dark:bg-slate-700/60">
            <p className="text-[11px] text-slate-400">{label}</p>
            <p className="mt-1 truncate font-medium text-slate-700 dark:text-slate-100">{value}</p>
        </div>
    )
}

function getRangeMarkerProgress(
    low?: number | null,
    high?: number | null,
    value?: number | null,
): number | null {
    if (low == null || high == null || value == null) return null
    if (!Number.isFinite(low) || !Number.isFinite(high) || !Number.isFinite(value)) return null

    const min = Math.min(low, high)
    const max = Math.max(low, high)
    if (max === min) return 50

    const raw = ((value - min) / (max - min)) * 100
    return Math.max(0, Math.min(100, raw))
}

function getDailyLimitPercent(item: TrackingBoardItem): number {
    const symbol = String(item.symbol || '').toUpperCase()
    const name = String(item.name || '').toUpperCase()

    if (name.includes('ST')) return 5
    if (symbol.endsWith('.BJ')) return 30
    if (symbol.startsWith('300') || symbol.startsWith('688')) return 20
    return 10
}

function getModelRangeAlert(
    item: TrackingBoardItem,
): { tone: 'danger' | 'warning'; message: string } | null {
    const livePrice = item.live_price
    const lowPrice = item.analysis?.low_price
    const highPrice = item.analysis?.high_price

    if (livePrice == null || !Number.isFinite(livePrice)) return null
    if (lowPrice != null && Number.isFinite(lowPrice) && livePrice < lowPrice) {
        return { tone: 'danger', message: '预警：已跌破模型低位' }
    }
    if (highPrice != null && Number.isFinite(highPrice) && livePrice > highPrice) {
        return { tone: 'warning', message: '预警：已突破模型高位' }
    }
    return null
}

function formatPrice(value?: number | null): string {
    if (value == null || !Number.isFinite(value)) return '--'
    return formatNumber(value, 2)
}

function formatPlainPrice(value?: number | null): string {
    return formatPrice(value)
}

function formatMoney(value?: number | null): string {
    if (value == null || !Number.isFinite(value)) return '--'
    return formatWithChineseUnit(value, 2)
}

function formatSignedMoney(value?: number | null): string {
    if (value == null || !Number.isFinite(value)) return '--'
    const sign = value >= 0 ? '+' : '-'
    return `${sign}${formatMoney(Math.abs(value))}`
}

function formatSignedPercent(value?: number | null): string {
    if (value == null || !Number.isFinite(value)) return '--'
    return `${value >= 0 ? '+' : ''}${formatNumber(value, 2)}%`
}

function formatShares(value?: number | null): string {
    if (value == null || !Number.isFinite(value)) return '--'
    if (Math.abs(value) >= 1e4) {
        return `${formatWithChineseUnit(value, 0)}股`
    }
    return `${formatNumber(value, 0)}股`
}

function formatWeight(value?: number | null): string {
    if (value == null || !Number.isFinite(value)) return '--'
    return `${formatNumber(value, 2)}%`
}

function formatVolume(value?: number | null): string {
    if (value == null || !Number.isFinite(value)) return '--'
    return formatWithChineseUnit(value, 0)
}

function formatAmount(value?: number | null): string {
    if (value == null || !Number.isFinite(value)) return '--'
    return formatWithChineseUnit(value, 2)
}

function formatDateTime(value?: string | null): string {
    const parsed = parseLooseDate(value)
    if (!parsed) return value || '--'

    const year = parsed.getFullYear()
    const month = String(parsed.getMonth() + 1).padStart(2, '0')
    const day = String(parsed.getDate()).padStart(2, '0')
    const hours = String(parsed.getHours()).padStart(2, '0')
    const minutes = String(parsed.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day} ${hours}:${minutes}`
}

function formatFooterTime(value?: string | null): string {
    const parsed = parseLooseDate(value)
    if (!parsed) return value || '--'

    const month = String(parsed.getMonth() + 1).padStart(2, '0')
    const day = String(parsed.getDate()).padStart(2, '0')
    const hours = String(parsed.getHours()).padStart(2, '0')
    const minutes = String(parsed.getMinutes()).padStart(2, '0')
    const seconds = String(parsed.getSeconds()).padStart(2, '0')
    return `${month}-${day} ${hours}:${minutes}:${seconds}`
}

function formatQuoteSource(value?: string | null): string {
    if (!value) return '--'
    return value.replace('qmt_', '').replace('xtdata', 'xtquant')
}

function formatNumber(value: number, digits = 2): string {
    return new Intl.NumberFormat('zh-CN', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    }).format(value)
}

function formatWithChineseUnit(value: number, baseDigits = 2): string {
    const abs = Math.abs(value)
    if (abs >= 1e8) {
        return `${formatNumber(value / 1e8, 2)}亿`
    }
    if (abs >= 1e4) {
        return `${formatNumber(value / 1e4, baseDigits === 0 ? 0 : 2)}万`
    }
    return formatNumber(value, baseDigits)
}

function parseLooseDate(value?: string | null): Date | null {
    if (!value) return null
    const trimmed = value.trim()
    if (!trimmed) return null

    let match = /^(\d{4})(\d{2})(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(trimmed)
    if (match) {
        return new Date(
            Number(match[1]),
            Number(match[2]) - 1,
            Number(match[3]),
            Number(match[4]),
            Number(match[5]),
            Number(match[6] || 0),
        )
    }

    match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/.exec(trimmed)
    if (match) {
        return new Date(
            Number(match[1]),
            Number(match[2]) - 1,
            Number(match[3]),
            Number(match[4]),
            Number(match[5]),
            Number(match[6] || 0),
        )
    }

    const parsed = new Date(trimmed)
    return Number.isNaN(parsed.getTime()) ? null : parsed
}
