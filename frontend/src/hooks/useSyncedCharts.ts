import { useCallback, useRef } from 'react'
import type { IChartApi, Time, TimeRangeChangeEventHandler } from 'lightweight-charts'

/**
 * 同步两个 lightweight-charts 图表的可见时间范围（缩放/滚动双向同步）。
 * 使用时间值同步而非逻辑索引，确保不同数据量的图表时间轴对齐。
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

        // 清理旧订阅
        if (handlersRef.current.klineHandler) {
            kline.timeScale().unsubscribeVisibleTimeRangeChange(handlersRef.current.klineHandler)
        }
        if (handlersRef.current.radarHandler) {
            radar.timeScale().unsubscribeVisibleTimeRangeChange(handlersRef.current.radarHandler)
        }

        // K线 → 雷达
        const klineHandler: TimeRangeChangeEventHandler<Time> = (range: { from: Time; to: Time } | null) => {
            if (syncingRef.current || !range) return
            syncingRef.current = true
            try { radar.timeScale().setVisibleRange(range) } catch {}
            syncingRef.current = false
        }

        // 雷达 → K线
        const radarHandler: TimeRangeChangeEventHandler<Time> = (range: { from: Time; to: Time } | null) => {
            if (syncingRef.current || !range) return
            syncingRef.current = true
            try { kline.timeScale().setVisibleRange(range) } catch {}
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

    return { registerKlineChart, registerRadarChart }
}
