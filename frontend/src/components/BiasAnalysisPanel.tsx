import { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, TrendingDown, Loader2, AlertTriangle, RefreshCw } from 'lucide-react'
import type { BiasAnalysisResponse, BiasProbabilityRow, BiasSnapshotResponse } from '@/types'
import { api } from '@/services/api'
import BiasTimeline from './BiasTimeline'

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

function DistChart({ distribution }: { distribution: Record<string, number> }) {
    const bins = [
        { label: "<-10%", mid: -12.5 },
        { label: "-10~-5%", mid: -7.5 },
        { label: "-5~-3%", mid: -4 },
        { label: "-3~-1%", mid: -2 },
        { label: "-1~0%", mid: -0.5 },
        { label: "0~1%", mid: 0.5 },
        { label: "1~3%", mid: 2 },
        { label: "3~5%", mid: 4 },
        { label: "5~10%", mid: 7.5 },
        { label: ">10%", mid: 12.5 },
    ]

    const data = bins.map(b => ({ ...b, count: distribution[b.label] || 0 }))
    const maxCount = Math.max(...data.map(d => d.count), 1)

    const W = 600, H = 150
    const padL = 24, padR = 12, padT = 10, padB = 24
    const chartW = W - padL - padR
    const chartH = H - padT - padB

    const xMin = -15, xMax = 15
    const xScale = (v: number) => padL + ((v - xMin) / (xMax - xMin)) * chartW
    const yScale = (v: number) => padT + chartH - (v / maxCount) * chartH

    const points = data.map(d => ({ x: xScale(d.mid), y: yScale(d.count) }))

    // Smooth line via 3-point moving average
    const smoothed = points.map((p, i) => {
        const prev = points[Math.max(0, i - 1)]
        const next = points[Math.min(points.length - 1, i + 1)]
        return { x: p.x, y: (prev.y + p.y * 2 + next.y) / 4 }
    })

    // SVG smooth path using quadratic beziers
    let smoothD = `M ${smoothed[0].x} ${smoothed[0].y}`
    for (let i = 1; i < smoothed.length; i++) {
        const cx = (smoothed[i - 1].x + smoothed[i].x) / 2
        const cy = smoothed[i - 1].y
        smoothD += ` Q ${cx} ${cy}, ${smoothed[i].x} ${smoothed[i].y}`
    }

    // Filled area under curve
    const areaD = `${smoothD} L ${smoothed[smoothed.length - 1].x} ${yScale(0)} L ${smoothed[0].x} ${yScale(0)} Z`

    const xTicks = [-10, -5, 0, 5, 10]

    return (
        <div className="w-full">
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img">
                {/* Grid lines */}
                {[0.25, 0.5, 0.75, 1].map(frac => (
                    <line key={frac}
                        x1={padL} y1={yScale(maxCount * frac)}
                        x2={W - padR} y2={yScale(maxCount * frac)}
                        stroke="currentColor" strokeWidth="0.5" opacity="0.1"
                    />
                ))}
                {/* Zero line */}
                <line x1={xScale(0)} y1={padT} x2={xScale(0)} y2={H - padB}
                    stroke="currentColor" strokeWidth="1" opacity="0.2" strokeDasharray="3 3"
                />

                {/* Bars */}
                {data.map((d, i) => {
                    const binHalf = [2.5, 2.5, 1, 1, 0.5, 0.5, 1, 1, 2.5, 2.5][i]
                    const bw = Math.max(((binHalf * 2) / (xMax - xMin)) * chartW * 0.7, 2)
                    const bx = xScale(d.mid) - bw / 2
                    const barTop = yScale(d.count)
                    const barH = Math.max(yScale(0) - barTop, 0)
                    const isNeg = d.mid < 0
                    return (
                        <rect key={d.label}
                            x={bx} y={barTop} width={bw} height={barH}
                            fill={isNeg ? '#34d399' : '#f87171'}
                            className={isNeg ? 'dark:fill-emerald-600' : 'dark:fill-red-600'}
                            rx="1.5" opacity="0.8"
                        >
                            <title>{d.label}: {d.count}天 ({((d.count / data.reduce((s, x) => s + x.count, 0)) * 100).toFixed(1)}%)</title>
                        </rect>
                    )
                })}

                {/* Area fill under curve */}
                <path d={areaD} fill="url(#biasGrad)" opacity="0.2" />

                {/* Smooth density curve */}
                <path d={smoothD} fill="none" stroke="#818cf8" strokeWidth="1.8" opacity="0.8" strokeLinecap="round" strokeLinejoin="round" />

                {/* X-axis ticks */}
                {xTicks.map(t => (
                    <g key={t}>
                        <line x1={xScale(t)} y1={H - padB} x2={xScale(t)} y2={H - padB + 4}
                            stroke="currentColor" opacity="0.3" strokeWidth="0.8" />
                        <text x={xScale(t)} y={H - 4} textAnchor="middle"
                            className="fill-slate-400 dark:fill-slate-500" fontSize="9">
                            {t === 0 ? '0' : `${t}%`}
                        </text>
                    </g>
                ))}

                <defs>
                    <linearGradient id="biasGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#818cf8" stopOpacity="0.5" />
                        <stop offset="100%" stopColor="#818cf8" stopOpacity="0" />
                    </linearGradient>
                </defs>
            </svg>
            <div className="flex items-center justify-center gap-4 text-[10px] text-slate-400 mt-1">
                <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm bg-emerald-400 dark:bg-emerald-600 inline-block" /> 负乖离
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm bg-red-400 dark:bg-red-600 inline-block" /> 正乖离
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-4 h-0.5 bg-indigo-400 inline-block" /> 密度曲线
                </span>
            </div>
        </div>
    )
}

export default function BiasAnalysisPanel({ symbol, name = '' }: Props) {
    const [data, setData] = useState<BiasAnalysisResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [snapshot, setSnapshot] = useState<BiasSnapshotResponse | null>(null)
    const [snapLoading, setSnapLoading] = useState(false)

    const load = async () => {
        setLoading(true)
        setError(null)
        try {
            const result = await api.getBiasAnalysis(symbol)
            setData(result)
            // 自动拉一次盘中快照
            api.getBiasSnapshot(symbol).then(setSnapshot).catch(() => {})
        } catch (e: any) {
            setError(e?.message || '分析失败')
        } finally {
            setLoading(false)
        }
    }

    const refreshSnapshot = async () => {
        setSnapLoading(true)
        try {
            const snap = await api.getBiasSnapshot(symbol)
            setSnapshot(snap)
        } catch {
            // silently ignore snapshot failures
        } finally {
            setSnapLoading(false)
        }
    }

    useEffect(() => {
        setData(null)
        setError(null)
        setSnapshot(null)
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
                        {data.name || name || data.symbol} · {data.total_days}个交易日
                    </span>
                </div>
                <button
                    onClick={load}
                    disabled={loading}
                    className="p-1.5 rounded-md text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-500/20 transition-colors disabled:opacity-50"
                    title="刷新分析"
                >
                    <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                </button>
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

                {/* Real-time Snapshot */}
                <div className="flex items-center gap-2 p-2 rounded bg-indigo-50/50 dark:bg-indigo-500/10 border border-indigo-100 dark:border-indigo-500/20">
                    <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-x-3 gap-y-1">
                        <div className="text-center">
                            <div className="text-[10px] text-slate-400">当前价</div>
                            <div className="text-xs font-mono font-semibold text-slate-700 dark:text-slate-300">
                                {snapshot ? snapshot.price.toFixed(2) : '--'}
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-slate-400">涨跌幅</div>
                            <div className={`text-xs font-mono font-semibold ${snapshot ? (snapshot.change_pct >= 0 ? 'text-red-600' : 'text-green-600') : ''}`}>
                                {snapshot ? `${snapshot.change_pct >= 0 ? '+' : ''}${snapshot.change_pct}%` : '--'}
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-slate-400">MA13乖离</div>
                            <div className={`text-xs font-mono font-semibold ${snapshot ? (snapshot.bias_pct >= 0 ? 'text-red-600' : 'text-green-600') : ''}`}>
                                {snapshot ? `${snapshot.bias_pct >= 0 ? '+' : ''}${snapshot.bias_pct}%` : '--'}
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-slate-400">牛熊乖离</div>
                            <div className={`text-xs font-mono font-semibold ${snapshot?.zj_bias != null ? (snapshot.zj_bias >= 0 ? 'text-amber-600' : 'text-sky-600') : ''}`}>
                                {snapshot?.zj_bias != null ? `${snapshot.zj_bias >= 0 ? '+' : ''}${snapshot.zj_bias}%` : '--'}
                            </div>
                        </div>
                    </div>
                    {snapshot && (
                        <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded ${
                            snapshot.market_phase === 'in_session'
                                ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400'
                                : 'bg-slate-100 dark:bg-slate-700 text-slate-500'
                        }`}>
                            {{ pre_open: '盘前', in_session: '盘中', lunch_break: '午休', post_close: '已收盘', closed: '休市' }[snapshot.market_phase] || snapshot.market_phase}
                        </span>
                    )}
                    <button
                        onClick={refreshSnapshot}
                        disabled={snapLoading}
                        className="shrink-0 px-2 py-1 text-[11px] rounded bg-indigo-100 dark:bg-indigo-500/30 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-200 dark:hover:bg-indigo-500/40 disabled:opacity-50 transition-colors"
                    >
                        {snapLoading ? '刷新中' : '刷新'}
                    </button>
                </div>

                {/* Daily Bias Timeline */}
                {data.points.length > 0 && (
                    <div>
                        <div className="text-[11px] font-medium text-slate-500 mb-1.5">乖离率时序走势</div>
                        <BiasTimeline points={data.points} snapshot={snapshot} />
                    </div>
                )}

                {/* Distribution Chart */}
                <div>
                    <div className="text-[11px] font-medium text-slate-500 mb-1.5">乖离率分布区间</div>
                    <DistChart distribution={distribution} />
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
