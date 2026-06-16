import { useEffect, useMemo, useRef, useState } from 'react'
import {
    BusinessDay,
    ColorType,
    HistogramData,
    HistogramSeries,
    IChartApi,
    ISeriesApi,
    MouseEventParams,
    Time,
    UTCTimestamp,
    createChart,
} from 'lightweight-charts'
import { api } from '@/services/api'
import type { FundFlowPoint, KlinePeriod } from '@/types'
import { useAnalysisStore } from '@/stores/analysisStore'

interface FundFlowPanelProps {
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

function fmtAmount(v: number): string {
    const abs = Math.abs(v)
    if (abs >= 1e4) return `${(abs / 1e4).toFixed(2)}亿`
    if (abs >= 1) return `${abs.toFixed(0)}万`
    return `${(abs * 10000).toFixed(0)}元`
}

export default function FundFlowPanel({ symbol, onChartReady, onSyncNow }: FundFlowPanelProps) {
    const klinePeriod = useAnalysisStore((state) => state.klinePeriod)
    const containerRef = useRef<HTMLDivElement | null>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const seriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
    const cacheRef = useRef<FundFlowPoint[]>([])
    const cachePeriodRef = useRef<KlinePeriod>('daily')
    const [data, setData] = useState<FundFlowPoint[]>([])
    const [hoverPoint, setHoverPoint] = useState<FundFlowPoint | null>(null)
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

        const series = chart.addSeries(HistogramSeries, {
            priceLineVisible: false,
            lastValueVisible: true,
            priceFormat: { type: 'volume' },
        })

        if (cacheRef.current.length && cachePeriodRef.current === klinePeriod) {
            const histData: HistogramData[] = []
            for (const p of cacheRef.current) {
                const time = toChartTime(p.date, klinePeriod)
                if (!time) continue
                const v = p.main_net ?? 0
                histData.push({ time, value: Math.abs(v), color: v >= 0 ? '#ef4444' : '#22c55e' })
            }
            series.setData(histData)
            chart.timeScale().fitContent()
        }

        seriesRef.current = series
        chartRef.current = chart
        onChartReady?.(chart)

        const handleCrosshairMove = (param: MouseEventParams) => {
            if (!param.time) {
                setHoverPoint(null)
                return
            }
            const d = param.seriesData.get(series) as HistogramData | undefined
            if (!d || !d.value) {
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
            seriesRef.current = null
        }
    }, [isDark, klinePeriod])

    useEffect(() => {
        let cancelled = false
        const ac = new AbortController()
        const load = async () => {
            if (!seriesRef.current) return
            try {
                const resp = await api.getFundFlow(symbol, range.start, range.end, klinePeriod, ac.signal)
                if (cancelled || ac.signal.aborted || !resp?.points) return
                if (useAnalysisStore.getState().klinePeriod !== klinePeriod) return

                setData(resp.points)
                cacheRef.current = resp.points
                cachePeriodRef.current = klinePeriod

                const histData: HistogramData[] = []
                for (const p of resp.points) {
                    const time = toChartTime(p.date, klinePeriod)
                    if (!time) continue
                    const v = p.main_net ?? 0
                    histData.push({ time, value: Math.abs(v), color: v >= 0 ? '#ef4444' : '#22c55e' })
                }
                seriesRef.current?.setData(histData)
                chartRef.current?.timeScale().fitContent()
                setTimeout(() => onSyncNow?.(), 100)
            } catch { if (ac.signal.aborted) return }
        }
        load()
        return () => { cancelled = true; ac.abort() }
    }, [symbol, range.start, range.end, klinePeriod, onSyncNow])

    const displayPoint = hoverPoint ?? (data.length ? data[data.length - 1] : null)
    const displayMainNet = displayPoint?.main_net

    return (
        <div className="card">
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">主力资金流向</span>
                </div>
                {displayMainNet != null && (
                    <div className="flex items-center gap-3 text-xs">
                        <span className={`font-medium ${displayMainNet >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>
                            {displayMainNet >= 0 ? '流入' : '流出'} {fmtAmount(displayMainNet)}
                        </span>
                        {displayPoint?.main_pct != null && (
                            <span className={`${displayPoint.main_pct >= 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                                {displayPoint.main_pct >= 0 ? '+' : ''}{displayPoint.main_pct.toFixed(2)}%
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
