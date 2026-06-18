import { useCallback, useRef, useState } from 'react'
import type { BiasPoint, BiasSnapshotResponse } from '@/types'

export default function BiasTimeline({ points, snapshot }: { points: BiasPoint[]; snapshot?: BiasSnapshotResponse | null }) {
    if (!points.length) return null

    const svgRef = useRef<SVGSVGElement>(null)
    const [hoverIdx, setHoverIdx] = useState<number | null>(null)

    const W = 600, H = 180
    const padL = 44, padR = 12, padT = 8, padB = 26
    const chartW = W - padL - padR
    const chartH = H - padT - padB

    // Y range from historical data only (snapshot excluded to avoid re-render instability)
    const maBiases = points.map(p => p.bias_pct)
    const zjBiases = points.filter(p => p.zj_bias != null).map(p => p.zj_bias!)
    const allBiases = maBiases.concat(zjBiases)
    const yMin = Math.min(-1, Math.floor(Math.min(...allBiases) - 1))
    const yMax = Math.max(1, Math.ceil(Math.max(...allBiases) + 1))
    const yRange = yMax - yMin

    const xScale = useCallback((i: number) => padL + (i / Math.max(points.length - 1, 1)) * chartW, [points.length])
    const yScale = useCallback((v: number) => padT + chartH - ((v - yMin) / yRange) * chartH, [yMin, yRange])

    // MA13 bias line
    const maLineD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(p.bias_pct)}`).join(' ')

    // Niuxiong bias line (skip nulls, use moveto on gaps)
    const zjSegments: string[] = []
    let zjActive = false
    for (let i = 0; i < points.length; i++) {
        if (points[i].zj_bias != null) {
            const cmd = zjActive ? 'L' : 'M'
            zjSegments.push(`${cmd} ${xScale(i)} ${yScale(points[i].zj_bias!)}`)
            zjActive = true
        } else {
            zjActive = false
        }
    }
    const zjLineD = zjSegments.join(' ')

    // MA13 area fills
    const zeroY = yScale(0)
    let aboveD = `M ${xScale(0)} ${zeroY}`
    let belowD = `M ${xScale(0)} ${zeroY}`
    for (let i = 0; i < points.length; i++) {
        const x = xScale(i)
        const y = yScale(points[i].bias_pct)
        if (points[i].bias_pct >= 0) {
            aboveD += ` L ${x} ${y}`
            belowD += ` L ${x} ${zeroY}`
        } else {
            aboveD += ` L ${x} ${zeroY}`
            belowD += ` L ${x} ${y}`
        }
    }
    const lastX = xScale(points.length - 1)
    aboveD += ` L ${lastX} ${zeroY} Z`
    belowD += ` L ${lastX} ${zeroY} Z`

    // Y-axis ticks
    const yTickStep = yRange <= 5 ? 1 : yRange <= 10 ? 2 : yRange <= 20 ? 5 : 10
    const yTicks: number[] = []
    for (let v = Math.ceil(yMin / yTickStep) * yTickStep; v <= yMax; v += yTickStep) yTicks.push(v)

    // X-axis date labels (show ~5)
    const xLabelCount = 5
    const xStep = Math.max(1, Math.floor(points.length / (xLabelCount - 1)))
    const xLabels: { i: number; date: string }[] = []
    for (let i = 0; i < points.length; i += xStep) {
        xLabels.push({ i, date: points[i].date.slice(5) }) // MM-DD
    }
    if (xLabels.length === 0 || xLabels[xLabels.length - 1].i !== points.length - 1) {
        xLabels.push({ i: points.length - 1, date: points[points.length - 1].date.slice(5) })
    }

    const handleMouseMove = (e: React.MouseEvent<SVGRectElement>) => {
        const svg = svgRef.current
        if (!svg) return
        const rect = svg.getBoundingClientRect()
        const scaleX = W / rect.width
        const mx = (e.clientX - rect.left) * scaleX
        if (mx < padL || mx > W - padR) { setHoverIdx(null); return }
        const idx = Math.round(((mx - padL) / chartW) * (points.length - 1))
        setHoverIdx(Math.max(0, Math.min(idx, points.length - 1)))
    }

    const handleMouseLeave = () => setHoverIdx(null)

    const hovered = hoverIdx !== null ? points[hoverIdx] : null
    const hx = hoverIdx !== null ? xScale(hoverIdx) : 0
    const hy = hovered ? yScale(hovered.bias_pct) : 0

    // Tooltip sizing: wider to show both bias values
    const hasZj = hovered && hovered.zj_bias != null
    const tooltipW = 160, tooltipH = hasZj ? 46 : 32
    const tooltipX = Math.max(padL, Math.min(W - padR - tooltipW, hx - tooltipW / 2))
    const tooltipY = Math.max(padT, hy - tooltipH - 6)

    return (
        <div className="w-full">
            <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img">
                {/* Horizontal grid lines */}
                {yTicks.map(v => (
                    <line key={v}
                        x1={padL} y1={yScale(v)} x2={W - padR} y2={yScale(v)}
                        stroke="currentColor" strokeWidth="0.5" opacity="0.08"
                    />
                ))}

                {/* Zero line */}
                <line x1={padL} y1={zeroY} x2={W - padR} y2={zeroY}
                    stroke="currentColor" strokeWidth="1" opacity="0.2"
                />

                {/* MA13 area fills */}
                <path d={aboveD} fill="#f87171" opacity="0.12" />
                <path d={belowD} fill="#34d399" opacity="0.12" />

                {/* MA13 bias line */}
                <path d={maLineD} fill="none" stroke="#818cf8" strokeWidth="1.5" opacity="0.85"
                    strokeLinecap="round" strokeLinejoin="round" />

                {/* Niuxiong bias line */}
                {zjLineD && (
                    <path d={zjLineD} fill="none" stroke="#f59e0b" strokeWidth="1.5" opacity="0.85"
                        strokeLinecap="round" strokeLinejoin="round" />
                )}

                {/* Real-time snapshot dots (only during market session) */}
                {snapshot && snapshot.market_phase === 'in_session' && (
                    <>
                        <circle cx={lastX} cy={yScale(snapshot.bias_pct)} r="4"
                            fill="#6366f1" stroke="white" strokeWidth="2" />
                        {snapshot.zj_bias != null && (
                            <circle cx={lastX} cy={yScale(snapshot.zj_bias)} r="4"
                                fill="#f59e0b" stroke="white" strokeWidth="2" />
                        )}
                    </>
                )}

                {/* Hover crosshair */}
                {hovered && (
                    <>
                        <line x1={hx} y1={padT} x2={hx} y2={H - padB}
                            stroke="currentColor" strokeWidth="0.8" opacity="0.2" strokeDasharray="3 2" />
                        <circle cx={hx} cy={hy} r="3"
                            fill="#818cf8" stroke="white" strokeWidth="1.5" />
                        {hovered.zj_bias != null && (
                            <circle cx={hx} cy={yScale(hovered.zj_bias)} r="3"
                                fill="#f59e0b" stroke="white" strokeWidth="1.5" />
                        )}
                        {/* Tooltip box */}
                        <rect x={tooltipX} y={tooltipY} width={tooltipW} height={tooltipH} rx="3"
                            fill="white" className="dark:fill-slate-800" opacity="0.95"
                            stroke="currentColor" strokeWidth="0.6" />
                        <text x={tooltipX + 6} y={tooltipY + 13}
                            className="fill-slate-500 dark:fill-slate-400" fontSize="9">
                            {hovered.date}
                        </text>
                        <text x={tooltipX + 6} y={tooltipY + 25}
                            className="fill-indigo-500 dark:fill-indigo-400"
                            fontSize="10" fontWeight="bold">
                            MA13: {hovered.bias_pct >= 0 ? '+' : ''}{hovered.bias_pct}%
                        </text>
                        {hovered.zj_bias != null && (
                            <text x={tooltipX + 6} y={tooltipY + 39}
                                className="fill-amber-500 dark:fill-amber-400"
                                fontSize="10" fontWeight="bold">
                                牛熊: {hovered.zj_bias >= 0 ? '+' : ''}{hovered.zj_bias}%
                            </text>
                        )}
                    </>
                )}

                {/* X-axis ticks & labels */}
                {xLabels.map(({ i, date }) => (
                    <g key={i}>
                        <line x1={xScale(i)} y1={H - padB} x2={xScale(i)} y2={H - padB + 4}
                            stroke="currentColor" opacity="0.25" strokeWidth="0.8" />
                        <text x={xScale(i)} y={H - 6} textAnchor="middle"
                            className="fill-slate-400 dark:fill-slate-500" fontSize="8.5">
                            {date}
                        </text>
                    </g>
                ))}

                {/* Y-axis ticks & labels */}
                {yTicks.map(v => (
                    <g key={v}>
                        <line x1={padL - 3} y1={yScale(v)} x2={padL} y2={yScale(v)}
                            stroke="currentColor" opacity="0.2" strokeWidth="0.8" />
                        <text x={padL - 5} y={yScale(v) + 3} textAnchor="end"
                            className="fill-slate-400 dark:fill-slate-500" fontSize="9">
                            {v}%
                        </text>
                    </g>
                ))}

                {/* Title */}
                <text x={W - padR} y={padT + 2} textAnchor="end"
                    className="fill-slate-300 dark:fill-slate-600" fontSize="8">
                    乖离率对比 · MA13 vs 牛熊线
                </text>

                {/* Invisible overlay for mouse tracking */}
                <rect x={padL} y={padT} width={chartW} height={chartH}
                    fill="transparent" style={{ cursor: 'crosshair' }}
                    onMouseMove={handleMouseMove}
                    onMouseLeave={handleMouseLeave}
                />
            </svg>
            <div className="flex items-center justify-center gap-4 text-[10px] text-slate-400 mt-1">
                <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm bg-red-400/40 border border-red-400 inline-block" /> 正乖离区
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm bg-emerald-400/40 border border-emerald-400 inline-block" /> 负乖离区
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-4 h-0.5 bg-indigo-400 inline-block" /> MA13乖离
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-4 h-0.5 bg-amber-400 inline-block" /> 牛熊乖离
                </span>
            </div>
        </div>
    )
}
