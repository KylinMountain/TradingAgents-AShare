import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Briefcase, Plus, Trash2, TrendingUp, Activity, Search,
    Clock, AlertTriangle, CheckCircle2, XCircle, Loader2, Timer,
    Database, ImagePlus,
} from 'lucide-react'
import { api } from '@/services/api'
import type { WatchlistItem, ScheduledAnalysis, StockSearchResult, Report } from '@/types'

const HORIZON_LABELS: Record<string, string> = { short: '短线', medium: '中线' }
const WATCHLIST_BATCH_SPLIT_RE = /[,\s，、；;]+/
const SCHEDULED_TEST_TOOLTIP =
    '会立刻对当前勾选的股票批量发起最近交易日分析请求，并自动带上已导入的持仓上下文；若已开启邮箱报告，也可以顺带检查邮箱是否收到结果。不会改动原有定时设置。'

function HorizonSwitch({
    value,
    onChange,
    disabled = false,
    compact = false,
}: {
    value: 'short' | 'medium'
    onChange: (horizon: 'short' | 'medium') => void
    disabled?: boolean
    compact?: boolean
}) {
    const wrapperClass = compact ? 'h-8 w-[124px]' : 'h-10 w-[144px]'
    const knobClass = compact ? 'top-1 left-1 h-6 w-[calc(50%-4px)]' : 'top-1 left-1 h-8 w-[calc(50%-4px)]'
    const labelClass = compact ? 'text-[11px]' : 'text-xs'

    return (
        <div className={`relative grid ${wrapperClass} grid-cols-2 rounded-full p-1 transition-colors ${
            disabled
                ? 'bg-slate-200 dark:bg-slate-700'
                : 'bg-slate-100 dark:bg-slate-700/70'
        }`}>
            <div
                className={`pointer-events-none absolute ${knobClass} rounded-full bg-white shadow-sm ring-1 ring-slate-200/80 transition-transform duration-300 dark:bg-slate-900 dark:ring-slate-700 ${
                    value === 'medium' ? 'translate-x-full' : ''
                }`}
            />
            {(['short', 'medium'] as const).map(horizon => (
                <button
                    key={horizon}
                    type="button"
                    onClick={() => onChange(horizon)}
                    disabled={disabled}
                    className={`relative z-10 rounded-full px-3 font-medium transition-all duration-200 ${labelClass} ${
                        value === horizon
                            ? 'text-slate-900 dark:text-white'
                            : 'text-slate-500 hover:text-slate-700 dark:text-slate-300 dark:hover:text-slate-100'
                    }`}
                >
                    {HORIZON_LABELS[horizon]}
                </button>
            ))}
        </div>
    )
}

export default function Portfolio() {
    const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
    const [scheduled, setScheduled] = useState<ScheduledAnalysis[]>([])
    const [latestReports, setLatestReports] = useState<Record<string, Report>>({})
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState<string | null>(null)
    const [selectedScheduledIds, setSelectedScheduledIds] = useState<string[]>([])
    const [batchHorizon, setBatchHorizon] = useState<'short' | 'medium'>('short')
    const [batchTriggerTime, setBatchTriggerTime] = useState('20:00')
    const [scheduledBatchBusyAction, setScheduledBatchBusyAction] = useState<string | null>(null)
    const [pendingHorizonTaskIds, setPendingHorizonTaskIds] = useState<Record<string, boolean>>({})

    // Search state
    const [searchQuery, setSearchQuery] = useState('')
    const [searchResults, setSearchResults] = useState<StockSearchResult[]>([])
    const [searchLoading, setSearchLoading] = useState(false)
    const [showDropdown, setShowDropdown] = useState(false)
    const [addingWatchlist, setAddingWatchlist] = useState(false)
    const [vlmParsing, setVlmParsing] = useState(false)
    const watchlistFileInputRef = useRef<HTMLInputElement>(null)
    const [watchlistFeedback, setWatchlistFeedback] = useState<{
        tone: 'success' | 'warning' | 'error'
        message: string
        details: string[]
    } | null>(null)
    const searchTimerRef = useRef<ReturnType<typeof setTimeout>>()
    const dropdownRef = useRef<HTMLDivElement>(null)

    const navigate = useNavigate()
    const trimmedQuery = searchQuery.trim()
    const isBatchInput = trimmedQuery.length > 0 && WATCHLIST_BATCH_SPLIT_RE.test(trimmedQuery)
    const selectedScheduledIdSet = new Set(selectedScheduledIds)
    const selectedScheduledCount = scheduled.filter(task => selectedScheduledIdSet.has(task.id)).length
    const hasSelectedScheduled = selectedScheduledCount > 0
    const allScheduledSelected = scheduled.length > 0 && selectedScheduledCount === scheduled.length
    const isScheduledBatchBusy = scheduledBatchBusyAction !== null

    const fetchAll = async () => {
        setLoading(true)
        setLoadError(null)
        try {
            const overview = await api.getPortfolioOverview()
            setWatchlist(overview.watchlist)
            setScheduled(overview.scheduled)
            const reportMap: Record<string, Report> = {}
            for (const report of overview.latest_reports) {
                reportMap[report.symbol] = report
            }
            setLatestReports(reportMap)
        } catch (error) {
            console.error('Failed to load portfolio overview:', error)
            setLoadError(error instanceof Error ? error.message : '加载自选与定时分析数据失败')
        }
        finally {
            setLoading(false)
        }
    }

    useEffect(() => { void fetchAll() }, [])

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

    useEffect(() => {
        const validIds = new Set(scheduled.map(task => task.id))
        setSelectedScheduledIds(current => current.filter(id => validIds.has(id)))
    }, [scheduled])

    useEffect(() => {
        if (selectedScheduledIds.length !== 1) return
        const selectedTask = scheduled.find(task => task.id === selectedScheduledIds[0])
        if (!selectedTask) return
        setBatchHorizon(selectedTask.horizon === 'medium' ? 'medium' : 'short')
        setBatchTriggerTime(selectedTask.trigger_time || '20:00')
    }, [scheduled, selectedScheduledIds])

    // Debounced search
    useEffect(() => {
        if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
        if (!trimmedQuery || isBatchInput) {
            setSearchResults([])
            setShowDropdown(false)
            setSearchLoading(false)
            return
        }
        setSearchLoading(true)
        searchTimerRef.current = setTimeout(async () => {
            try {
                const res = await api.searchStocks(trimmedQuery)
                setSearchResults(res.results)
                setShowDropdown(true)
            } catch (error) {
                console.error('Failed to search stocks:', error)
                setShowDropdown(false)
            }
            setSearchLoading(false)
        }, 300)
    }, [trimmedQuery, isBatchInput])

    const addToWatchlist = async (symbol: string) => {
        try {
            const response = await api.addToWatchlist(symbol)
            const item = response.results.find(result => result.status === 'added')?.item
            if (!item) {
                throw new Error(response.results[0]?.message || '添加失败')
            }
            setSearchQuery('')
            setShowDropdown(false)
            setWatchlistFeedback({
                tone: 'success',
                message: `已添加 ${item.name} 到自选列表`,
                details: [],
            })
            fetchAll()
        } catch (e) {
            alert(e instanceof Error ? e.message : '添加失败')
        }
    }

    const submitWatchlistInput = async () => {
        if (!trimmedQuery) return
        setAddingWatchlist(true)
        setWatchlistFeedback(null)
        try {
            const response = await api.addToWatchlist(trimmedQuery)
            const details = response.results
                .filter(item => item.status !== 'added')
                .slice(0, 6)
                .map(item => `${item.input}：${item.message}`)
            const tone =
                response.summary.failed > 0 && response.summary.added === 0 && response.summary.duplicate === 0
                    ? 'error'
                    : response.summary.failed > 0 || response.summary.duplicate > 0
                        ? 'warning'
                        : 'success'
            setWatchlistFeedback({
                tone,
                message: response.message,
                details,
            })
            if (response.summary.added > 0) {
                await fetchAll()
            }
            if (response.summary.failed === 0) {
                setSearchQuery('')
                setShowDropdown(false)
            }
        } catch (e) {
            alert(e instanceof Error ? e.message : '批量添加失败')
        } finally {
            setAddingWatchlist(false)
        }
    }

    const handleWatchlistImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return
        e.target.value = ''

        setVlmParsing(true)
        setWatchlistFeedback(null)
        try {
            const result = await api.parsePositionImage(file)
            if (result.positions.length === 0) {
                setWatchlistFeedback({ tone: 'error', message: '未从截图中识别到股票信息', details: [] })
                return
            }
            const symbols = result.positions.map(p => p.symbol).join(',')
            setSearchQuery(symbols)
            setWatchlistFeedback({
                tone: 'success',
                message: `已识别 ${result.positions.length} 只股票，请点击"批量添加"确认`,
                details: result.positions.map(p => `${p.symbol} ${p.name || ''}`).slice(0, 10),
            })
        } catch (err) {
            setWatchlistFeedback({
                tone: 'error',
                message: err instanceof Error ? err.message : '图片解析失败',
                details: [],
            })
        } finally {
            setVlmParsing(false)
        }
    }

    const removeFromWatchlist = async (id: string) => {
        try {
            await api.removeFromWatchlist(id)
            await fetchAll()
        } catch (error) {
            console.error('Failed to remove watchlist item:', error)
            alert(error instanceof Error ? error.message : '移除自选失败')
        }
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

    const updateWatchlistScheduledFlags = (symbols: string[], hasScheduled: boolean) => {
        if (symbols.length === 0) return
        const symbolSet = new Set(symbols)
        setWatchlist(current =>
            current.map(item => (
                symbolSet.has(item.symbol)
                    ? { ...item, has_scheduled: hasScheduled }
                    : item
            ))
        )
    }

    const mergeScheduledTask = (nextTask: ScheduledAnalysis) => {
        setScheduled(current =>
            current.map(task => (task.id === nextTask.id ? { ...task, ...nextTask } : task))
        )
    }

    const mergeScheduledTasks = (nextTasks: ScheduledAnalysis[]) => {
        const taskMap = new Map(nextTasks.map(task => [task.id, task]))
        setScheduled(current =>
            current.map(task => {
                const nextTask = taskMap.get(task.id)
                return nextTask ? { ...task, ...nextTask } : task
            })
        )
    }

    const removeScheduledTasksFromState = (itemIds: string[]) => {
        if (itemIds.length === 0) return
        const itemIdSet = new Set(itemIds)
        const removedSymbols = scheduled
            .filter(task => itemIdSet.has(task.id))
            .map(task => task.symbol)

        setScheduled(current => current.filter(task => !itemIdSet.has(task.id)))
        setSelectedScheduledIds(current => current.filter(id => !itemIdSet.has(id)))
        updateWatchlistScheduledFlags(removedSymbols, false)
    }

    const toggleScheduledSelection = (taskId: string) => {
        setSelectedScheduledIds(current => (
            current.includes(taskId)
                ? current.filter(id => id !== taskId)
                : [...current, taskId]
        ))
    }

    const toggleSelectAllScheduled = () => {
        setSelectedScheduledIds(current => (
            current.length === scheduled.length
                ? []
                : scheduled.map(task => task.id)
        ))
    }

    const updateScheduledHorizon = async (id: string, horizon: string) => {
        const previousTask = scheduled.find(task => task.id === id)
        if (!previousTask || previousTask.horizon === horizon) return

        setPendingHorizonTaskIds(current => ({ ...current, [id]: true }))
        mergeScheduledTask({ ...previousTask, horizon })
        try {
            const updatedTask = await api.updateScheduled(id, { horizon })
            mergeScheduledTask(updatedTask)
        } catch (e) {
            mergeScheduledTask(previousTask)
            alert(e instanceof Error ? e.message : '切换分析周期失败')
        } finally {
            setPendingHorizonTaskIds(current => {
                const next = { ...current }
                delete next[id]
                return next
            })
        }
    }

    const updateScheduledTime = async (id: string, trigger_time: string) => {
        const previousTask = scheduled.find(task => task.id === id)
        if (!previousTask || previousTask.trigger_time === trigger_time) return

        mergeScheduledTask({ ...previousTask, trigger_time })
        try {
            const updatedTask = await api.updateScheduled(id, { trigger_time })
            mergeScheduledTask(updatedTask)
        } catch (e) {
            mergeScheduledTask(previousTask)
            alert(e instanceof Error ? e.message : '时间设置失败（需在交易时段外）')
        }
    }

    const toggleScheduledActive = async (id: string, active: boolean) => {
        const previousTask = scheduled.find(task => task.id === id)
        if (!previousTask || previousTask.is_active === active) return

        mergeScheduledTask({ ...previousTask, is_active: active })
        try {
            const updatedTask = await api.updateScheduled(id, { is_active: active })
            mergeScheduledTask(updatedTask)
        } catch (e) {
            mergeScheduledTask(previousTask)
            alert(e instanceof Error ? e.message : '状态切换失败')
        }
    }

    const deleteScheduledTask = async (id: string) => {
        const targetTask = scheduled.find(task => task.id === id)
        if (!targetTask) return
        try {
            await api.deleteScheduled(id)
            removeScheduledTasksFromState([id])
        } catch (e) {
            alert(e instanceof Error ? e.message : '删除失败')
        }
    }

    const applyBatchScheduledUpdate = async (
        actionKey: string,
        updates: { is_active?: boolean; horizon?: string; trigger_time?: string },
        errorMessage: string,
    ) => {
        const selectedTasks = scheduled.filter(task => selectedScheduledIdSet.has(task.id))
        if (selectedTasks.length === 0) {
            alert('请先勾选要批量设置的定时任务')
            return
        }

        setScheduledBatchBusyAction(actionKey)
        mergeScheduledTasks(selectedTasks.map(task => ({ ...task, ...updates })))
        try {
            const result = await api.updateScheduledBatch(
                selectedTasks.map(task => task.id),
                updates,
            )
            mergeScheduledTasks(result.items)
        } catch (e) {
            mergeScheduledTasks(selectedTasks)
            alert(e instanceof Error ? e.message : errorMessage)
        } finally {
            setScheduledBatchBusyAction(null)
        }
    }

    const applyBatchScheduledDelete = async () => {
        const selectedTasks = scheduled.filter(task => selectedScheduledIdSet.has(task.id))
        if (selectedTasks.length === 0) {
            alert('请先勾选要批量删除的定时任务')
            return
        }
        if (!confirm(`确定删除选中的 ${selectedTasks.length} 个定时任务吗？`)) return

        setScheduledBatchBusyAction('delete')
        try {
            const result = await api.deleteScheduledBatch(selectedTasks.map(task => task.id))
            removeScheduledTasksFromState(result.deleted_ids)
            if (result.missing_ids.length > 0) {
                await fetchAll()
            }
        } catch (e) {
            alert(e instanceof Error ? e.message : '批量删除失败')
        } finally {
            setScheduledBatchBusyAction(null)
        }
    }

    const triggerScheduledTest = async () => {
        const selectedTasks = scheduled.filter(task => selectedScheduledIdSet.has(task.id))
        if (selectedTasks.length === 0) {
            alert('请先勾选要测试的定时任务')
            return
        }

        setScheduledBatchBusyAction('trigger-test')
        try {
            const result = await api.triggerScheduledBatch(selectedTasks.map(task => task.id))
            const summaryText = result.summary.with_position_context > 0
                ? `已触发 ${result.summary.total} 个分析请求，其中 ${result.summary.with_position_context} 个已带入持仓上下文。`
                : `已触发 ${result.summary.total} 个分析请求。`
            alert(summaryText)
            navigate('/reports')
        } catch (e) {
            alert(e instanceof Error ? e.message : '测试触发失败')
        } finally {
            setScheduledBatchBusyAction(null)
        }
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
            {loadError && (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
                    {loadError}
                </div>
            )}
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">自选 & 定时分析</h1>
                <p className="text-slate-500 dark:text-slate-400 mt-1">为关注标的创建每日自动分析任务</p>
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
                        <div className="space-y-3" ref={dropdownRef}>
                            <div className="relative flex items-center gap-2">
                                <div className="relative flex-1">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                    <input
                                        type="text"
                                        value={searchQuery}
                                        onChange={e => setSearchQuery(e.target.value)}
                                        onFocus={() => searchResults.length > 0 && !isBatchInput && setShowDropdown(true)}
                                        onKeyDown={e => e.key === 'Enter' && trimmedQuery && submitWatchlistInput()}
                                        placeholder="搜索代码/名称，批量粘贴，或点右侧📷上传截图识别"
                                        className="input pl-9 pr-10 w-full"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => watchlistFileInputRef.current?.click()}
                                        disabled={vlmParsing}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 transition-colors disabled:opacity-40 dark:hover:bg-indigo-500/10"
                                        title="上传截图批量添加"
                                    >
                                        {vlmParsing ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImagePlus className="w-4 h-4" />}
                                    </button>
                                    <input
                                        ref={watchlistFileInputRef}
                                        type="file"
                                        accept="image/*"
                                        className="hidden"
                                        onChange={handleWatchlistImageUpload}
                                    />
                                    {searchLoading && !vlmParsing && <Loader2 className="absolute right-9 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-slate-400" />}
                                </div>
                                <button
                                    type="button"
                                    onClick={submitWatchlistInput}
                                    disabled={!trimmedQuery || addingWatchlist}
                                    className="btn-primary inline-flex items-center justify-center gap-2 whitespace-nowrap shrink-0"
                                >
                                    {addingWatchlist ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                                    {isBatchInput ? '批量添加' : '添加'}
                                </button>
                            </div>

                            {watchlistFeedback && (
                                <div className={`rounded-xl border px-3 py-3 text-sm ${
                                    watchlistFeedback.tone === 'success'
                                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300'
                                        : watchlistFeedback.tone === 'warning'
                                            ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300'
                                            : 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300'
                                }`}>
                                    <div>{watchlistFeedback.message}</div>
                                    {watchlistFeedback.details.length > 0 && (
                                        <div className="mt-2 space-y-1 text-xs opacity-90">
                                            {watchlistFeedback.details.map(detail => (
                                                <div key={detail}>{detail}</div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Search dropdown */}
                            {showDropdown && searchResults.length > 0 && (
                                <div className="border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 shadow-lg max-h-60 overflow-y-auto">
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

                    {/* Compact batch toolbar — only visible when items are selected */}
                    {hasSelectedScheduled && (
                        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-blue-200/80 bg-blue-50/60 px-3 py-2 dark:border-blue-500/20 dark:bg-blue-500/5">
                            <label className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 dark:text-slate-200">
                                <input
                                    type="checkbox"
                                    checked={allScheduledSelected}
                                    onChange={toggleSelectAllScheduled}
                                    disabled={isScheduledBatchBusy}
                                    className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                                />
                                全选
                            </label>
                            <span className="text-xs text-slate-500 dark:text-slate-400">已选 {selectedScheduledCount} 项</span>
                            <span className="mx-1 h-4 w-px bg-slate-200 dark:bg-slate-700" />

                            <HorizonSwitch
                                value={batchHorizon}
                                compact
                                disabled={isScheduledBatchBusy}
                                onChange={horizon => {
                                    setBatchHorizon(horizon)
                                    void applyBatchScheduledUpdate(`horizon-${horizon}`, { horizon }, '批量切换周期失败')
                                }}
                            />

                            <div className="inline-flex items-center gap-1">
                                <input
                                    type="time"
                                    value={batchTriggerTime}
                                    onChange={e => setBatchTriggerTime(e.target.value)}
                                    disabled={isScheduledBatchBusy}
                                    className="h-8 w-[96px] rounded-lg border border-slate-300 bg-white px-2 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
                                />
                                <button
                                    type="button"
                                    onClick={() => void applyBatchScheduledUpdate('time', { trigger_time: batchTriggerTime }, '批量修改时间失败')}
                                    disabled={isScheduledBatchBusy}
                                    className="h-8 rounded-lg bg-slate-800 px-2.5 text-[11px] font-medium text-white hover:bg-slate-700 disabled:opacity-40 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
                                >
                                    {scheduledBatchBusyAction === 'time' ? <Loader2 className="h-3 w-3 animate-spin" /> : '应用'}
                                </button>
                            </div>

                            <span className="mx-1 h-4 w-px bg-slate-200 dark:bg-slate-700" />

                            <div className="inline-flex items-center gap-1.5">
                                <button
                                    type="button"
                                    onClick={() => void triggerScheduledTest()}
                                    disabled={isScheduledBatchBusy}
                                    title={SCHEDULED_TEST_TOOLTIP}
                                    className="h-8 rounded-lg bg-sky-600 px-2.5 text-[11px] font-medium text-white hover:bg-sky-700 disabled:opacity-40"
                                >
                                    {scheduledBatchBusyAction === 'trigger-test' ? <Loader2 className="h-3 w-3 animate-spin" /> : '测试'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => void applyBatchScheduledUpdate('enable', { is_active: true }, '批量启用失败')}
                                    disabled={isScheduledBatchBusy}
                                    className="h-8 rounded-lg bg-emerald-500 px-2.5 text-[11px] font-medium text-white hover:bg-emerald-600 disabled:opacity-40"
                                >
                                    {scheduledBatchBusyAction === 'enable' ? <Loader2 className="h-3 w-3 animate-spin" /> : '启用'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => void applyBatchScheduledUpdate('disable', { is_active: false }, '批量停用失败')}
                                    disabled={isScheduledBatchBusy}
                                    className="h-8 rounded-lg bg-amber-500 px-2.5 text-[11px] font-medium text-white hover:bg-amber-600 disabled:opacity-40"
                                >
                                    {scheduledBatchBusyAction === 'disable' ? <Loader2 className="h-3 w-3 animate-spin" /> : '停用'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => void applyBatchScheduledDelete()}
                                    disabled={isScheduledBatchBusy}
                                    className="h-8 rounded-lg bg-rose-500 px-2.5 text-[11px] font-medium text-white hover:bg-rose-600 disabled:opacity-40"
                                >
                                    {scheduledBatchBusyAction === 'delete' ? <Loader2 className="h-3 w-3 animate-spin" /> : '删除'}
                                </button>
                            </div>

                            <button
                                type="button"
                                onClick={() => setSelectedScheduledIds([])}
                                className="ml-auto text-[11px] text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                            >
                                取消
                            </button>
                        </div>
                    )}

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
                                        selectedScheduledIdSet.has(task.id)
                                            ? 'border-blue-300 bg-blue-50/60 ring-2 ring-blue-200/70 dark:border-blue-500/40 dark:bg-blue-500/10 dark:ring-blue-500/20'
                                            : !task.is_active
                                            ? 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/30 opacity-60'
                                            : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60'
                                    }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <input
                                            type="checkbox"
                                            checked={selectedScheduledIdSet.has(task.id)}
                                            onChange={() => toggleScheduledSelection(task.id)}
                                            disabled={isScheduledBatchBusy}
                                            className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                                        />

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
                                            {task.has_imported_context && (
                                                <div className="flex items-center gap-1 mt-1.5 text-[10px] text-indigo-600 dark:text-indigo-300 flex-wrap">
                                                    <Database className="w-3 h-3" />
                                                    <span>已带入持仓上下文</span>
                                                    {task.imported_current_position != null && <span>持仓 {task.imported_current_position}</span>}
                                                    {task.imported_average_cost != null && <span>成本 {task.imported_average_cost}</span>}
                                                    {(task.imported_trade_points_count || 0) > 0 && <span>买卖点 {task.imported_trade_points_count}</span>}
                                                </div>
                                            )}
                                        </div>

                                        {/* Horizon switch */}
                                        <HorizonSwitch
                                            value={task.horizon === 'medium' ? 'medium' : 'short'}
                                            compact
                                            disabled={Boolean(pendingHorizonTaskIds[task.id]) || isScheduledBatchBusy}
                                            onChange={horizon => updateScheduledHorizon(task.id, horizon)}
                                        />

                                        {/* Time picker */}
                                        <input
                                            type="time"
                                            value={task.trigger_time}
                                            onChange={e => updateScheduledTime(task.id, e.target.value)}
                                            disabled={isScheduledBatchBusy}
                                            className="w-[90px] text-sm px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-600 bg-transparent text-slate-700 dark:text-slate-200"
                                        />

                                        {/* Active toggle */}
                                        <button
                                            type="button"
                                            onClick={() => toggleScheduledActive(task.id, !task.is_active)}
                                            disabled={isScheduledBatchBusy}
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
                                            type="button"
                                            onClick={() => deleteScheduledTask(task.id)}
                                            disabled={isScheduledBatchBusy}
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
