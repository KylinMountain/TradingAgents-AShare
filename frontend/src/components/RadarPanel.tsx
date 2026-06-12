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
    LineStyle,
    MouseEventParams,
    Time,
    UTCTimestamp,
    createChart,
    createSeriesMarkers,
} from 'lightweight-charts'
import { Radar } from 'lucide-react'
import { api } from '@/services/api'
import type { RadarPoint } from '@/types'
import { useAnalysisStore } from '@/stores/analysisStore'
import type { KlinePeriod } from '@/types'

interface RadarPanelProps {
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

export default function RadarPanel({ symbol, onChartReady, onSyncNow }: RadarPanelProps) {
    const klinePeriod = useAnalysisStore((state) => state.klinePeriod)
    const containerRef = useRef<HTMLDivElement | null>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const avgSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
    const waveSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
    const zeroLineRef = useRef<ISeriesApi<'Line'> | null>(null)
    const overboughtRef = useRef<ISeriesApi<'Line'> | null>(null)
    const oversoldRef = useRef<ISeriesApi<'Line'> | null>(null)
    const histRefs = useRef<Record<string, ISeriesApi<'Histogram'>>>({})
    const markersRef = useRef<any>(null)
    const radarCacheRef = useRef<RadarPoint[]>([])
    const radarPeriodRef = useRef<KlinePeriod>('daily')
    const [radarData, setRadarData] = useState<RadarPoint[]>([])
    const [hoverData, setHoverData] = useState<{ wave: number | null; avg: number | null } | null>(null)
    const [isDark, setIsDark] = useState(document.documentElement.classList.contains('dark'))

    const range = useMemo(() => {
        const end = new Date()
        const rangeDays = klinePeriod === 'daily' ? 180 : klinePeriod === 'weekly' ? 730 : 1825
        const start = new Date(end.getTime() - rangeDays * 24 * 60 * 60 * 1000)
        const toText = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
        return { start: toText(start), end: toText(end) }
    }, [klinePeriod])

    // Theme observer
    useEffect(() => {
        const observer = new MutationObserver(() => {
            setIsDark(document.documentElement.classList.contains('dark'))
        })
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
        return () => observer.disconnect()
    }, [])

    // Chart init
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
                        const y = d.getUTCFullYear()
                        const m = String(d.getUTCMonth() + 1).padStart(2, '0')
                        const day = String(d.getUTCDate()).padStart(2, '0')
                        return `${y}/${m}/${day}`
                    }
                    if (typeof time === 'object') {
                        const y = String(time.year)
                        const m = String(time.month).padStart(2, '0')
                        const d = String(time.day).padStart(2, '0')
                        return `${y}/${m}/${d}`
                    }
                    return String(time)
                },
            },
            crosshair: {
                vertLine: { color: isDark ? 'rgba(59, 130, 246, 0.35)' : 'rgba(59, 130, 246, 0.25)' },
                horzLine: { color: isDark ? 'rgba(59, 130, 246, 0.35)' : 'rgba(59, 130, 246, 0.25)' },
            },
        })

        const avgSeries = chart.addSeries(LineSeries, {
            color: '#eab308', lineWidth: 2, lineStyle: LineStyle.Solid,
            priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: true,
        })
        const waveSeries = chart.addSeries(LineSeries, {
            color: '#60a5fa', lineWidth: 1, lineStyle: LineStyle.Solid,
            priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: true,
        })
        const zeroLine = chart.addSeries(LineSeries, {
            color: '#64748b', lineWidth: 1, lineStyle: LineStyle.Solid,
            priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        })
        const overboughtLine = chart.addSeries(LineSeries, {
            color: '#eab308', lineWidth: 1, lineStyle: LineStyle.Dashed,
            priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        })
        const oversoldLine = chart.addSeries(LineSeries, {
            color: '#eab308', lineWidth: 1, lineStyle: LineStyle.Dashed,
            priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        })
        const upHist = chart.addSeries(HistogramSeries, {
            color: '#ef4444', priceLineVisible: false, lastValueVisible: false,
        })
        const downHist = chart.addSeries(HistogramSeries, {
            color: '#22c55e', priceLineVisible: false, lastValueVisible: false,
        })

        // Markers on main series via createSeriesMarkers on avgSeries
        const markers = createSeriesMarkers(avgSeries)
        markersRef.current = markers

        // Immediately apply cached data if chart is recreated for same period
        if (radarCacheRef.current.length && radarPeriodRef.current === klinePeriod) {
            const pts = radarCacheRef.current
            const avgData: LineData[] = []
            const waveData: LineData[] = []
            const upHistData: HistogramData[] = []
            const downHistData: HistogramData[] = []
            let prevAvg: number | null = null
            for (const p of pts) {
                if (p.radar_avg == null) continue
                const t = toChartTime(p.date, klinePeriod)
                if (!t) continue
                avgData.push({ time: t, value: p.radar_avg })
                if (p.radar_wave != null) {
                    waveData.push({ time: t, value: p.radar_wave })
                }
                if (prevAvg !== null) {
                    const diff = p.radar_avg - prevAvg
                    if (diff >= 0) upHistData.push({ time: t, value: diff })
                    else downHistData.push({ time: t, value: diff })
                }
                prevAvg = p.radar_avg
            }
            avgSeries.setData(avgData)
            waveSeries.setData(waveData)
            upHist.setData(upHistData)
            downHist.setData(downHistData)
            if (avgData.length > 0) {
                zeroLine.setData(avgData.map(d => ({ time: d.time, value: 0 })))
                overboughtLine.setData(avgData.map(d => ({ time: d.time, value: 3.2 })))
                oversoldLine.setData(avgData.map(d => ({ time: d.time, value: 0.5 })))
            }
            const signalMarkers = pts
                .filter(p => p.radar_buy || p.radar_sell || p.radar_top || p.radar_down)
                .map(p => {
                    const t = toChartTime(p.date, klinePeriod)
                    if (!t) return null
                    if (p.radar_buy) return { time: t, position: 'belowBar' as const, color: '#ef4444', shape: 'arrowUp' as const, text: '底' }
                    if (p.radar_sell) return { time: t, position: 'belowBar' as const, color: '#f59e0b', shape: 'arrowUp' as const, text: '升' }
                    if (p.radar_top) return { time: t, position: 'aboveBar' as const, color: '#22c55e', shape: 'arrowDown' as const, text: '顶' }
                    if (p.radar_down) return { time: t, position: 'aboveBar' as const, color: '#06b6d4', shape: 'arrowDown' as const, text: '下' }
                    return null
                })
                .filter(Boolean)
            markers.setMarkers(signalMarkers as any)
            chart.timeScale().fitContent()
        }

        avgSeriesRef.current = avgSeries
        waveSeriesRef.current = waveSeries
        zeroLineRef.current = zeroLine
        overboughtRef.current = overboughtLine
        oversoldRef.current = oversoldLine
        histRefs.current = { up: upHist, down: downHist }
        chartRef.current = chart
        onChartReady?.(chart)

        const handleCrosshairMove = (param: MouseEventParams) => {
            if (!param.time) {
                setHoverData(null)
                return
            }
            const waveValue = param.seriesData.get(waveSeries) as LineData | undefined
            const avgValue = param.seriesData.get(avgSeries) as LineData | undefined
            setHoverData({
                wave: waveValue?.value ?? null,
                avg: avgValue?.value ?? null,
            })
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
            avgSeriesRef.current = null
            waveSeriesRef.current = null
            zeroLineRef.current = null
            overboughtRef.current = null
            oversoldRef.current = null
            histRefs.current = {}
        }
    }, [isDark, klinePeriod])

    // Load data and apply to series
    useEffect(() => {
        let cancelled = false
        const ac = new AbortController()
        const load = async () => {
            if (!avgSeriesRef.current || !histRefs.current.up) return
            try {
                const resp = await api.getRadar(symbol, range.start, range.end, klinePeriod, ac.signal)
                if (cancelled || ac.signal.aborted || !resp?.points) return
                if (useAnalysisStore.getState().klinePeriod !== klinePeriod) return

                setRadarData(resp.points)
                radarCacheRef.current = resp.points
                radarPeriodRef.current = klinePeriod

                const avgSeries = avgSeriesRef.current
                const waveSeries = waveSeriesRef.current
                const histSeries = histRefs.current
                if (!avgSeries || !histSeries.up) return

                const avgData: LineData[] = []
                const waveData: LineData[] = []
                const upHistData: HistogramData[] = []
                const downHistData: HistogramData[] = []

                let prevAvg: number | null = null
                for (const p of resp.points) {
                    if (p.radar_avg == null) continue
                    const time = toChartTime(p.date, klinePeriod)
                    if (!time) continue

                    avgData.push({ time, value: p.radar_avg })
                    if (p.radar_wave != null) {
                        waveData.push({ time, value: p.radar_wave })
                    }

                    if (prevAvg !== null) {
                        const diff = p.radar_avg - prevAvg
                        const entry = { time, value: diff }
                        if (diff >= 0) upHistData.push(entry)
                        else downHistData.push(entry)
                    }
                    prevAvg = p.radar_avg
                }

                avgSeries.setData(avgData)
                waveSeries?.setData(waveData)
                histSeries.up.setData(upHistData)
                histSeries.down.setData(downHistData)

                if (zeroLineRef.current && avgData.length > 0) {
                    zeroLineRef.current.setData(avgData.map(d => ({ time: d.time, value: 0 })))
                }
                if (overboughtRef.current && avgData.length > 0) {
                    overboughtRef.current.setData(avgData.map(d => ({ time: d.time, value: 3.2 })))
                }
                if (oversoldRef.current && avgData.length > 0) {
                    oversoldRef.current.setData(avgData.map(d => ({ time: d.time, value: 0.5 })))
                }

                const signalMarkers = resp.points
                    .filter(p => p.radar_buy || p.radar_sell || p.radar_top || p.radar_down)
                    .map(p => {
                        const time = toChartTime(p.date, klinePeriod)
                        if (!time) return null
                        if (p.radar_buy) return { time, position: 'belowBar' as const, color: '#ef4444', shape: 'arrowUp' as const, text: '底' }
                        if (p.radar_sell) return { time, position: 'belowBar' as const, color: '#f59e0b', shape: 'arrowUp' as const, text: '升' }
                        if (p.radar_top) return { time, position: 'aboveBar' as const, color: '#22c55e', shape: 'arrowDown' as const, text: '顶' }
                        if (p.radar_down) return { time, position: 'aboveBar' as const, color: '#06b6d4', shape: 'arrowDown' as const, text: '下' }
                        return null
                    })
                    .filter(Boolean)

                markersRef.current?.setMarkers(signalMarkers as any)
                chartRef.current?.timeScale().fitContent()
                // 初始加载/切换周期后从K线同步一次逻辑范围
                setTimeout(() => onSyncNow?.(), 100)
            } catch { if (ac.signal.aborted) return }
        }
        load()
        return () => { cancelled = true; ac.abort() }
    }, [symbol, range.start, range.end, klinePeriod, onSyncNow])

    const lastPoint = radarData.length ? radarData[radarData.length - 1] : null

    return (
        <div className="card">
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <Radar className="w-4 h-4 text-yellow-500" />
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">主力趋势雷达</span>
                </div>
                {lastPoint && (
                    <div className="flex items-center gap-3 text-xs">
                        <span className="flex items-center gap-1">
                            <span className="inline-block w-3 h-0.5 bg-blue-400" />
                            <span className="text-slate-500 dark:text-slate-400">波动线</span>
                            <span className="text-blue-400 font-medium">{hoverData?.wave?.toFixed(2) ?? lastPoint.radar_wave ?? '--'}</span>
                        </span>
                        <span className="flex items-center gap-1">
                            <span className="inline-block w-3 h-0.5 bg-yellow-400" />
                            <span className="text-slate-500 dark:text-slate-400">平均线</span>
                            <span className="text-yellow-500 font-medium">{hoverData?.avg?.toFixed(2) ?? lastPoint.radar_avg ?? '--'}</span>
                        </span>
                        <span className="flex items-center gap-1">
                            <span className="inline-block w-3 h-0.5 bg-slate-500" />
                            <span className="text-slate-500 dark:text-slate-400">零轴</span>
                        </span>
                        {lastPoint.radar_buy && <span className="text-red-500 font-bold">底</span>}
                        {lastPoint.radar_sell && <span className="text-amber-500 font-bold">升</span>}
                        {lastPoint.radar_top && <span className="text-green-500 font-bold">顶</span>}
                        {lastPoint.radar_down && <span className="text-cyan-500 font-bold">下</span>}
                    </div>
                )}
            </div>
            <div className="relative h-[150px] rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 overflow-hidden">
                <div ref={containerRef} className="absolute inset-0" />
            </div>
        </div>
    )
}
