import { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, TrendingDown, Loader2, AlertTriangle } from 'lucide-react'
import type { BiasAnalysisResponse, BiasProbabilityRow } from '@/types'
import { api } from '@/services/api'

interface Props {
    symbol: string
    name?: string
}

function ProbTable({ rows }: { rows: BiasProbabilityRow[] }) {
    if (!rows.length) return null

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-xs">
                <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-700">
                        <th className="text-left py-1.5 px-1 text-slate-500 font-medium">乖离阈值</th>
                        <th className="text-right py-1.5 px-1 text-slate-500 font-medium">1日</th>
                        <th className="text-right py-1.5 px-1 text-slate-500 font-medium">3日</th>
                        <th className="text-right py-1.5 px-1 text-slate-500 font-medium">5日</th>
                        <th className="text-right py-1.5 px-1 text-slate-500 font-medium">10日</th>
                        <th className="text-right py-1.5 px-1 text-slate-500 font-medium">10日均收益</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row, i) => {
                        const highlight = (v: number) => {
                            if (v >= 65) return 'text-green-600 dark:text-green-400 font-semibold'
                            if (v >= 55) return 'text-slate-700 dark:text-slate-300'
                            return 'text-slate-500 dark:text-slate-500'
                        }
                        return (
                            <tr key={i} className="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30">
                                <td className="py-1.5 px-1 text-slate-600 dark:text-slate-400 font-mono [font-variant-ligatures:none]">{row.threshold_label}</td>
                                <td className={`py-1.5 px-1 text-right ${highlight(row.day_1_pct)}`}>{row.day_1_pct}%</td>
                                <td className={`py-1.5 px-1 text-right ${highlight(row.day_3_pct)}`}>{row.day_3_pct}%</td>
                                <td className={`py-1.5 px-1 text-right ${highlight(row.day_5_pct)}`}>{row.day_5_pct}%</td>
                                <td className={`py-1.5 px-1 text-right ${highlight(row.day_10_pct)}`}>{row.day_10_pct}%</td>
                                <td className={`py-1.5 px-1 text-right font-mono ${row.day_10_avg_ret >= 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                                    {row.day_10_avg_ret >= 0 ? '+' : ''}{row.day_10_avg_ret}%
                                </td>
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}

function DistBar({ label, count, maxCount, total }: { label: string; count: number; maxCount: number; total: number }) {
    const pct = (count / Math.max(total, 1)) * 100
    const barPct = maxCount > 0 ? (count / maxCount) * 100 : 0
    const isNegative = label.startsWith('<')
    return (
        <div className="flex items-center gap-1.5 text-[11px]">
            <span className="w-14 text-right text-slate-500 dark:text-slate-400 flex-shrink-0">{label}</span>
            <div className="flex-1 h-4 bg-slate-100 dark:bg-slate-800 rounded-sm overflow-hidden">
                <div
                    className={`h-full rounded-sm transition-all ${isNegative ? 'bg-green-400 dark:bg-green-600' : 'bg-red-400 dark:bg-red-600'}`}
                    style={{ width: `${Math.max(barPct, 2)}%` }}
                />
            </div>
            <span className="w-8 text-right text-slate-600 dark:text-slate-300 font-mono">{count}</span>
            <span className="w-10 text-right text-slate-400">{pct.toFixed(1)}%</span>
        </div>
    )
}

export default function BiasAnalysisPanel({ symbol, name = '' }: Props) {
    const [data, setData] = useState<BiasAnalysisResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const load = async () => {
        setLoading(true)
        setError(null)
        try {
            const result = await api.getBiasAnalysis(symbol)
            setData(result)
        } catch (e: any) {
            setError(e?.message || '分析失败')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        setData(null)
        setError(null)
    }, [symbol])

    if (!data && !loading && !error) {
        return (
            <div className="card p-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-indigo-500" />
                        <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                            乖离率统计分析
                        </span>
                    </div>
                    <button
                        onClick={load}
                        className="px-3 py-1 text-xs rounded-md bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-500/30 transition-colors"
                    >
                        开始分析
                    </button>
                </div>
            </div>
        )
    }

    if (loading) {
        return (
            <div className="card p-6 flex items-center justify-center gap-3">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />
                <span className="text-sm text-slate-500">正在分析乖离率分布...</span>
            </div>
        )
    }

    if (error) {
        return (
            <div className="card p-4">
                <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm">{error}</span>
                </div>
                <button onClick={load} className="mt-2 px-3 py-1 text-xs rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 hover:bg-slate-200 transition-colors">
                    重试
                </button>
            </div>
        )
    }

    if (!data) return null

    const { stats, distribution, pullback_after_high, rebound_after_low, pullback_summary, rebound_summary } = data
    const maxDist = Math.max(...Object.values(distribution), 1)
    const totalDays = Object.values(distribution).reduce((a, b) => a + b, 0)
    const distEntries = Object.entries(distribution)

    return (
        <div className="card overflow-hidden flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-indigo-500" />
                    <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                        乖离率统计分析
                    </span>
                    <span className="text-[11px] text-slate-400">
                        {name || data.symbol} · {data.total_days}个交易日
                    </span>
                </div>
            </div>

            <div className="p-3 space-y-3">
                {/* Stats Summary */}
                <div className="grid grid-cols-5 gap-2">
                    {[
                        ['均值', `${stats.mean}%`, stats.mean > 0 ? 'text-red-600' : 'text-green-600'],
                        ['中位', `${stats.median}%`, stats.median > 0 ? 'text-red-600' : 'text-green-600'],
                        ['标准差', `${stats.std}%`, 'text-slate-600'],
                        ['最高', `${stats.max_val}%`, 'text-red-600'],
                        ['最低', `${stats.min_val}%`, 'text-green-600'],
                    ].map(([label, value, color]) => (
                        <div key={label as string} className="text-center p-1.5 rounded bg-slate-50 dark:bg-slate-800/50">
                            <div className="text-[10px] text-slate-400">{label}</div>
                            <div className={`text-xs font-mono font-semibold ${color} dark:opacity-90`}>{value}</div>
                        </div>
                    ))}
                </div>

                {/* Distribution */}
                <div>
                    <div className="text-[11px] font-medium text-slate-500 mb-1.5">乖离率分布区间</div>
                    <div className="space-y-0.5">
                        {distEntries.map(([label, count]) => (
                            <DistBar key={label} label={label} count={count} maxCount={maxDist} total={totalDays} />
                        ))}
                    </div>
                </div>

                {/* Pullback after high bias */}
                {pullback_after_high.length > 0 && (
                    <div>
                        <div className="flex items-center gap-1.5 mb-1.5">
                            <TrendingDown className="w-3 h-3 text-orange-500" />
                            <span className="text-[11px] font-medium text-slate-500">正向高位乖离 → N日后回撤概率</span>
                        </div>
                        <ProbTable rows={pullback_after_high} />
                        <div className="mt-1 text-[11px] text-slate-400 leading-relaxed">{pullback_summary}</div>
                    </div>
                )}

                {/* Rebound after low bias */}
                {rebound_after_low.length > 0 && (
                    <div>
                        <div className="flex items-center gap-1.5 mb-1.5">
                            <TrendingUp className="w-3 h-3 text-emerald-500" />
                            <span className="text-[11px] font-medium text-slate-500">负向低位乖离 → N日后反弹概率</span>
                        </div>
                        <ProbTable rows={rebound_after_low} />
                        <div className="mt-1 text-[11px] text-slate-400 leading-relaxed">{rebound_summary}</div>
                    </div>
                )}

                {/* Date range */}
                <div className="text-[10px] text-slate-400 text-right">
                    数据范围: {data.start_date} ~ {data.end_date}
                </div>
            </div>
        </div>
    )
}
