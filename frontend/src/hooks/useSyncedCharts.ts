import { useCallback, useRef } from 'react'
import type { IChartApi, Time, TimeRangeChangeEventHandler } from 'lightweight-charts'

/**
 * 同步两个 lightweight-charts 图表的可见时间范围（缩放/滚动双向同步）。
 *
 * 事件驱动 + 直接逻辑范围复制：用 subscribeVisibleTimeRangeChange 检测缩放，
 * 然后读取源图表的当前可见逻辑范围，直接应用到目标图表。
 */
export function useSyncedCharts() {
    const klineChartRef = useRef<IChartApi | null>(null)
    const radarChartRef = useRef<IChartApi | null>(null)
    const syncingRef = useRef(false)
    const handlersRef = useRef<{
        klineHandler: TimeRangeChangeEventHandler<Time> | null
        radarHandler: TimeRangeChangeEventHandler<Time> | null
    }>({ klineHandler: null, radarHandler: null })

    const setupRangeSync = useCallback(() => {
        const kline = klineChartRef.current
        const radar = radarChartRef.current
        if (!kline || !radar) return

        if (handlersRef.current.klineHandler) {
            kline.timeScale().unsubscribeVisibleTimeRangeChange(handlersRef.current.klineHandler)
        }
        if (handlersRef.current.radarHandler) {
            radar.timeScale().unsubscribeVisibleTimeRangeChange(handlersRef.current.radarHandler)
        }

        const klineHandler: TimeRangeChangeEventHandler<Time> = () => {
            if (syncingRef.current) return
            const src = klineChartRef.current
            const dst = radarChartRef.current
            if (!src || !dst) return
            const logical = src.timeScale().getVisibleLogicalRange()
            if (!logical) return
            syncingRef.current = true
            try { dst.timeScale().setVisibleLogicalRange(logical) } catch {}
            syncingRef.current = false
        }

        const radarHandler: TimeRangeChangeEventHandler<Time> = () => {
            if (syncingRef.current) return
            const src = radarChartRef.current
            const dst = klineChartRef.current
            if (!src || !dst) return
            const logical = src.timeScale().getVisibleLogicalRange()
            if (!logical) return
            syncingRef.current = true
            try { dst.timeScale().setVisibleLogicalRange(logical) } catch {}
            syncingRef.current = false
        }

        kline.timeScale().subscribeVisibleTimeRangeChange(klineHandler)
        radar.timeScale().subscribeVisibleTimeRangeChange(radarHandler)

        handlersRef.current = { klineHandler, radarHandler }
    }, [])

    const registerKlineChart = useCallback((chart: IChartApi) => {
        klineChartRef.current = chart
        setupRangeSync()
    }, [setupRangeSync])

    const registerRadarChart = useCallback((chart: IChartApi) => {
        radarChartRef.current = chart
        setupRangeSync()
    }, [setupRangeSync])

    const syncNow = useCallback(() => {
        const src = klineChartRef.current
        const dst = radarChartRef.current
        if (!src || !dst) return
        const logical = src.timeScale().getVisibleLogicalRange()
        if (logical) {
            try { dst.timeScale().setVisibleLogicalRange(logical) } catch {}
        }
    }, [])

    return { registerKlineChart, registerRadarChart, syncNow }
}
