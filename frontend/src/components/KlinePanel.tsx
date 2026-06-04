import { useEffect, useMemo, useRef, useState } from 'react'
import {
    BusinessDay,
    CandlestickData,
    CandlestickSeries,
    ColorType,
    IChartApi,
    ISeriesApi,
    LineData,
    LineSeries,
    LineStyle,
    MouseEventParams,
    Time,
    createChart,
} from 'lightweight-charts'
import { Activity, CandlestickChart, TrendingUp } from 'lucide-react'
import { api } from '@/services/api'
import type { KlineCandle, NiuxiongPoint } from '@/types'
import { useAnalysisStore } from '@/stores/analysisStore'

interface KlinePanelProps {
    symbol: string
    onSymbolChange?: (symbol: string) => void
}

function toDateText(date: Date): string {
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    return `${y}-${m}-${d}`
}

function toBusinessDay(value: string): BusinessDay | null {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
    if (!m) return null
    const year = Number(m[1])
    const month = Number(m[2])
    const day = Number(m[3])
    if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null
    return { year, month, day }
}

const SYMBOL_NAME_MAP: Record<string, string> = {
    '000001.SH': '上证指数',
    '399001.SZ': '深证成指',
    '399006.SZ': '创业板指',
    '000300.SH': '沪深300',
    '000905.SH': '中证500',
    '000852.SH': '中证1000',
    '300750.SZ': '宁德时代',
    '600406.SH': '国电南瑞',
    '510300.SH': '沪深300ETF',
}

function getDisplayName(symbol: string): string {
    const s = symbol.toUpperCase()
    return SYMBOL_NAME_MAP[s] ? `${SYMBOL_NAME_MAP[s]}（${s}）` : s
}

function formatNumber(value?: number | null, digits = 2): string {
    if (value == null || !Number.isFinite(value)) return '--'
    return new Intl.NumberFormat('zh-CN', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    }).format(value)
}

function formatVolume(value?: number | null): string {
    if (value == null || !Number.isFinite(value)) return '--'
    if (Math.abs(value) >= 1e8) return `${formatNumber(value / 1e8, 2)}亿`
    if (Math.abs(value) >= 1e4) return `${formatNumber(value / 1e4, 2)}万`
    return formatNumber(value, 0)
}

const INDEX_PRESETS = [
    { symbol: '000001.SH', label: '上证指数' },
    { symbol: '399001.SZ', label: '深证成指' },
    { symbol: '399006.SZ', label: '创业板指' },
    { symbol: '000688.SH', label: '科创50' },
    { symbol: '899050.BJ', label: '北证50' },
] as const

export default function KlinePanel({ symbol, onSymbolChange }: KlinePanelProps) {
    const currentAnalysisSymbol = useAnalysisStore((state) => state.currentSymbol)
    const containerRef = useRef<HTMLDivElement | null>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
    const niuxiongSeriesRefs = useRef<Record<string, ISeriesApi<'Line'>>>({})
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [isDark, setIsDark] = useState(document.documentElement.classList.contains('dark'))
    const [candles, setCandles] = useState<KlineCandle[]>([])
    const [activeCandle, setActiveCandle] = useState<KlineCandle | null>(null)
    const [showNiuxiong, setShowNiuxiong] = useState(true)
    const showNiuxiongRef = useRef(true)
    const [niuxiongData, setNiuxiongData] = useState<NiuxiongPoint[]>([])
    const candlesRef = useRef<KlineCandle[]>([])

    const range = useMemo(() => {
        const end = new Date()
        const start = new Date(end.getTime() - 180 * 24 * 60 * 60 * 1000)
        return {
            start: toDateText(start),
            end: toDateText(end),
        }
    }, [])

    const updateNiuxiongSeries = (points: NiuxiongPoint[]) => {
        const seriesMap = niuxiongSeriesRefs.current
        if (!seriesMap.decision_line || !showNiuxiongRef.current) return

        const keys = ['decision_line', 'bear_line', 'orbit_line'] as const
        for (const key of keys) {
            const lineData: LineData[] = []
            for (const p of points) {
                const val = p[key]
                if (val == null) continue
                const time = toBusinessDay(p.date)
                if (!time) continue
                lineData.push({ time: time as Time, value: val })
            }
            seriesMap[key]?.setData(lineData)
        }
        chartRef.current?.timeScale().fitContent()
    }

    // Listen for theme changes
    useEffect(() => {
        const observer = new MutationObserver(() => {
            const dark = document.documentElement.classList.contains('dark')
            setIsDark(dark)
        })
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
        return () => observer.disconnect()
    }, [])

    useEffect(() => {
        if (!containerRef.current) return

        const textColor = isDark ? '#94a3b8' : '#475569'
        const gridColor = isDark ? 'rgba(51, 65, 85, 0.6)' : 'rgba(203, 213, 225, 0.6)'
        const bgColor = isDark ? 'transparent' : 'transparent'

        const chart = createChart(containerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: bgColor },
                textColor: textColor,
                attributionLogo: false,
            },
            localization: {
                locale: 'zh-CN',
                dateFormat: 'yyyy-MM-dd',
            },
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
            grid: {
                vertLines: { color: gridColor },
                horzLines: { color: gridColor },
            },
            rightPriceScale: {
                borderColor: isDark ? '#334155' : '#cbd5e1',
            },
            timeScale: {
                borderColor: isDark ? '#334155' : '#cbd5e1',
                timeVisible: true,
                rightOffset: 6,
                tickMarkFormatter: (time: BusinessDay | string) => {
                    if (typeof time !== 'object') return String(time)
                    const y = String(time.year)
                    const m = String(time.month).padStart(2, '0')
                    const d = String(time.day).padStart(2, '0')
                    return `${y}/${m}/${d}`
                },
            },
            crosshair: {
                vertLine: { color: isDark ? 'rgba(59, 130, 246, 0.35)' : 'rgba(59, 130, 246, 0.25)' },
                horzLine: { color: isDark ? 'rgba(59, 130, 246, 0.35)' : 'rgba(59, 130, 246, 0.25)' },
            },
        })

        const series = chart.addSeries(CandlestickSeries, {
            upColor: '#ef4444',
            downColor: '#22c55e',
            wickUpColor: '#ef4444',
            wickDownColor: '#22c55e',
            borderVisible: false,
        })

        // Niuxiong indicator line series
        const niuxiongColors: Record<string, { color: string; lineWidth: 1 | 2; lineStyle: LineStyle; title: string }> = {
            decision_line: { color: '#eab308', lineWidth: 1, lineStyle: LineStyle.Dashed, title: '决策线' },
            bear_line: { color: '#22c55e', lineWidth: 1, lineStyle: LineStyle.Dashed, title: '熊线' },
            orbit_line: { color: '#06b6d4', lineWidth: 2, lineStyle: LineStyle.Solid, title: '轨道线' },
        }
        const seriesMap: Record<string, ISeriesApi<'Line'>> = {}
        for (const [key, cfg] of Object.entries(niuxiongColors)) {
            const s = chart.addSeries(LineSeries, {
                color: cfg.color,
                lineWidth: cfg.lineWidth,
                lineStyle: cfg.lineStyle,
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
            })
            seriesMap[key] = s
        }
        niuxiongSeriesRefs.current = seriesMap

        chartRef.current = chart
        seriesRef.current = series

        if (candlesRef.current.length) {
            const existingData: CandlestickData[] = candlesRef.current.flatMap((c) => {
                const time = toBusinessDay((c.date || '').slice(0, 10))
                const open = Number(c.open)
                const high = Number(c.high)
                const low = Number(c.low)
                const close = Number(c.close)
                if (!time) return []
                if (![open, high, low, close].every(Number.isFinite)) return []
                return [{ time, open, high, low, close }]
            })
            series.setData(existingData)
            chart.timeScale().fitContent()
        }

        const handleCrosshairMove = (param: MouseEventParams) => {
            if (!param.time || !seriesRef.current) {
                setActiveCandle(candlesRef.current.length ? candlesRef.current[candlesRef.current.length - 1] : null)
                return
            }
            const pointData = param.seriesData.get(seriesRef.current) as CandlestickData | undefined
            if (!pointData) return
            const time = typeof pointData.time === 'object'
                ? `${pointData.time.year}-${String(pointData.time.month).padStart(2, '0')}-${String(pointData.time.day).padStart(2, '0')}`
                : String(pointData.time)
            const matched = candlesRef.current.find(c => c.date === time)
            if (matched) setActiveCandle(matched)
        }
        chart.subscribeCrosshairMove(handleCrosshairMove)

        const handleDblClick = () => {
            chartRef.current?.timeScale().fitContent()
        }
        containerRef.current.addEventListener('dblclick', handleDblClick)

        const onResize = () => {
            if (!containerRef.current || !chartRef.current) return
            chartRef.current.applyOptions({
                width: containerRef.current.clientWidth,
                height: containerRef.current.clientHeight,
            })
        }

        window.addEventListener('resize', onResize)
        return () => {
            window.removeEventListener('resize', onResize)
            containerRef.current?.removeEventListener('dblclick', handleDblClick)
            chart.unsubscribeCrosshairMove(handleCrosshairMove)
            chartRef.current?.remove()
            chartRef.current = null
            seriesRef.current = null
        }
    }, [isDark])

    useEffect(() => {
        let cancelled = false

        const load = async () => {
            if (!seriesRef.current) return
            setLoading(true)
            setError(null)
            try {
                const [klineResp, niuxiongResp] = await Promise.all([
                    api.getKline(symbol, range.start, range.end),
                    api.getNiuxiong(symbol, range.start, range.end).catch(() => null),
                ])
                const data: CandlestickData[] = klineResp.candles.flatMap((c) => {
                    const time = toBusinessDay((c.date || '').slice(0, 10))
                    const open = Number(c.open)
                    const high = Number(c.high)
                    const low = Number(c.low)
                    const close = Number(c.close)
                    if (!time) return []
                    if (![open, high, low, close].every(Number.isFinite)) return []
                    return [{ time, open, high, low, close }]
                })

                if (cancelled) return
                setCandles(klineResp.candles)
                candlesRef.current = klineResp.candles
                setActiveCandle(klineResp.candles.length ? klineResp.candles[klineResp.candles.length - 1] : null)
                seriesRef.current?.setData(data)

                // Update niuxiong overlay
                if (niuxiongResp?.points) {
                    setNiuxiongData(niuxiongResp.points)
                    updateNiuxiongSeries(niuxiongResp.points)
                }

                chartRef.current?.timeScale().fitContent()
                if (!data.length) {
                    setError('暂无可用K线数据')
                }
            } catch (e) {
                if (cancelled) return
                setError(e instanceof Error ? e.message : '加载K线失败')
                setCandles([])
                candlesRef.current = []
                setActiveCandle(null)
                seriesRef.current?.setData([])
            } finally {
                if (!cancelled) setLoading(false)
            }
        }

        load()
        return () => {
            cancelled = true
        }
    }, [range.end, range.start, symbol])

    const panelCandle = activeCandle ?? (candles.length ? candles[candles.length - 1] : null)
    const panelChange = panelCandle?.change ?? (panelCandle ? panelCandle.close - panelCandle.open : null)
    const panelChangePercent = panelCandle?.change_percent ?? (
        panelCandle && panelCandle.open !== 0 ? (panelChange! / panelCandle.open) * 100 : null
    )
    const isUp = (panelChange ?? 0) >= 0
    const compactChangePercent = panelChangePercent == null ? '--' : `${panelChangePercent >= 0 ? '+' : ''}${formatNumber(panelChangePercent)}%`
    const showCurrentSymbolButton = !!currentAnalysisSymbol && currentAnalysisSymbol !== symbol
    const currentSymbolLabel = currentAnalysisSymbol ? getDisplayName(currentAnalysisSymbol).replace(/（.*?）/, '') : '当前标的'

    return (
        <section className="card h-full flex flex-col overflow-hidden">
            <div className="flex items-center justify-between mb-3 shrink-0">
                <div className="min-w-0 flex items-center gap-3">
                    <CandlestickChart className="w-5 h-5 text-cyan-500" />
                    <div className="min-w-0 flex flex-wrap items-center gap-x-4 gap-y-1">
                        <h2 className="truncate text-lg font-semibold text-slate-900 dark:text-slate-100">{getDisplayName(symbol)} K线</h2>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                            <span className="text-slate-500 dark:text-slate-400">{panelCandle?.date || '--'}</span>
                            <span className={`font-medium ${isUp ? 'text-red-500' : 'text-emerald-500'}`}>收盘 {formatNumber(panelCandle?.close)}</span>
                            <span className="text-slate-500 dark:text-slate-400">开盘 {formatNumber(panelCandle?.open)}</span>
                            <span className={`font-medium ${isUp ? 'text-red-500' : 'text-emerald-500'}`}>{compactChangePercent}</span>
                            <span className="text-slate-500 dark:text-slate-400">高/低 {formatNumber(panelCandle?.high)} / {formatNumber(panelCandle?.low)}</span>
                            <span className="text-slate-500 dark:text-slate-400">量 {formatVolume(panelCandle?.volume)}</span>
                            <span className="text-slate-500 dark:text-slate-400">换手 {panelCandle?.turnover_rate == null ? '--' : `${formatNumber(panelCandle.turnover_rate)}%`}</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-1.5">
                    {showCurrentSymbolButton && (
                        <button
                            onClick={() => onSymbolChange?.(currentAnalysisSymbol)}
                            className="text-xs px-2.5 py-1 rounded border border-emerald-500 text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 transition-colors"
                        >
                            {currentSymbolLabel}
                        </button>
                    )}
                    {INDEX_PRESETS.map((item) => (
                        <button
                            key={item.symbol}
                            onClick={() => onSymbolChange?.(item.symbol)}
                            className={`text-xs px-2 py-1 rounded border transition-colors ${item.symbol === symbol
                                    ? 'border-blue-500 text-blue-500 bg-blue-50 dark:bg-blue-500/10'
                                    : 'border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:border-slate-400 dark:hover:border-slate-500'
                                }`}
                        >
                            {item.label}
                        </button>
                    ))}
                    <button
                        onClick={() => {
                            const next = !showNiuxiongRef.current
                            showNiuxiongRef.current = next
                            setShowNiuxiong(next)
                            if (next) {
                                updateNiuxiongSeries(niuxiongData)
                            } else {
                                for (const s of Object.values(niuxiongSeriesRefs.current)) {
                                    s.setData([])
                                }
                            }
                        }}
                        className={`text-xs px-2 py-1 rounded border transition-colors flex items-center gap-1 ${showNiuxiong
                                ? 'border-cyan-500 text-cyan-500 bg-cyan-50 dark:bg-cyan-500/10'
                                : 'border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:border-slate-400 dark:hover:border-slate-500'
                            }`}
                    >
                        <TrendingUp className="w-3 h-3" />
                        牛熊线
                    </button>
                </div>
            </div>
            <div className="relative flex-1 min-h-0 rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 overflow-hidden">
                <div ref={containerRef} className="absolute inset-0" />
                {showNiuxiong && niuxiongData.length > 0 && (() => {
                    const last = niuxiongData[niuxiongData.length - 1]
                    return (
                        <div className="absolute left-3 top-3 text-xs px-2 py-1.5 rounded bg-white/80 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 flex flex-col gap-0.5">
                            <div className="flex items-center gap-4">
                                <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-yellow-400" style={{ borderTop: '1px dashed #eab308' }} />决策线 <span className="text-yellow-500 font-medium">{last.decision_line ?? '--'}</span></span>
                                <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-green-500" style={{ borderTop: '1px dashed #22c55e' }} />熊线 <span className="text-green-500 font-medium">{last.bear_line ?? '--'}</span></span>
                                <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-cyan-500" />轨道线 <span className="text-cyan-500 font-medium">{last.orbit_line ?? '--'}</span></span>
                            </div>
                        </div>
                    )
                })()}
                {loading && (
                    <div className="absolute right-3 top-3 text-xs px-2 py-1 rounded bg-white/90 dark:bg-slate-800/90 text-slate-600 dark:text-slate-400 flex items-center gap-1">
                        <Activity className="w-3 h-3 animate-pulse" />
                        加载中
                    </div>
                )}
                {error && (
                    <div className="absolute left-3 top-3 text-xs px-2 py-1 rounded bg-white/90 dark:bg-slate-800/90 text-orange-500">
                        {error}
                    </div>
                )}
            </div>
        </section>
    )
}
