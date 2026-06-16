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
import type { PositionPoint, KlinePeriod } from '@/types'
import { useAnalysisStore } from '@/stores/analysisStore'

interface PositionPanelProps {
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

const zoneColors: Record<string, string> = {
    overbought: 'text-red-500',
    high: 'text-orange-500',
    neutral: 'text-slate-500',
    low: 'text-green-500',
    oversold: 'text-blue-500',
}
const zoneLabels: Record<string, string> = {
    overbought: '超买',
    high: '偏高',
    neutral: '中性',
    low: '偏低',
    oversold: '超卖',
}

export default function PositionPanel({ symbol, onChartReady, onSyncNow }: PositionPanelProps) {
    const klinePeriod = useAnalysisStore((state) => state.klinePeriod)
    const containerRef = useRef<HTMLDivElement | null>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const seriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
    const cacheRef = useRef<PositionPoint[]>([])
    const cachePeriodRef = useRef<KlinePeriod>('daily')
    const [data, setData] = useState<PositionPoint[]>([])
    const [hoverData, setHoverData] = useState<{ index: number | null; zone: string | null } | null>(null)
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
            priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
        })

        if (cacheRef.current.length && cachePeriodRef.current === klinePeriod) {
            const histData: HistogramData[] = []
            for (const p of cacheRef.current) {
                const time = toChartTime(p.date, klinePeriod)
                if (!time) continue
                if (p.position_index == null) {
                    histData.push({ time, value: 0, color: 'rgba(0,0,0,0)' })
                } else {
                    let color = '#64748b'
                    if (p.zone === 'overbought') color = '#ef4444'
                    else if (p.zone === 'high') color = '#f97316'
                    else if (p.zone === 'low') color = '#22c55e'
                    else if (p.zone === 'oversold') color = '#3b82f6'
                    histData.push({ time, value: p.position_index, color })
                }
            }
            series.setData(histData)
            chart.timeScale().fitContent()
        }

        seriesRef.current = series
        chartRef.current = chart
        onChartReady?.(chart)

        const handleCrosshairMove = (param: MouseEventParams) => {
            if (!param.time) {
                setHoverData(null)
                return
            }
            const data = param.seriesData.get(series) as HistogramData | undefined
            if (data && data.value !== 0) {
                // Find the corresponding point to get zone
                const dateStr = typeof param.time === 'object'
                    ? `${param.time.year}-${String(param.time.month).padStart(2, '0')}-${String(param.time.day).padStart(2, '0')}`
                    : new Date((param.time as number) * 1000).toISOString().slice(0, 10)
                const pt = cacheRef.current.find(p => p.date === dateStr)
                setHoverData({ index: data.value, zone: pt?.zone ?? null })
            } else {
                setHoverData({ index: null, zone: null })
            }
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
                const resp = await api.getPosition(symbol, range.start, range.end, klinePeriod, ac.signal)
                if (cancelled || ac.signal.aborted || !resp?.points) return
                if (useAnalysisStore.getState().klinePeriod !== klinePeriod) return

                setData(resp.points)
                cacheRef.current = resp.points
                cachePeriodRef.current = klinePeriod

                const histData: HistogramData[] = []
                for (const p of resp.points) {
                    const time = toChartTime(p.date, klinePeriod)
                    if (!time) continue
                    if (p.position_index == null) {
                        histData.push({ time, value: 0, color: 'rgba(0,0,0,0)' })
                    } else {
                        let color = '#64748b'
                        if (p.zone === 'overbought') color = '#ef4444'
                        else if (p.zone === 'high') color = '#f97316'
                        else if (p.zone === 'low') color = '#22c55e'
                        else if (p.zone === 'oversold') color = '#3b82f6'
                        histData.push({ time, value: p.position_index, color })
                    }
                }
                seriesRef.current?.setData(histData)
                chartRef.current?.timeScale().fitContent()
                setTimeout(() => onSyncNow?.(), 100)
            } catch { if (ac.signal.aborted) return }
        }
        load()
        return () => { cancelled = true; ac.abort() }
    }, [symbol, range.start, range.end, klinePeriod, onSyncNow])

    const lastPoint = data.length ? data[data.length - 1] : null
    const displayIndex = hoverData?.index ?? lastPoint?.position_index
    const displayZone = hoverData?.zone ?? lastPoint?.zone

    return (
        <div className="card">
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">位置指标</span>
                </div>
                {displayIndex != null && (
                    <div className="flex items-center gap-3 text-xs">
                        <span className={`font-medium ${zoneColors[displayZone ?? 'neutral'] ?? 'text-slate-500'}`}>
                            {displayIndex.toFixed(1)}
                        </span>
                        <span className={zoneColors[displayZone ?? 'neutral'] ?? 'text-slate-500'}>
                            {zoneLabels[displayZone ?? 'neutral'] ?? '--'}
                        </span>
                    </div>
                )}
            </div>
            <div className="relative h-[150px] rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 overflow-hidden">
                <div ref={containerRef} className="absolute inset-0" />
            </div>
        </div>
    )
}
