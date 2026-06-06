import { useCallback, useRef } from 'react'
import type { IChartApi, LogicalRange, LogicalRangeChangeEventHandler } from 'lightweight-charts'

/**
 * 同步两个 lightweight-charts 图表的可见时间范围（缩放/滚动双向同步）。
 * K线图和主力雷达图共享时间轴，缩放任一图表时另一图表自动跟随。
 */
export function useSyncedCharts() {
    const klineChartRef = useRef<IChartApi | null>(null)
    const radarChartRef = useRef<IChartApi | null>(null)
    const syncingRef = useRef(false)
    const handlersRef = useRef<{
        klineHandler: LogicalRangeChangeEventHandler | null
        radarHandler: LogicalRangeChangeEventHandler | null
    }>({ klineHandler: null, radarHandler: null })

    const setupRangeSync = useCallback(() => {
        const kline = klineChartRef.current
        const radar = radarChartRef.current
        if (!kline || !radar) return

        // 清理旧订阅
        if (handlersRef.current.klineHandler) {
            kline.timeScale().unsubscribeVisibleLogicalRangeChange(handlersRef.current.klineHandler)
        }
        if (handlersRef.current.radarHandler) {
            radar.timeScale().unsubscribeVisibleLogicalRangeChange(handlersRef.current.radarHandler)
        }

        // K线 → 雷达
        const klineHandler: LogicalRangeChangeEventHandler = (range: LogicalRange | null) => {
            if (syncingRef.current || !range) return
            syncingRef.current = true
            radar.timeScale().setVisibleLogicalRange(range)
            syncingRef.current = false
        }

        // 雷达 → K线
        const radarHandler: LogicalRangeChangeEventHandler = (range: LogicalRange | null) => {
            if (syncingRef.current || !range) return
            syncingRef.current = true
            kline.timeScale().setVisibleLogicalRange(range)
            syncingRef.current = false
        }

        kline.timeScale().subscribeVisibleLogicalRangeChange(klineHandler)
        radar.timeScale().subscribeVisibleLogicalRangeChange(radarHandler)

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
