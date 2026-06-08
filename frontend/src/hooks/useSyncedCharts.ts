import { useCallback, useRef } from 'react'
import type { IChartApi, Time, TimeRangeChangeEventHandler } from 'lightweight-charts'

/**
 * 同步主图(K线)与多个副图的可见时间范围（缩放/滚动双向同步）。
 */
export function useSyncedCharts() {
    const klineChartRef = useRef<IChartApi | null>(null)
    const subChartsRef = useRef<Map<string, IChartApi>>(new Map())
    const syncingRef = useRef(false)
    const handlersRef = useRef<Map<string, { kline: TimeRangeChangeEventHandler<Time>; sub: TimeRangeChangeEventHandler<Time> }>>(new Map())

    const teardownSync = useCallback(() => {
        const kline = klineChartRef.current
        if (!kline) return
        for (const [key, handlers] of handlersRef.current) {
            const sub = subChartsRef.current.get(key)
            if (sub) {
                kline.timeScale().unsubscribeVisibleTimeRangeChange(handlers.kline)
                sub.timeScale().unsubscribeVisibleTimeRangeChange(handlers.sub)
            }
        }
        handlersRef.current.clear()
    }, [])

    const setupSync = useCallback(() => {
        teardownSync()
        const kline = klineChartRef.current
        if (!kline) return

        for (const [key, sub] of subChartsRef.current) {
            const klineHandler: TimeRangeChangeEventHandler<Time> = () => {
                if (syncingRef.current) return
                const src = klineChartRef.current
                const dst = subChartsRef.current.get(key)
                if (!src || !dst) return
                const logical = src.timeScale().getVisibleLogicalRange()
                if (!logical) return
                syncingRef.current = true
                try { dst.timeScale().setVisibleLogicalRange(logical) } catch {}
                syncingRef.current = false
            }

            const subHandler: TimeRangeChangeEventHandler<Time> = () => {
                if (syncingRef.current) return
                const src = subChartsRef.current.get(key)
                const dst = klineChartRef.current
                if (!src || !dst) return
                const logical = src.timeScale().getVisibleLogicalRange()
                if (!logical) return
                syncingRef.current = true
                try { dst.timeScale().setVisibleLogicalRange(logical) } catch {}
                syncingRef.current = false
            }

            kline.timeScale().subscribeVisibleTimeRangeChange(klineHandler)
            sub.timeScale().subscribeVisibleTimeRangeChange(subHandler)
            handlersRef.current.set(key, { kline: klineHandler, sub: subHandler })
        }
    }, [teardownSync])

    const registerKlineChart = useCallback((chart: IChartApi) => {
        klineChartRef.current = chart
        setupSync()
    }, [setupSync])

    const registerSubChart = useCallback((key: string, chart: IChartApi) => {
        subChartsRef.current.set(key, chart)
        setupSync()
    }, [setupSync])

    const syncNow = useCallback(() => {
        const src = klineChartRef.current
        if (!src) return
        const logical = src.timeScale().getVisibleLogicalRange()
        if (!logical) return
        for (const [, sub] of subChartsRef.current) {
            try { sub.timeScale().setVisibleLogicalRange(logical) } catch {}
        }
    }, [])

    return { registerKlineChart, registerSubChart, syncNow }
}
