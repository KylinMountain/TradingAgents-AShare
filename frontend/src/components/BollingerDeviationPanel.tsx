import { useEffect, useMemo, useRef, useState } from 'react'
import {
    BusinessDay,
    ColorType,
    HistogramData,
    HistogramSeries,
    IChartApi,
    ISeriesApi,
    LineData,
    LineSeries,
    MouseEventParams,
    Time,
    UTCTimestamp,
    createChart,
} from 'lightweight-charts'
import { api } from '@/services/api'
import type { BollingerDeviationPoint, KlinePeriod } from '@/types'
import { useAnalysisStore } from '@/stores/analysisStore'

interface BollingerDeviationPanelProps {
    symbol: string
    onChartReady?: (chart: IChartApi) => void
    onSyncNow?: () => void
}

function toChartTime(value: string, period: KlinePeriod): Time | null {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
    if (!m) return null
    const year = Number(m[1])
    const month = Number(m[2])
    const day = Number(m[3])
    if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null
    if (period === 'daily') {
        return { year, month, day } as BusinessDay
    }
    return (Date.UTC(year, month - 1, day) / 1000) as UTCTimestamp
}

function getMccdColor(p: BollingerDeviationPoint): string {
    if (p.is_cross_lp) return '#FF55FF'
    if (p.is_warning) return '#00AA00'
    if (p.llb != null && p.mccd < p.llb) return '#FF6677'
    if (p.lb != null && p.mccd < p.lb) return '#444444'
    return '#3b82f6'
}

function getSignalLabel(p: BollingerDeviationPoint): string {
    if (p.is_cross_lp) return '乖离反转'
    if (p.is_warning) return '顶部警示'
    if (p.llb != null && p.mccd < p.llb) return '极端超卖'
    if (p.lb != null && p.mccd < p.lb) return '超卖'
    return '正常'
}

const BAND_COLORS = {
    ub: '#00AA00',
    lb: '#00AA00',
    uub: '#FF9900',
    llb: '#FF9900',
}

export default function BollingerDeviationPanel({ symbol, onChartReady, onSyncNow }: BollingerDeviationPanelProps) {
    const klinePeriod = useAnalysisStore((state) => state.klinePeriod)
    const containerRef = useRef<HTMLDivElement | null>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const mccdSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
    const ubSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
    const lbSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
    const uubSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
    const llbSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
    const cacheRef = useRef<BollingerDeviationPoint[]>([])
    const cachePeriodRef = useRef<KlinePeriod>('daily')
    const [data, setData] = useState<BollingerDeviationPoint[]>([])
    const [hoverPoint, setHoverPoint] = useState<BollingerDeviationPoint | null>(null)
    const [isDark, setIsDark] = useState(document.documentElement.classList.contains('dark'))

    const range = useMemo(() => {
        const end = new Date()
        const rangeDays = klinePeriod === 'daily' ? 365 : klinePeriod === 'weekly' ? 730 : 1825
        const start = new Date(end.getTime() - rangeDays * 24 * 60 * 60 * 1000)
        const toText = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
        return { start: toText(start), end: toText(end) }
    }, [klinePeriod])

    useEffect(() => {
        const observer = new MutationObserver(() => {
            setIsDark(document.documentElement.classList.contains('dark'))
        })
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
        return () => observer.disconnect()
    }, [])

    useEffect(() => {
        if (!containerRef.current) return

        const textColor = isDark ? '#94a3b8' : '#475569'
        const gridColor = isDark ? 'rgba(51, 65, 85, 0.6)' : 'rgba(203, 213, 225, 0.6)'

        const chart = createChart(containerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor,
                attributionLogo: false,
            },
            localization: { locale: 'zh-CN', dateFormat: 'yyyy-MM-dd' },
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
            grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
            rightPriceScale: {
                borderColor: isDark ? '#334155' : '#cbd5e1',
                scaleMargins: { top: 0.05, bottom: 0.05 },
            },
            timeScale: {
                borderColor: isDark ? '#334155' : '#cbd5e1',
                timeVisible: true,
                rightOffset: 6,
                tickMarkFormatter: (time: Time) => {
                    if (typeof time === 'number') {
                        const d = new Date(time * 1000)
                        return `${d.getUTCFullYear()}/${String(d.getUTCMonth() + 1).padStart(2, '0')}/${String(d.getUTCDate()).padStart(2, '0')}`
                    }
                    if (typeof time === 'object') {
                        return `${time.year}/${String(time.month).padStart(2, '0')}/${String(time.day).padStart(2, '0')}`
                    }
                    return String(time)
                },
            },
            crosshair: {
                vertLine: { color: isDark ? 'rgba(59, 130, 246, 0.35)' : 'rgba(59, 130, 246, 0.25)' },
                horzLine: { color: isDark ? 'rgba(59, 130, 246, 0.35)' : 'rgba(59, 130, 246, 0.25)' },
            },
        })

        const mccdSeries = chart.addSeries(HistogramSeries, {
            priceLineVisible: false,
            lastValueVisible: true,
        })

        const ubSeries = chart.addSeries(LineSeries, {
            color: BAND_COLORS.ub,
            lineWidth: 1,
            lineStyle: 2, // dotted
            priceLineVisible: false,
            lastValueVisible: false,
        })

        const lbSeries = chart.addSeries(LineSeries, {
            color: BAND_COLORS.lb,
            lineWidth: 1,
            lineStyle: 2,
            priceLineVisible: false,
            lastValueVisible: false,
        })

        const uubSeries = chart.addSeries(LineSeries, {
            color: BAND_COLORS.uub,
            lineWidth: 1,
            lineStyle: 2,
            priceLineVisible: false,
            lastValueVisible: false,
        })

        const llbSeries = chart.addSeries(LineSeries, {
            color: BAND_COLORS.llb,
            lineWidth: 1,
            lineStyle: 2,
            priceLineVisible: false,
            lastValueVisible: false,
        })

        if (cacheRef.current.length && cachePeriodRef.current === klinePeriod) {
            const histData: HistogramData[] = []
            const ubData: LineData[] = []
            const lbData: LineData[] = []
            const uubData: LineData[] = []
            const llbData: LineData[] = []
            for (const p of cacheRef.current) {
                const time = toChartTime(p.date, klinePeriod)
                if (!time) continue
                histData.push({ time, value: p.mccd, color: getMccdColor(p) })
                if (p.ub != null) ubData.push({ time, value: p.ub })
                if (p.lb != null) lbData.push({ time, value: p.lb })
                if (p.uub != null) uubData.push({ time, value: p.uub })
                if (p.llb != null) llbData.push({ time, value: p.llb })
            }
            mccdSeries.setData(histData)
            ubSeries.setData(ubData)
            lbSeries.setData(lbData)
            uubSeries.setData(uubData)
            llbSeries.setData(llbData)
            chart.timeScale().fitContent()
        }

        mccdSeriesRef.current = mccdSeries
        ubSeriesRef.current = ubSeries
        lbSeriesRef.current = lbSeries
        uubSeriesRef.current = uubSeries
        llbSeriesRef.current = llbSeries
        chartRef.current = chart
        onChartReady?.(chart)

        const handleCrosshairMove = (param: MouseEventParams) => {
            if (!param.time) {
                setHoverPoint(null)
                return
            }
            const d = param.seriesData.get(mccdSeries) as HistogramData | undefined
            if (!d) {
                setHoverPoint(null)
                return
            }
            const dateStr = typeof param.time === 'object'
                ? `${param.time.year}-${String(param.time.month).padStart(2, '0')}-${String(param.time.day).padStart(2, '0')}`
                : new Date((param.time as number) * 1000).toISOString().slice(0, 10)
            const pt = cacheRef.current.find(p => p.date === dateStr)
            setHoverPoint(pt ?? null)
        }
        chart.subscribeCrosshairMove(handleCrosshairMove)

        const onResize = () => {
            if (!containerRef.current || !chartRef.current) return
            chartRef.current.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight })
        }
        window.addEventListener('resize', onResize)

        return () => {
            window.removeEventListener('resize', onResize)
            chart.unsubscribeCrosshairMove(handleCrosshairMove)
            chartRef.current?.remove()
            chartRef.current = null
            mccdSeriesRef.current = null
            ubSeriesRef.current = null
            lbSeriesRef.current = null
            uubSeriesRef.current = null
            llbSeriesRef.current = null
        }
    }, [isDark, klinePeriod])

    useEffect(() => {
        let cancelled = false
        const ac = new AbortController()
        const load = async () => {
            if (!mccdSeriesRef.current) return
            try {
                const resp = await api.getBollingerDeviation(symbol, range.start, range.end, klinePeriod, ac.signal)
                if (cancelled || ac.signal.aborted || !resp?.points) return
                if (useAnalysisStore.getState().klinePeriod !== klinePeriod) return

                setData(resp.points)
                cacheRef.current = resp.points
                cachePeriodRef.current = klinePeriod

                const histData: HistogramData[] = []
                const ubData: LineData[] = []
                const lbData: LineData[] = []
                const uubData: LineData[] = []
                const llbData: LineData[] = []
                for (const p of resp.points) {
                    const time = toChartTime(p.date, klinePeriod)
                    if (!time) continue
                    histData.push({ time, value: p.mccd, color: getMccdColor(p) })
                    if (p.ub != null) ubData.push({ time, value: p.ub })
                    if (p.lb != null) lbData.push({ time, value: p.lb })
                    if (p.uub != null) uubData.push({ time, value: p.uub })
                    if (p.llb != null) llbData.push({ time, value: p.llb })
                }
                mccdSeriesRef.current?.setData(histData)
                ubSeriesRef.current?.setData(ubData)
                lbSeriesRef.current?.setData(lbData)
                uubSeriesRef.current?.setData(uubData)
                llbSeriesRef.current?.setData(llbData)
                chartRef.current?.timeScale().fitContent()
                setTimeout(() => onSyncNow?.(), 100)
            } catch { if (ac.signal.aborted) return }
        }
        load()
        return () => { cancelled = true; ac.abort() }
    }, [symbol, range.start, range.end, klinePeriod, onSyncNow])

    const displayPoint = hoverPoint ?? (data.length ? data[data.length - 1] : null)
    const displayLabel = displayPoint ? getSignalLabel(displayPoint) : null
    const displayMccd = displayPoint?.mccd

    return (
        <div className="card">
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">布林乖离</span>
                    <span className="text-[11px] text-slate-400">
                        UB/LB<span className="mx-0.5" style={{ color: BAND_COLORS.ub }}>━</span>
                        UUB/LLB<span className="mx-0.5" style={{ color: BAND_COLORS.uub }}>━</span>
                    </span>
                </div>
                {displayPoint != null && (
                    <div className="flex items-center gap-3 text-xs">
                        {displayLabel && (
                            <span className="font-medium" style={{ color: getMccdColor(displayPoint) }}>
                                {displayLabel}
                            </span>
                        )}
                        {displayMccd != null && (
                            <span className="text-slate-500">
                                MCCD: {displayMccd >= 0 ? '+' : ''}{(displayMccd / 1e4).toFixed(1)}万
                            </span>
                        )}
                    </div>
                )}
            </div>
            <div className="relative h-[150px] rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 overflow-hidden">
                <div ref={containerRef} className="absolute inset-0" />
            </div>
        </div>
    )
}
