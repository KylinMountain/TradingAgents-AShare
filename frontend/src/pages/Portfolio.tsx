import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Briefcase, Plus, Trash2, TrendingUp, Activity, Search,
    Clock, AlertTriangle, CheckCircle2, XCircle, Loader2, Timer,
} from 'lucide-react'
import { api } from '@/services/api'
import type { WatchlistItem, ScheduledAnalysis, StockSearchResult, Report } from '@/types'

const HORIZON_LABELS: Record<string, string> = { short: '短线', medium: '中线' }

export default function Portfolio() {
    const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
    const [scheduled, setScheduled] = useState<ScheduledAnalysis[]>([])
    const [latestReports, setLatestReports] = useState<Record<string, Report>>({})
    const [loading, setLoading] = useState(true)

    // Search state
    const [searchQuery, setSearchQuery] = useState('')
    const [searchResults, setSearchResults] = useState<StockSearchResult[]>([])
    const [searchLoading, setSearchLoading] = useState(false)
    const [showDropdown, setShowDropdown] = useState(false)
    const searchTimerRef = useRef<ReturnType<typeof setTimeout>>()
    const dropdownRef = useRef<HTMLDivElement>(null)

    const navigate = useNavigate()

    const fetchAll = async () => {
        setLoading(true)
        try {
            const [wRes, sRes] = await Promise.all([
                api.getWatchlist(),
                api.getScheduled(),
            ])
            setWatchlist(wRes.items)
            setScheduled(sRes.items)

            // Fetch latest report for each watchlist symbol
            const reportMap: Record<string, Report> = {}
            await Promise.all(
                wRes.items.map(async (item) => {
                    try {
                        const res = await api.getReports(item.symbol, 0, 1)
                        if (res.reports.length > 0) reportMap[item.symbol] = res.reports[0]
                    } catch {}
                })
            )
            setLatestReports(reportMap)
        } catch {}
        setLoading(false)
    }

    useEffect(() => { fetchAll() }, [])

    // Close dropdown on outside click
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setShowDropdown(false)
            }
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [])

    // Debounced search
    useEffect(() => {
        if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
        if (!searchQuery.trim()) {
            setSearchResults([])
            setShowDropdown(false)
            return
        }
        setSearchLoading(true)
        searchTimerRef.current = setTimeout(async () => {
            try {
                const res = await api.searchStocks(searchQuery.trim())
                setSearchResults(res.results)
                setShowDropdown(true)
            } catch {}
            setSearchLoading(false)
        }, 300)
    }, [searchQuery])

    const addToWatchlist = async (symbol: string) => {
        try {
            await api.addToWatchlist(symbol)
            setSearchQuery('')
            setShowDropdown(false)
            fetchAll()
        } catch (e) {
            alert(e instanceof Error ? e.message : '添加失败')
        }
    }

    const removeFromWatchlist = async (id: string) => {
        try {
            await api.removeFromWatchlist(id)
            fetchAll()
        } catch {}
    }

    const toggleScheduled = async (symbol: string, hasScheduled: boolean) => {
        try {
            if (hasScheduled) {
                const task = scheduled.find(s => s.symbol === symbol)
                if (task) await api.deleteScheduled(task.id)
            } else {
                await api.createScheduled(symbol, 'short', '20:00')
            }
            fetchAll()
        } catch (e) {
            alert(e instanceof Error ? e.message : '操作失败')
        }
    }

    const updateScheduledHorizon = async (id: string, horizon: string) => {
        try {
            await api.updateScheduled(id, { horizon })
            fetchAll()
        } catch {}
    }

    const updateScheduledTime = async (id: string, trigger_time: string) => {
        try {
            await api.updateScheduled(id, { trigger_time })
            fetchAll()
        } catch (e) {
            alert(e instanceof Error ? e.message : '时间设置失败（需在交易时段外）')
        }
    }

    const toggleScheduledActive = async (id: string, active: boolean) => {
        try {
            await api.updateScheduled(id, { is_active: active })
            fetchAll()
        } catch {}
    }

    const deleteScheduledTask = async (id: string) => {
        try {
            await api.deleteScheduled(id)
            fetchAll()
        } catch {}
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">自选 & 定时分析</h1>
                <p className="text-slate-500 dark:text-slate-400 mt-1">管理关注标的，开启每日定时自动分析</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Left: Watchlist */}
                <div className="space-y-4">
                    {/* Stock search */}
                    <div className="card space-y-3">
                        <div className="flex items-center gap-2">
                            <Plus className="w-5 h-5 text-blue-500" />
                            <h2 className="font-semibold text-slate-900 dark:text-slate-100">添加自选</h2>
                        </div>
                        <div className="relative" ref={dropdownRef}>
                            <div className="flex items-center gap-2">
                                <div className="relative flex-1">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                    <input
                                        value={searchQuery}
                                        onChange={e => setSearchQuery(e.target.value)}
                                        onFocus={() => searchResults.length > 0 && setShowDropdown(true)}
                                        placeholder="搜索代码或名称，如 300750 或 宁德时代"
                                        className="input pl-9 w-full"
                                        maxLength={20}
                                    />
                                    {searchLoading && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-slate-400" />}
                                </div>
                            </div>

                            {/* Search dropdown */}
                            {showDropdown && searchResults.length > 0 && (
                                <div className="absolute z-50 w-full mt-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                                    {searchResults.map(r => (
                                        <button
                                            key={r.symbol}
                                            onClick={() => addToWatchlist(r.symbol)}
                                            className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                                        >
                                            <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{r.name}</span>
                                            <span className="text-xs text-slate-400">{r.symbol}</span>
                                            <Plus className="w-3.5 h-3.5 text-blue-500 ml-auto" />
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Watchlist */}
                    <div className="card">
                        <div className="flex items-center gap-2 mb-4">
                            <Briefcase className="w-5 h-5 text-purple-500" />
                            <h2 className="font-semibold text-slate-900 dark:text-slate-100">自选列表 ({watchlist.length}/50)</h2>
                        </div>

                        {watchlist.length === 0 ? (
                            <div className="text-center py-10">
                                <Briefcase className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                                <p className="text-slate-500 dark:text-slate-400">还没有关注的股票</p>
                                <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">搜索代码或名称添加</p>
                            </div>
                        ) : (
                            <div className="divide-y divide-slate-100 dark:divide-slate-700">
                                {watchlist.map(item => {
                                    const report = latestReports[item.symbol]
                                    return (
                                        <div key={item.id} className="flex items-center gap-3 py-3">
                                            <div className="w-9 h-9 rounded-lg bg-blue-100 dark:bg-blue-500/10 flex items-center justify-center shrink-0">
                                                <TrendingUp className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="font-medium text-slate-900 dark:text-slate-100 text-sm">{item.name}</p>
                                                <p className="text-xs text-slate-400">{item.symbol}</p>
                                                {report && (
                                                    <p className="text-xs text-slate-400 mt-0.5">
                                                        最近：{report.trade_date} · {report.direction || report.decision || '—'}
                                                    </p>
                                                )}
                                            </div>
                                            {/* Schedule toggle */}
                                            <button
                                                onClick={() => toggleScheduled(item.symbol, item.has_scheduled)}
                                                className={`flex items-center gap-1 px-2 py-1 text-xs rounded-lg transition-colors ${
                                                    item.has_scheduled
                                                        ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100'
                                                        : 'bg-slate-100 dark:bg-slate-700 text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-600'
                                                }`}
                                                title={item.has_scheduled ? '已开启定时分析' : '开启定时分析'}
                                            >
                                                <Timer className="w-3 h-3" />
                                                {item.has_scheduled ? '定时' : '定时'}
                                            </button>
                                            {/* Analyze */}
                                            <button
                                                onClick={() => navigate(`/analysis?symbol=${item.symbol}`)}
                                                className="flex items-center gap-1 px-2 py-1 text-xs rounded-lg bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-500/20 transition-colors"
                                            >
                                                <Activity className="w-3 h-3" />
                                                分析
                                            </button>
                                            {/* Delete */}
                                            <button
                                                onClick={() => removeFromWatchlist(item.id)}
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

                {/* Right: Scheduled Analysis */}
                <div className="card">
                    <div className="flex items-center gap-2 mb-4">
                        <Clock className="w-5 h-5 text-emerald-500" />
                        <h2 className="font-semibold text-slate-900 dark:text-slate-100">定时分析 ({scheduled.length}/10)</h2>
                    </div>
                    <p className="text-xs text-slate-400 mb-4">每个交易日在设定时间自动执行（允许 20:00~次日 08:00）</p>

                    {scheduled.length === 0 ? (
                        <div className="text-center py-10">
                            <Clock className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                            <p className="text-slate-500 dark:text-slate-400">暂无定时任务</p>
                            <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">在自选列表中点击"定时"开启</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {scheduled.map(task => (
                                <div
                                    key={task.id}
                                    className={`rounded-xl border p-3 transition-all ${
                                        !task.is_active
                                            ? 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/30 opacity-60'
                                            : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60'
                                    }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <p className="font-medium text-sm text-slate-900 dark:text-slate-100">{task.name}</p>
                                                <span className="text-xs text-slate-400">{task.symbol}</span>
                                            </div>
                                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                                                {/* Horizon badge */}
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400">
                                                    {HORIZON_LABELS[task.horizon] || task.horizon}
                                                </span>
                                                {/* Trigger time */}
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">
                                                    <Clock className="w-2.5 h-2.5" />
                                                    {task.trigger_time}
                                                </span>
                                                {/* Last run status */}
                                                {task.last_run_date && (
                                                    <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                                                        {task.last_run_status === 'success' ? (
                                                            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                                                        ) : task.last_run_status === 'failed' ? (
                                                            <XCircle className="w-3 h-3 text-red-500" />
                                                        ) : null}
                                                        {task.last_run_date}
                                                    </span>
                                                )}
                                            </div>
                                            {task.consecutive_failures >= 3 && (
                                                <div className="flex items-center gap-1 mt-1.5 text-[10px] text-amber-600 dark:text-amber-400">
                                                    <AlertTriangle className="w-3 h-3" />
                                                    连续失败 {task.consecutive_failures} 次，已自动停用
                                                </div>
                                            )}
                                        </div>

                                        {/* Horizon select (single) */}
                                        <div className="flex gap-1">
                                            {(['short', 'medium'] as const).map(h => (
                                                <button
                                                    key={h}
                                                    onClick={() => updateScheduledHorizon(task.id, h)}
                                                    className={`px-2 py-0.5 text-[10px] rounded-full border transition-colors ${
                                                        task.horizon === h
                                                            ? 'bg-blue-500 border-blue-500 text-white'
                                                            : 'border-slate-300 dark:border-slate-600 text-slate-400 hover:border-blue-400'
                                                    }`}
                                                >
                                                    {HORIZON_LABELS[h]}
                                                </button>
                                            ))}
                                        </div>

                                        {/* Time picker */}
                                        <input
                                            type="time"
                                            value={task.trigger_time}
                                            onChange={e => updateScheduledTime(task.id, e.target.value)}
                                            className="w-[90px] text-sm px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-600 bg-transparent text-slate-700 dark:text-slate-200"
                                        />

                                        {/* Active toggle */}
                                        <button
                                            onClick={() => toggleScheduledActive(task.id, !task.is_active)}
                                            className={`relative w-9 h-5 rounded-full transition-colors shrink-0 ${
                                                task.is_active ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'
                                            }`}
                                        >
                                            <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                                                task.is_active ? 'translate-x-4' : 'translate-x-0.5'
                                            }`} />
                                        </button>

                                        {/* Delete */}
                                        <button
                                            onClick={() => deleteScheduledTask(task.id)}
                                            className="p-1.5 text-slate-400 hover:text-red-500 transition-colors shrink-0"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>

                                    {task.last_report_id && task.last_run_status === 'success' && (
                                        <button
                                            onClick={() => navigate(`/reports?report=${task.last_report_id}`)}
                                            className="mt-2 text-xs text-blue-500 hover:text-blue-600 flex items-center gap-1"
                                        >
                                            查看最近报告 →
                                        </button>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
