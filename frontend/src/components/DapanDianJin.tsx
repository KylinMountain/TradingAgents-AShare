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
            </h3>
            <div className="flex items-center gap-3 sm:gap-4 mb-3 sm:mb-4">
                <div>
                    <div className="text-[10px] sm:text-xs text-slate-400">最新阳谱{latest.updated_at ? ` ${latest.updated_at}` : ''}</div>
                    <div className="text-xl sm:text-2xl font-bold text-red-400 tabular-nums">{latest.yang_pct.toFixed(1)}%</div>
                </div>
                <div className="flex items-center gap-1">
                    {diff > 0 ? <TrendingUp className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-red-400" /> : diff < 0 ? <TrendingDown className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-green-400" /> : <Minus className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-slate-400" />}
                    <span className={`text-xs sm:text-sm tabular-nums ${diff > 0 ? 'text-red-400' : diff < 0 ? 'text-green-400' : 'text-slate-400'}`}>
                        较前日 {diff > 0 ? '+' : ''}{diff.toFixed(1)}%
                    </span>
                    {latestGold && (
                        <span className={`ml-2 text-xs sm:text-sm font-medium ${latestGold.signal === 1 ? 'text-amber-400' : 'text-slate-400'}`}>
                            {latestGold.signal === 1 ? <span className="text-amber-400">🖐️ 金</span> : <span className="text-slate-400"><span className="grayscale">👇</span> 银</span>}
                        </span>
                    )}
                    {latestBg && (
                        <span className={`ml-1 text-xs sm:text-sm font-medium ${latestBg === '红' ? 'text-red-500' : 'text-green-500'}`}>
                            {latestBg === '红' ? '▲' : '▼'}
                        </span>
                    )}
                </div>
            </div>
            <div className="overflow-x-auto -mx-3 sm:mx-0">
            <table className="text-xs sm:text-sm border-separate border-spacing-0">
                <thead>
                    <tr className="text-center text-[10px] sm:text-xs text-slate-400">
                        <th className="sticky left-0 z-10 bg-white dark:bg-slate-900/50 pb-2 sm:pb-3 pr-3 sm:pr-4 font-medium text-left">日期</th>
                        {recent.map(r => <th key={r.trade_date} className="pb-2 sm:pb-3 px-2 sm:px-4 font-medium min-w-[4.5rem] sm:min-w-[5rem]">{r.trade_date}</th>)}
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
