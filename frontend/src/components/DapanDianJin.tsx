import { Activity, TrendingDown, TrendingUp, Minus } from 'lucide-react'
import type { YangYinHistoryPoint, GoldFingerPoint, RedGreenBgPoint } from '@/types'

function getBgClass(bg: string | undefined): string {
    if (bg === '红') return 'bg-red-50 dark:bg-red-950/30'
    if (bg === '绿') return 'bg-green-50 dark:bg-green-950/30'
    return ''
}

interface DapanDianJinProps {
    history?: YangYinHistoryPoint[]
    goldFingerHistory?: GoldFingerPoint[]
    redGreenBgHistory?: RedGreenBgPoint[]
}

export default function DapanDianJin({ history, goldFingerHistory, redGreenBgHistory }: DapanDianJinProps) {
    if (!history || history.length < 2) return null
    const latest = history[history.length - 1]
    const prev = history[history.length - 2]
    const diff = latest.yang_pct - prev.yang_pct
    const recent = [...history].reverse()

    const goldMap = new Map<string, GoldFingerPoint>()
    if (goldFingerHistory) {
        for (const g of goldFingerHistory) goldMap.set(g.trade_date, g)
    }
    const latestGold = goldMap.get(latest.trade_date)

    const bgMap = new Map<string, string>()
    if (redGreenBgHistory) {
        for (const bg of redGreenBgHistory) bgMap.set(bg.trade_date, bg.background)
    }
    const latestBg = bgMap.get(latest.trade_date)

    return (
        <div className="rounded-xl border border-slate-200 bg-white p-3 sm:p-4 dark:border-slate-700/50 dark:bg-slate-900/50">
            <h3 className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2 sm:mb-3 flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-amber-400" />
                大盘点金
                <span className="ml-auto text-[10px] sm:text-xs font-normal text-slate-400">{latest.trade_date}</span>
            </h3>
            <div className="mb-3 sm:mb-4">
                <div className="text-[10px] sm:text-xs text-slate-400 mb-0.5">最新阳谱{latest.updated_at ? ` ${latest.updated_at}` : ''}</div>
                <div className="text-2xl sm:text-3xl font-bold text-red-400 tabular-nums mb-2">{latest.yang_pct.toFixed(1)}%</div>
                <div className="flex flex-wrap items-center gap-2">
                    <span className={`inline-flex items-center gap-0.5 rounded-md px-2 py-0.5 text-xs font-medium ${diff > 0 ? 'bg-red-50 text-red-500 dark:bg-red-950/25 dark:text-red-400' : diff < 0 ? 'bg-green-50 text-green-500 dark:bg-green-950/25 dark:text-green-400' : 'bg-slate-50 text-slate-500 dark:bg-slate-800 dark:text-slate-400'}`}>
                        {diff > 0 ? <TrendingUp className="h-3 w-3" /> : diff < 0 ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                        较前日 {diff > 0 ? '+' : ''}{diff.toFixed(1)}%
                    </span>
                    {latestGold && (
                        <span className={`inline-flex items-center gap-0.5 rounded-md px-2 py-0.5 text-xs font-medium ${latestGold.signal === 1 ? 'bg-amber-50 text-amber-600 dark:bg-amber-950/25 dark:text-amber-400' : 'bg-slate-50 text-slate-500 dark:bg-slate-800 dark:text-slate-400'}`}>
                            {latestGold.signal === 1 ? '🖐️ 金手指' : '👇 银手指'}
                        </span>
                    )}
                    {latestBg && (
                        <span className={`inline-flex items-center gap-0.5 rounded-md px-2 py-0.5 text-xs font-medium ${latestBg === '红' ? 'bg-red-50 text-red-500 dark:bg-red-950/25 dark:text-red-400' : 'bg-green-50 text-green-500 dark:bg-green-950/25 dark:text-green-400'}`}>
                            {latestBg === '红' ? '▲' : '▼'} 趋势{latestBg}
                        </span>
                    )}
                </div>
            </div>
            <div className="overflow-x-auto -mx-3 sm:mx-0">
            <table className="text-xs sm:text-sm border-separate border-spacing-0">
                <thead>
                    <tr className="text-center text-[10px] sm:text-xs text-slate-400">
                        <th className="sticky left-0 z-10 bg-white dark:bg-slate-900/50 pb-2 sm:pb-3 pr-3 sm:pr-4 font-medium text-left">日期</th>
                        {recent.map(r => <th key={r.trade_date} className={`pb-2 sm:pb-3 px-2 sm:px-4 font-medium min-w-[4.5rem] sm:min-w-[5rem] ${getBgClass(bgMap.get(r.trade_date))}`}>{r.trade_date}</th>)}
                    </tr>
                </thead>
                <tbody>
                    <tr className="border-b border-slate-50 dark:border-slate-800/50">
                        <td className="sticky left-0 z-10 bg-white dark:bg-slate-900/50 py-1.5 sm:py-2 pr-3 sm:pr-4 font-medium text-black dark:text-white">阳谱</td>
                        {recent.map(r => <td key={r.trade_date} className={`py-1.5 sm:py-2 px-2 sm:px-4 text-center text-black dark:text-white tabular-nums ${getBgClass(bgMap.get(r.trade_date))}`}>{r.yang_pct.toFixed(1)}%</td>)}
                    </tr>
                    <tr className="border-b border-slate-50 dark:border-slate-800/50">
                        <td className="sticky left-0 z-10 bg-white dark:bg-slate-900/50 py-1.5 sm:py-2 pr-3 sm:pr-4 font-medium text-black dark:text-white">阴谱</td>
                        {recent.map(r => <td key={r.trade_date} className={`py-1.5 sm:py-2 px-2 sm:px-4 text-center text-black dark:text-white tabular-nums ${getBgClass(bgMap.get(r.trade_date))}`}>{r.yin_pct.toFixed(1)}%</td>)}
                    </tr>
                    <tr>
                        <td className="sticky left-0 z-10 bg-white dark:bg-slate-900/50 py-1.5 sm:py-2 pr-3 sm:pr-4 font-medium text-black dark:text-white">金/银</td>
                        {recent.map(r => {
                            const g = goldMap.get(r.trade_date)
                            const bgClass = getBgClass(bgMap.get(r.trade_date))
                            if (!g) return <td key={r.trade_date} className={`py-1.5 sm:py-2 px-2 sm:px-4 text-center text-slate-300 ${bgClass}`}>—</td>
                            return (
                                <td key={r.trade_date} className={`py-1.5 sm:py-2 px-2 sm:px-4 text-center font-medium ${g.signal === 1 ? 'text-amber-400' : 'text-slate-400'} ${bgClass}`}>
                                    {g.signal === 1 ? <span className="text-amber-400">🖐️ 金</span> : <span className="text-slate-400"><span className="grayscale">👇</span> 银</span>}
                                </td>
                            )
                        })}
                    </tr>
                    <tr>
                        <td className="sticky left-0 z-10 bg-white dark:bg-slate-900/50 py-1.5 sm:py-2 pr-3 sm:pr-4 font-medium text-black dark:text-white">趋势</td>
                        {recent.map(r => {
                            const bg = bgMap.get(r.trade_date)
                            if (!bg) return <td key={r.trade_date} className="py-1.5 sm:py-2 px-2 sm:px-4 text-center text-slate-300">—</td>
                            return (
                                <td key={r.trade_date} className={`py-1.5 sm:py-2 px-2 sm:px-4 text-center ${getBgClass(bg)}`}>
                                    {bg === '红' ? <span className="text-red-500">▲</span> : <span className="text-green-500">▼</span>}
                                </td>
                            )
                        })}
                    </tr>
                </tbody>
            </table>
            </div>
        </div>
    )
}
