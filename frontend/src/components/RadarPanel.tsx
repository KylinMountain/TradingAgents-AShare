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
    Time,
    createChart,
    createSeriesMarkers,
} from 'lightweight-charts'
import { Radar } from 'lucide-react'
import { api } from '@/services/api'
import type { RadarPoint } from '@/types'

interface RadarPanelProps {
    symbol: string
}

function toBusinessDay(value: string): BusinessDay | null {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
    if (!m) return null
    return { year: Number(m[1]), month: Number(m[2]), day: Number(m[3]) }
}

export default function RadarPanel({ symbol }: RadarPanelProps) {
    const containerRef = useRef<HTMLDivElement | null>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const avgSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
    const waveSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
    const zeroLineRef = useRef<ISeriesApi<'Line'> | null>(null)
    const overboughtRef = useRef<ISeriesApi<'Line'> | null>(null)
    const oversoldRef = useRef<ISeriesApi<'Line'> | null>(null)
    const histRefs = useRef<Record<string, ISeriesApi<'Histogram'>>>({})
    const markersRef = useRef<any>(null)
    const [radarData, setRadarData] = useState<RadarPoint[]>([])
    const [isDark, setIsDark] = useState(document.documentElement.classList.contains('dark'))

    const range = useMemo(() => {
        const end = new Date()
        const start = new Date(end.getTime() - 180 * 24 * 60 * 60 * 1000)
        const toText = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
        return { start: toText(start), end: toText(end) }
    }, [])

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

        avgSeriesRef.current = avgSeries
        waveSeriesRef.current = waveSeries
        zeroLineRef.current = zeroLine
        overboughtRef.current = overboughtLine
        oversoldRef.current = oversoldLine
        histRefs.current = { up: upHist, down: downHist }
        chartRef.current = chart

        const onResize = () => {
            if (!containerRef.current || !chartRef.current) return
            chartRef.current.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight })
        }
        window.addEventListener('resize', onResize)

        return () => {
            window.removeEventListener('resize', onResize)
            chartRef.current?.remove()
            chartRef.current = null
            avgSeriesRef.current = null
            waveSeriesRef.current = null
            zeroLineRef.current = null
            overboughtRef.current = null
            oversoldRef.current = null
            histRefs.current = {}
        }
    }, [isDark])

    // Load data
    useEffect(() => {
        let cancelled = false
        api.getRadar(symbol, range.start, range.end)
            .then(resp => {
                if (cancelled || !resp?.points) return
                setRadarData(resp.points)
            })
            .catch(() => {})
        return () => { cancelled = true }
    }, [symbol, range.start, range.end])

    // Update series
    useEffect(() => {
        const avgSeries = avgSeriesRef.current
        const waveSeries = waveSeriesRef.current
        const histSeries = histRefs.current
        if (!avgSeries || !histSeries.up || !radarData.length) return

        const avgData: LineData[] = []
        const waveData: LineData[] = []
        const upHistData: HistogramData[] = []
        const downHistData: HistogramData[] = []

        let prevAvg: number | null = null
        for (const p of radarData) {
            if (p.radar_avg == null) continue
            const time = toBusinessDay(p.date)
            if (!time) continue

            avgData.push({ time: time as Time, value: p.radar_avg })
            if (p.radar_wave != null) {
                waveData.push({ time: time as Time, value: p.radar_wave })
            }

            if (prevAvg !== null) {
                const diff = p.radar_avg - prevAvg
                const entry = { time: time as Time, value: diff }
                if (diff >= 0) upHistData.push(entry)
                else downHistData.push(entry)
            }
            prevAvg = p.radar_avg
        }

        avgSeries.setData(avgData)
        waveSeries?.setData(waveData)
        histSeries.up.setData(upHistData)
        histSeries.down.setData(downHistData)

        // Zero line at 0
        if (zeroLineRef.current && avgData.length > 0) {
            zeroLineRef.current.setData(avgData.map(d => ({ time: d.time, value: 0 })))
        }
        // Overbought line at 3.2
        if (overboughtRef.current && avgData.length > 0) {
            overboughtRef.current.setData(avgData.map(d => ({ time: d.time, value: 3.2 })))
        }
        // Oversold line at 0.5
        if (oversoldRef.current && avgData.length > 0) {
            oversoldRef.current.setData(avgData.map(d => ({ time: d.time, value: 0.5 })))
        }

        // Signal markers
        const signalMarkers = radarData
            .filter(p => p.radar_buy || p.radar_sell || p.radar_top || p.radar_down)
            .map(p => {
                const time = toBusinessDay(p.date)
                if (!time) return null
                if (p.radar_buy) return { time: time as Time, position: 'belowBar' as const, color: '#ef4444', shape: 'arrowUp' as const, text: '底' }
                if (p.radar_sell) return { time: time as Time, position: 'belowBar' as const, color: '#f59e0b', shape: 'arrowUp' as const, text: '升' }
                if (p.radar_top) return { time: time as Time, position: 'aboveBar' as const, color: '#22c55e', shape: 'arrowDown' as const, text: '顶' }
                if (p.radar_down) return { time: time as Time, position: 'aboveBar' as const, color: '#06b6d4', shape: 'arrowDown' as const, text: '下' }
                return null
            })
            .filter(Boolean)

        markersRef.current?.setMarkers(signalMarkers as any)
        chartRef.current?.timeScale().fitContent()
    }, [radarData])

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
                            <span className="text-blue-400 font-medium">{lastPoint.radar_wave ?? '--'}</span>
                        </span>
                        <span className="flex items-center gap-1">
                            <span className="inline-block w-3 h-0.5 bg-yellow-400" />
                            <span className="text-slate-500 dark:text-slate-400">平均线</span>
                            <span className="text-yellow-500 font-medium">{lastPoint.radar_avg ?? '--'}</span>
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
