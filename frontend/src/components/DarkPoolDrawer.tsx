import { useCallback, useEffect, useState } from 'react'
import { X, Loader2, TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react'
import { api } from '@/services/api'
import type { DarkPoolAnalysisResponse } from '@/types'

interface DarkPoolDrawerProps {
    symbol: string
    stockName?: string | null
    open: boolean
    onClose: () => void
}

export default function DarkPoolDrawer({ symbol, stockName, open, onClose }: DarkPoolDrawerProps) {
    const [data, setData] = useState<DarkPoolAnalysisResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchData = useCallback(async () => {
        if (!symbol || !open) return
        setLoading(true)
        setError(null)
        try {
            const resp = await api.getDarkPoolAnalysis(symbol)
            setData(resp)
        } catch (e: any) {
            setError(e?.message || '加载失败')
        } finally {
            setLoading(false)
        }
    }, [symbol, open])

    useEffect(() => {
        if (open) fetchData()
    }, [open, fetchData])

    useEffect(() => {
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
        if (open) { document.addEventListener('keydown', handler); return () => document.removeEventListener('keydown', handler) }
    }, [open, onClose])

    if (!open) return null

    const isEmpty = !data && !loading && !error

    return (
        <>
            <div className="fixed inset-0 bg-black/40 z-40 animate-in fade-in duration-200" onClick={onClose} />
            <div className="fixed top-0 right-0 h-full w-[520px] max-w-[90vw] dark bg-slate-900 border-l border-slate-700 shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-300">
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 shrink-0">
                    <div className="flex items-center gap-3 min-w-0">
                        <span className="text-lg">🔍</span>
                        <h2 className="text-lg font-bold text-white truncate">
                            {stockName ? `${stockName}（${symbol}）` : (data?.symbol || symbol)} 盘面分析
                        </h2>
                        {data?.date && (
                            <span className="text-xs text-slate-400">{data.date}</span>
                        )}
                    </div>
                    <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
                    {loading && (
                        <div className="flex items-center justify-center py-20 text-slate-400">
                            <Loader2 className="w-6 h-6 animate-spin mr-2" />
                            加载分析数据...
                        </div>
                    )}

                    {error && (
                        <div className="flex items-center gap-2 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400">
                            <AlertCircle className="w-5 h-5 shrink-0" />
                            <span className="text-sm">{error}</span>
                        </div>
                    )}

                    {isEmpty && !loading && (
                        <div className="py-20 text-center text-slate-500 text-sm">暂无数据</div>
                    )}

                    {data && !loading && (
                        <>
                            {/* 行情概览 */}
                            {data.market && (
                                <Section title="行情概览">
                                    <div className="grid grid-cols-4 gap-2 text-sm">
                                        <KV label="开盘" value={data.market.open.toFixed(2)} />
                                        <KV label="最高" value={data.market.high.toFixed(2)} cls="text-red-400" />
                                        <KV label="最低" value={data.market.low.toFixed(2)} cls="text-emerald-400" />
                                        <KV label="收盘" value={data.market.close.toFixed(2)} />
                                        <KV label="涨跌" value={`${data.market.chg_pct > 0 ? '+' : ''}${data.market.chg_pct}%`}
                                            cls={data.market.chg_pct > 0 ? 'text-red-400' : 'text-emerald-400'} />
                                        <KV label="成交" value={`${(data.market.total_amt_wan / 10000).toFixed(2)}亿`} />
                                        <KV label="手数" value={`${data.market.total_vol}手`} />
                                        <KV label="笔数" value={`${data.market.tick_count}`} />
                                    </div>
                                </Section>
                            )}

                            {/* 维度一 */}
                            {data.dim1_institutional && (
                                <Section title="维度一 · 机构参与度">
                                    <div className="grid grid-cols-2 gap-2 text-sm">
                                        <KV label="机构参与占比" value={`${data.dim1_institutional.inst_participation_pct}%`} />
                                        <KV label="机构净主动" value={`${data.dim1_institutional.inst_net_wan > 0 ? '+' : ''}${data.dim1_institutional.inst_net_wan}万`}
                                            cls={data.dim1_institutional.inst_net_wan > 0 ? 'text-red-400' : 'text-emerald-400'} />
                                        <KV label="散户净主动" value={`${data.dim1_institutional.retail_net_wan > 0 ? '+' : ''}${data.dim1_institutional.retail_net_wan}万`} />
                                        <KV label="逐笔净主动" value={`${data.dim1_institutional.tick_net_wan > 0 ? '+' : ''}${data.dim1_institutional.tick_net_wan}万`} />
                                        <KV label="大单主动买" value={`${data.dim1_institutional.big_active_buy_wan}万`} cls="text-red-400" />
                                        <KV label="大单主动卖" value={`${data.dim1_institutional.big_active_sell_wan}万`} cls="text-emerald-400" />
                                    </div>
                                    <IntentBadge intent={data.dim1_institutional.intent} />
                                </Section>
                            )}

                            {/* 维度二 */}
                            {data.dim2_tail && (
                                <Section title="维度二 · 尾盘异动">
                                    <div className="grid grid-cols-3 gap-2 text-sm">
                                        <KV label="尾盘量占比" value={`${data.dim2_tail.tail_vol_ratio_pct}%`} />
                                        <KV label="尾盘涨跌" value={`${data.dim2_tail.tail_chg_pct > 0 ? '+' : ''}${data.dim2_tail.tail_chg_pct}%`}
                                            cls={data.dim2_tail.tail_chg_pct > 0 ? 'text-red-400' : 'text-emerald-400'} />
                                        <KV label="全日涨跌" value={`${data.dim2_tail.full_chg_pct > 0 ? '+' : ''}${data.dim2_tail.full_chg_pct}%`}
                                            cls={data.dim2_tail.full_chg_pct > 0 ? 'text-red-400' : 'text-emerald-400'} />
                                    </div>
                                    <SignalBadge signal={data.dim2_tail.signal} />
                                </Section>
                            )}

                            {/* 维度三 */}
                            {data.dim3_split && (
                                <Section title="维度三 · 拆单检测 v4">
                                    <div className="grid grid-cols-2 gap-2 text-sm mb-3">
                                        <KV label="暗盘事件" value={`${data.dim3_split.high_conf_count}个`} cls="text-purple-400 font-semibold" />
                                        <KV label="疑似事件" value={`${data.dim3_split.suspected_count}个`} />
                                        <KV label="拆单总量" value={`${data.dim3_split.split_vol}手`} />
                                        <KV label="占比" value={`${data.dim3_split.split_vol_pct}%`} />
                                        <KV label="主动买" value={`${data.dim3_split.active_buy_vol}手`} cls="text-red-400" />
                                        <KV label="主动卖" value={`${data.dim3_split.active_sell_vol}手`} cls="text-emerald-400" />
                                    </div>
                                    <DirectionBadge direction={data.dim3_split.direction} />

                                    {/* 事件列表 */}
                                    {data.dim3_split.events.length > 0 && (
                                        <div className="mt-3 space-y-2">
                                            <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider">事件明细</h4>
                                            {data.dim3_split.events.map((ev, i) => (
                                                <div key={i} className={`rounded-lg p-3 text-xs border ${ev.level === '暗盘' ? 'bg-purple-500/10 border-purple-500/30' :
                                                        ev.level === '疑似' ? 'bg-amber-500/10 border-amber-500/30' : 'bg-slate-800 border-slate-700'
                                                    }`}>
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="text-slate-300">{ev.start} ~ {ev.end}</span>
                                                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${ev.level === '暗盘' ? 'bg-purple-500/20 text-purple-400' :
                                                                ev.level === '疑似' ? 'bg-amber-500/20 text-amber-400' : 'bg-slate-700 text-slate-400'
                                                            }`}>{ev.level}</span>
                                                    </div>
                                                    <div className="flex items-center gap-3 text-slate-400">
                                                        <span>{ev.duration_min}min</span>
                                                        <span className={ev.direction === '买' ? 'text-red-400' : 'text-emerald-400'}>{ev.direction}方</span>
                                                        <span>{ev.volume}手</span>
                                                        <span className="text-slate-500">基{ev.base_score}分 质{ev.quality_score}分</span>
                                                    </div>
                                                    <div className="mt-1 text-slate-500">{ev.indicators}</div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </Section>
                            )}

                            {/* 综合判断 */}
                            {data.composite && (
                                <Section title="综合判断">
                                    {/* 关键数据 */}
                                    {data.composite.key_facts && data.composite.key_facts.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5 mb-3">
                                            {data.composite.key_facts.map((f, i) => (
                                                <span key={i} className="px-2 py-0.5 rounded text-xs bg-slate-700/50 text-slate-300">{f}</span>
                                            ))}
                                        </div>
                                    )}

                                    {/* 主力意图 */}
                                    {data.composite.intent && (
                                        <div className={`p-3 rounded-lg mb-3 text-sm leading-relaxed ${
                                            data.composite.verdict.includes('偏多') ? 'bg-red-500/10 border border-red-500/20 text-red-300' :
                                            data.composite.verdict.includes('偏空') ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300' :
                                            'bg-slate-700/30 border border-slate-600/30 text-slate-300'
                                        }`}>
                                            <div className="text-xs text-slate-400 mb-1">主力意图</div>
                                            {data.composite.intent}
                                        </div>
                                    )}

                                    {/* 预测 */}
                                    {data.composite.prediction && (
                                        <div className="p-3 rounded-lg mb-3 bg-purple-500/10 border border-purple-500/20 text-purple-300 text-sm leading-relaxed">
                                            <div className="text-xs text-slate-400 mb-1">短期预测</div>
                                            {data.composite.prediction}
                                        </div>
                                    )}

                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="text-xs text-slate-400">信号:</span>
                                        <div className="flex flex-wrap gap-1">
                                            {data.composite.signals.map((s, i) => (
                                                <span key={i} className="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-300">{s}</span>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-xs text-slate-400">置信分:</span>
                                        <span className={`text-lg font-bold ${data.composite.confidence >= 3 ? 'text-red-400' :
                                                data.composite.confidence <= -3 ? 'text-emerald-400' : 'text-slate-300'
                                            }`}>{data.composite.confidence > 0 ? '+' : ''}{data.composite.confidence}</span>
                                        <VerdictBadge verdict={data.composite.verdict} />
                                    </div>
                                </Section>
                            )}
                        </>
                    )}
                </div>
            </div>
        </>
    )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700/50 p-4">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">{title}</h3>
            {children}
        </div>
    )
}

function KV({ label, value, cls = '' }: { label: string; value: string; cls?: string }) {
    return (
        <div className="flex flex-col">
            <span className="text-xs text-slate-500">{label}</span>
            <span className={`text-sm ${cls || 'text-slate-200'}`}>{value}</span>
        </div>
    )
}

function IntentBadge({ intent }: { intent: string }) {
    const isBull = intent.includes('偏多')
    const isBear = intent.includes('偏空')
    return (
        <div className={`mt-2 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${isBull ? 'bg-red-500/15 text-red-400 border border-red-500/30' :
                isBear ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' :
                    'bg-slate-700 text-slate-300 border border-slate-600'
            }`}>
            {isBull ? <TrendingUp className="w-3 h-3" /> : isBear ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
            {intent}
        </div>
    )
}

function SignalBadge({ signal }: { signal: string }) {
    const cls = signal.includes('买入') ? 'bg-red-500/15 text-red-400 border-red-500/30'
        : signal.includes('卖出') ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
            : 'bg-slate-700 text-slate-300 border-slate-600'
    return (
        <div className={`mt-2 inline-flex px-3 py-1 rounded-full text-xs font-medium border ${cls}`}>
            {signal}
        </div>
    )
}

function DirectionBadge({ direction }: { direction: string }) {
    const isBuy = direction.includes('买')
    const isSell = direction.includes('卖')
    return (
        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${isBuy && !isSell ? 'bg-red-500/15 text-red-400 border-red-500/30' :
                isSell && !isBuy ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' :
                    'bg-slate-700 text-slate-300 border-slate-600'
            }`}>
            {isBuy && !isSell ? <TrendingUp className="w-3 h-3" /> : isSell && !isBuy ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
            {direction}
        </div>
    )
}

function VerdictBadge({ verdict }: { verdict: string }) {
    const isBull = verdict.includes('偏多')
    const isBear = verdict.includes('偏空')
    return (
        <span className={`px-3 py-1 rounded-full text-sm font-bold ${isBull ? 'bg-red-500/20 text-red-400' :
                isBear ? 'bg-emerald-500/20 text-emerald-400' :
                    'bg-slate-700 text-slate-300'
            }`}>{verdict}</span>
    )
}
