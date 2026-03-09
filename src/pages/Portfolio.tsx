import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Briefcase, Plus, Trash2, TrendingUp, Activity, Flame, RefreshCw, TrendingDown } from 'lucide-react'
import { api } from '@/services/api'
import type { Report, HotStock } from '@/types'

interface Holding {
    symbol: string
    notes: string
    addedAt: string
}

const STORAGE_KEY = 'ta-portfolio'

function loadHoldings(): Holding[] {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as Holding[]
    } catch {
        return []
    }
}

function saveHoldings(holdings: Holding[]) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(holdings))
}

const parseDecisionColor = (decision?: string) => {
    if (!decision) return 'text-slate-400'
    const d = decision.toUpperCase()
    if (d.includes('BUY') || d.includes('增持') || d.includes('买入')) return 'text-green-500'
    if (d.includes('SELL') || d.includes('减持') || d.includes('卖出')) return 'text-red-500'
    return 'text-slate-500 dark:text-slate-400'
}

const parseDecisionLabel = (decision?: string) => {
    if (!decision) return '暂无'
    const d = decision.toUpperCase()
    if (d.includes('BUY') || d.includes('增持') || d.includes('买入')) return '增持'
    if (d.includes('SELL') || d.includes('减持') || d.includes('卖出')) return '减持'
    return '持有'
}

export default function Portfolio() {
    const [holdings, setHoldings] = useState<Holding[]>(loadHoldings)
    const [newSymbol, setNewSymbol] = useState('')
    const [newNotes, setNewNotes] = useState('')
    const [latestReports, setLatestReports] = useState<Record<string, Report>>({})
    const [hotStocks, setHotStocks] = useState<HotStock[]>([])
    const [hotLoading, setHotLoading] = useState(false)
    const [hotSource, setHotSource] = useState<'em' | 'xq' | 'ths'>('em')
    const navigate = useNavigate()

    useEffect(() => {
        holdings.forEach(h => {
            api.getReports(h.symbol, 0, 1).then(res => {
                if (res.reports.length > 0) {
                    setLatestReports(prev => ({ ...prev, [h.symbol]: res.reports[0] }))
                }
            }).catch(() => {})
        })
    }, [holdings])

    const fetchHotStocks = (source = hotSource) => {
        setHotLoading(true)
        api.getHotStocks(30, source)
            .then(res => setHotStocks(res.stocks))
            .catch(() => {})
            .finally(() => setHotLoading(false))
    }

    useEffect(() => { fetchHotStocks(hotSource) }, [hotSource])

    const addHolding = (symbol?: string, notes?: string) => {
        const sym = (symbol ?? newSymbol).trim().toUpperCase()
        if (!sym || holdings.some(h => h.symbol === sym)) return
        const updated = [...holdings, { symbol: sym, notes: (notes ?? newNotes).trim(), addedAt: new Date().toISOString() }]
        setHoldings(updated)
        saveHoldings(updated)
        if (!symbol) { setNewSymbol(''); setNewNotes('') }
    }

    const removeHolding = (symbol: string) => {
        const updated = holdings.filter(h => h.symbol !== symbol)
        setHoldings(updated)
        saveHoldings(updated)
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">自选股 &amp; 热榜选股</h1>
                <p className="text-slate-500 dark:text-slate-400 mt-1">管理关注标的，从热榜快速发起分析</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Left: Watchlist */}
                <div className="space-y-4">
                    {/* Add stock */}
                    <div className="card space-y-3">
                        <div className="flex items-center gap-2">
                            <Plus className="w-5 h-5 text-blue-500" />
                            <h2 className="font-semibold text-slate-900 dark:text-slate-100">添加自选</h2>
                        </div>
                        <div className="flex gap-2">
                            <input
                                value={newSymbol}
                                onChange={e => setNewSymbol(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && addHolding()}
                                placeholder="代码，如 600519.SH"
                                className="input flex-1"
                                maxLength={20}
                            />
                            <input
                                value={newNotes}
                                onChange={e => setNewNotes(e.target.value)}
                                placeholder="备注"
                                className="input flex-1"
                                maxLength={100}
                            />
                            <button onClick={() => addHolding()} className="btn-primary px-4">
                                <Plus className="w-4 h-4" />
                            </button>
                        </div>
                    </div>

                    {/* Holdings list */}
                    <div className="card">
                        <div className="flex items-center gap-2 mb-4">
                            <Briefcase className="w-5 h-5 text-purple-500" />
                            <h2 className="font-semibold text-slate-900 dark:text-slate-100">自选列表 ({holdings.length})</h2>
                        </div>

                        {holdings.length === 0 ? (
                            <div className="text-center py-10">
                                <Briefcase className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                                <p className="text-slate-500 dark:text-slate-400">还没有关注的股票</p>
                                <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">从热榜添加或手动输入代码</p>
                            </div>
                        ) : (
                            <div className="divide-y divide-slate-100 dark:divide-slate-700">
                                {holdings.map(h => {
                                    const report = latestReports[h.symbol]
                                    return (
                                        <div key={h.symbol} className="flex items-center gap-3 py-3">
                                            <div className="w-9 h-9 rounded-lg bg-blue-100 dark:bg-blue-500/10 flex items-center justify-center shrink-0">
                                                <TrendingUp className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="font-medium text-slate-900 dark:text-slate-100 text-sm">{h.symbol}</p>
                                                {h.notes && <p className="text-xs text-slate-400 truncate">{h.notes}</p>}
                                                {report && (
                                                    <p className="text-xs text-slate-400 mt-0.5">
                                                        {report.trade_date}
                                                        {report.confidence != null && ` · ${report.confidence}%`}
                                                    </p>
                                                )}
                                            </div>
                                            {report && (
                                                <span className={`text-xs font-medium ${parseDecisionColor(report.decision)}`}>
                                                    {parseDecisionLabel(report.decision)}
                                                </span>
                                            )}
                                            <button
                                                onClick={() => navigate(`/analysis?symbol=${h.symbol}`)}
                                                className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-500/20 transition-colors"
                                            >
                                                <Activity className="w-3 h-3" />
                                                分析
                                            </button>
                                            <button
                                                onClick={() => removeHolding(h.symbol)}
                                                className="p-1.5 text-slate-400 hover:text-red-500 transition-colors"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    )
                                })}
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: Hot stocks */}
                <div className="card">
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                            <Flame className="w-5 h-5 text-orange-500" />
                            <h2 className="font-semibold text-slate-900 dark:text-slate-100">热榜选股</h2>
                        </div>
                        <button
                            onClick={() => fetchHotStocks()}
                            disabled={hotLoading}
                            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors disabled:opacity-40"
                        >
                            <RefreshCw className={`w-4 h-4 ${hotLoading ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                    <div className="flex gap-1 mb-3">
                        {(['em', 'xq', 'ths'] as const).map(src => (
                            <button
                                key={src}
                                onClick={() => setHotSource(src)}
                                className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${hotSource === src
                                    ? 'bg-orange-500 border-orange-500 text-white'
                                    : 'border-slate-300 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-orange-400'
                                }`}
                            >
                                {src === 'em' ? '东财热榜' : src === 'xq' ? '雪球热门' : '连涨榜'}
                            </button>
                        ))}
                    </div>

                    {hotStocks.length === 0 ? (
                        <div className="text-center py-10">
                            <Flame className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                            <p className="text-slate-500 dark:text-slate-400">{hotLoading ? '加载中...' : '暂无数据'}</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-slate-100 dark:divide-slate-700 max-h-[500px] overflow-y-auto">
                            {hotStocks.map(stock => (
                                <div key={stock.symbol} className="flex items-center gap-3 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/30 -mx-4 px-4 transition-colors">
                                    <span className="text-xs text-slate-400 w-5 text-right shrink-0">{stock.rank}</span>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="font-medium text-sm text-slate-900 dark:text-slate-100">{stock.name}</span>
                                            <span className="text-xs text-slate-400">{stock.symbol}</span>
                                        </div>
                                        <div className="flex items-center gap-3 mt-0.5">
                                            <span className="text-sm text-slate-700 dark:text-slate-300">¥{stock.price.toFixed(2)}</span>
                                            {stock.change_pct !== 0 && (
                                                <span className={`text-xs font-medium flex items-center gap-0.5 ${stock.change_pct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                                    {stock.change_pct >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                                    {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                                                </span>
                                            )}
                                            {stock.extra && (
                                                <span className="text-xs text-slate-500 dark:text-slate-400">
                                                    {stock.extra}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-1">
                                        {!holdings.some(h => h.symbol === stock.symbol) && (
                                            <button
                                                onClick={() => addHolding(stock.symbol, stock.name)}
                                                className="p-1.5 text-slate-400 hover:text-blue-500 transition-colors"
                                                title="加入自选"
                                            >
                                                <Plus className="w-4 h-4" />
                                            </button>
                                        )}
                                        <button
                                            onClick={() => navigate(`/analysis?symbol=${stock.symbol}`)}
                                            className="flex items-center gap-1 px-2 py-1 text-xs rounded-lg bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-500/20 transition-colors"
                                        >
                                            <Activity className="w-3 h-3" />
                                            分析
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
