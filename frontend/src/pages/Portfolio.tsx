import { useState, useEffect, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Briefcase, Plus, Trash2, TrendingUp, Activity, Search,
    Clock, AlertTriangle, CheckCircle2, XCircle, Loader2, Settings2, Save,
} from 'lucide-react'
import { api } from '@/services/api'
import type { WatchlistItem, ScheduledAnalysis, StockSearchResult, Report } from '@/types'

type TaskDraft = {
    frequency: 'daily' | 'weekly' | 'monthly'
    trigger_time: string
    day_of_week: number | null
    day_of_month: number | null
    prompt_mode: 'merge_global' | 'override_global'
    custom_prompt: string
}

const WINDOW_SLOTS = [
    { task_slot: 'pre_open_0800', title: '开盘前', time: '08:00' },
    { task_slot: 'midday_1200', title: '午间', time: '12:00' },
    { task_slot: 'post_close_2000', title: '收盘后', time: '20:00' },
] as const

const CUSTOM_SLOTS = [
    { task_slot: 'custom_short', title: '自定义短线', horizonLabel: '短线', defaultTime: '20:00' },
    { task_slot: 'custom_long', title: '自定义长期', horizonLabel: '长期', defaultTime: '20:00' },
] as const

const WEEKDAY_OPTIONS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

function createDefaultDraft(slot: string): TaskDraft {
    const custom = CUSTOM_SLOTS.find(item => item.task_slot === slot)
    return {
        frequency: 'daily',
        trigger_time: custom?.defaultTime || '20:00',
        day_of_week: 0,
        day_of_month: 1,
        prompt_mode: 'merge_global',
        custom_prompt: '',
    }
}

function buildDraftFromTask(task?: ScheduledAnalysis): TaskDraft {
    if (!task) return createDefaultDraft('')
    return {
        frequency: (task.frequency === 'weekly' || task.frequency === 'monthly' ? task.frequency : 'daily'),
        trigger_time: task.trigger_time || '20:00',
        day_of_week: task.day_of_week ?? 0,
        day_of_month: task.day_of_month ?? 1,
        prompt_mode: task.prompt_mode || 'merge_global',
        custom_prompt: task.custom_prompt || '',
    }
}

function slotSort(task: ScheduledAnalysis) {
    const order = ['pre_open_0800', 'midday_1200', 'post_close_2000', 'custom_short', 'custom_long']
    return order.indexOf(task.task_slot)
}

export default function Portfolio() {
    const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
    const [scheduled, setScheduled] = useState<ScheduledAnalysis[]>([])
    const [latestReports, setLatestReports] = useState<Record<string, Report>>({})
    const [loading, setLoading] = useState(true)
    const [selectedSymbol, setSelectedSymbol] = useState<string>('')
    const [drafts, setDrafts] = useState<Record<string, TaskDraft>>({})
    const [savingSlot, setSavingSlot] = useState<string | null>(null)

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
            const [wRes, sRes] = await Promise.all([api.getWatchlist(), api.getScheduled()])
            setWatchlist(wRes.items)
            setScheduled(sRes.items)
            setSelectedSymbol(prev => prev || wRes.items[0]?.symbol || '')

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

    useEffect(() => { void fetchAll() }, [])

    useEffect(() => {
        if (!selectedSymbol && watchlist[0]?.symbol) {
            setSelectedSymbol(watchlist[0].symbol)
        }
        if (selectedSymbol && !watchlist.some(item => item.symbol === selectedSymbol)) {
            setSelectedSymbol(watchlist[0]?.symbol || '')
        }
    }, [selectedSymbol, watchlist])

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

    const selectedTasks = useMemo(
        () => scheduled.filter(task => task.symbol === selectedSymbol).sort((a, b) => slotSort(a) - slotSort(b)),
        [scheduled, selectedSymbol],
    )

    useEffect(() => {
        const nextDrafts: Record<string, TaskDraft> = {}
        for (const slot of [...WINDOW_SLOTS, ...CUSTOM_SLOTS]) {
            const task = selectedTasks.find(item => item.task_slot === slot.task_slot)
            nextDrafts[slot.task_slot] = buildDraftFromTask(task)
        }
        setDrafts(nextDrafts)
    }, [selectedTasks])

    const addToWatchlist = async (symbol: string) => {
        try {
            await api.addToWatchlist(symbol)
            setSearchQuery('')
            setShowDropdown(false)
            await fetchAll()
            setSelectedSymbol(symbol)
        } catch (e) {
            alert(e instanceof Error ? e.message : '添加失败')
        }
    }

    const removeFromWatchlist = async (id: string) => {
        try {
            await api.removeFromWatchlist(id)
            await fetchAll()
        } catch {}
    }

    const setDraft = (slot: string, partial: Partial<TaskDraft>) => {
        setDrafts(prev => ({
            ...prev,
            [slot]: {
                ...(prev[slot] || createDefaultDraft(slot)),
                ...partial,
            },
        }))
    }

    const getTask = (slot: string) => selectedTasks.find(task => task.task_slot === slot)

    const createTaskForSlot = async (task_slot: string) => {
        if (!selectedSymbol) return
        setSavingSlot(task_slot)
        try {
            const draft = drafts[task_slot] || createDefaultDraft(task_slot)
            const isWindow = WINDOW_SLOTS.some(item => item.task_slot === task_slot)
            await api.createScheduled({
                symbol: selectedSymbol,
                task_type: isWindow ? 'market_window' : 'custom_recurring',
                task_slot,
                frequency: isWindow ? 'trading_day' : draft.frequency,
                trigger_time: isWindow ? undefined : draft.trigger_time,
                day_of_week: draft.frequency === 'weekly' ? draft.day_of_week : null,
                day_of_month: draft.frequency === 'monthly' ? draft.day_of_month : null,
                prompt_mode: draft.prompt_mode,
                custom_prompt: draft.custom_prompt,
            })
            await fetchAll()
        } catch (e) {
            alert(e instanceof Error ? e.message : '创建定时任务失败')
        } finally {
            setSavingSlot(null)
        }
    }

    const saveTaskForSlot = async (task: ScheduledAnalysis) => {
        setSavingSlot(task.task_slot)
        try {
            const draft = drafts[task.task_slot] || buildDraftFromTask(task)
            await api.updateScheduled(task.id, {
                frequency: task.task_type === 'custom_recurring' ? draft.frequency : undefined,
                trigger_time: task.task_type === 'custom_recurring' ? draft.trigger_time : undefined,
                day_of_week: draft.frequency === 'weekly' ? draft.day_of_week : null,
                day_of_month: draft.frequency === 'monthly' ? draft.day_of_month : null,
                prompt_mode: draft.prompt_mode,
                custom_prompt: draft.custom_prompt,
            })
            await fetchAll()
        } catch (e) {
            alert(e instanceof Error ? e.message : '保存失败')
        } finally {
            setSavingSlot(null)
        }
    }

    const toggleTaskActive = async (task: ScheduledAnalysis) => {
        setSavingSlot(task.task_slot)
        try {
            await api.updateScheduled(task.id, { is_active: !task.is_active })
            await fetchAll()
        } catch {}
        finally {
            setSavingSlot(null)
        }
    }

    const deleteTask = async (task: ScheduledAnalysis) => {
        setSavingSlot(task.task_slot)
        try {
            await api.deleteScheduled(task.id)
            await fetchAll()
        } catch {}
        finally {
            setSavingSlot(null)
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
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">自选 & 定时分析</h1>
                <p className="text-slate-500 dark:text-slate-400 mt-1">每只股票固定支持 3 个交易日窗口任务和 2 个自定义循环任务</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[1.05fr,1.35fr] gap-6">
                <div className="space-y-4">
                    <div className="card space-y-3">
                        <div className="flex items-center gap-2">
                            <Plus className="w-5 h-5 text-blue-500" />
                            <h2 className="font-semibold text-slate-900 dark:text-slate-100">添加自选</h2>
                        </div>
                        <div className="relative" ref={dropdownRef}>
                            <div className="relative">
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

                    <div className="card">
                        <div className="flex items-center gap-2 mb-4">
                            <Briefcase className="w-5 h-5 text-purple-500" />
                            <h2 className="font-semibold text-slate-900 dark:text-slate-100">自选列表 ({watchlist.length}/50)</h2>
                        </div>

                        {watchlist.length === 0 ? (
                            <div className="text-center py-10">
                                <Briefcase className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                                <p className="text-slate-500 dark:text-slate-400">还没有关注的股票</p>
                            </div>
                        ) : (
                            <div className="divide-y divide-slate-100 dark:divide-slate-700">
                                {watchlist.map(item => {
                                    const report = latestReports[item.symbol]
                                    const selected = selectedSymbol === item.symbol
                                    return (
                                        <div
                                            key={item.id}
                                            onClick={() => setSelectedSymbol(item.symbol)}
                                            className={`w-full flex items-center gap-3 py-3 text-left transition-colors ${selected ? 'bg-blue-50/70 dark:bg-blue-500/10' : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'}`}
                                        >
                                            <div className="w-9 h-9 rounded-lg bg-blue-100 dark:bg-blue-500/10 flex items-center justify-center shrink-0 ml-2">
                                                <TrendingUp className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="font-medium text-slate-900 dark:text-slate-100 text-sm">{item.name}</p>
                                                <p className="text-xs text-slate-400">{item.symbol}</p>
                                                <p className="text-xs text-slate-400 mt-0.5">
                                                    定时任务：{item.scheduled_count || 0}/5
                                                    {report && ` · 最近：${report.trade_date} · ${report.direction || report.decision || '—'}`}
                                                </p>
                                            </div>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation()
                                                    navigate(`/analysis?symbol=${item.symbol}`)
                                                }}
                                                className="flex items-center gap-1 px-2 py-1 text-xs rounded-lg bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-500/20 transition-colors"
                                            >
                                                <Activity className="w-3 h-3" />
                                                分析
                                            </button>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation()
                                                    removeFromWatchlist(item.id)
                                                }}
                                                className="p-1.5 text-slate-400 hover:text-red-500 transition-colors mr-2"
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

                <div className="space-y-4">
                    <div className="card">
                        <div className="flex items-center gap-2 mb-2">
                            <Settings2 className="w-5 h-5 text-emerald-500" />
                            <h2 className="font-semibold text-slate-900 dark:text-slate-100">定时任务管理</h2>
                        </div>
                        {selectedSymbol ? (
                            <p className="text-sm text-slate-500 dark:text-slate-400">
                                当前股票：<span className="font-medium text-slate-700 dark:text-slate-200">{watchlist.find(item => item.symbol === selectedSymbol)?.name || selectedSymbol}</span>
                                <span className="ml-2 text-xs text-slate-400">{selectedSymbol}</span>
                            </p>
                        ) : (
                            <p className="text-sm text-slate-400">请先在左侧选择一只股票。</p>
                        )}
                    </div>

                    {selectedSymbol && (
                        <>
                            <div className="card space-y-4">
                                <div>
                                    <h3 className="font-semibold text-slate-900 dark:text-slate-100">交易日窗口任务</h3>
                                    <p className="text-xs text-slate-400 mt-1">固定为交易日 08:00、12:00、20:00，仅可启停和配置提示偏好。</p>
                                </div>
                                <div className="space-y-3">
                                    {WINDOW_SLOTS.map(slot => {
                                        const task = getTask(slot.task_slot)
                                        const draft = drafts[slot.task_slot] || createDefaultDraft(slot.task_slot)
                                        return (
                                            <div key={slot.task_slot} className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 bg-white dark:bg-slate-800/40">
                                                <div className="flex items-center gap-3">
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-medium text-slate-900 dark:text-slate-100">{slot.title}</span>
                                                            <span className="text-xs px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">{slot.time}</span>
                                                            {task && (
                                                                <span className="text-xs px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400">交易日窗口</span>
                                                            )}
                                                        </div>
                                                        {task?.last_run_date && (
                                                            <div className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                                                                {task.last_run_status === 'success' ? <CheckCircle2 className="w-3 h-3 text-emerald-500" /> : null}
                                                                {task.last_run_status === 'failed' ? <XCircle className="w-3 h-3 text-red-500" /> : null}
                                                                最近执行：{task.last_run_date}
                                                            </div>
                                                        )}
                                                    </div>
                                                    {!task ? (
                                                        <button onClick={() => createTaskForSlot(slot.task_slot)} className="btn-primary h-9 px-3 text-sm" disabled={savingSlot === slot.task_slot}>
                                                            {savingSlot === slot.task_slot ? <Loader2 className="w-4 h-4 animate-spin" /> : '启用'}
                                                        </button>
                                                    ) : (
                                                        <div className="flex items-center gap-2">
                                                            <button
                                                                onClick={() => toggleTaskActive(task)}
                                                                className={`relative w-10 h-6 rounded-full transition-colors ${task.is_active ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`}
                                                            >
                                                                <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${task.is_active ? 'translate-x-5' : 'translate-x-1'}`} />
                                                            </button>
                                                            <button onClick={() => deleteTask(task)} className="p-2 text-slate-400 hover:text-red-500">
                                                                <Trash2 className="w-4 h-4" />
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>

                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                                                    <select
                                                        value={draft.prompt_mode}
                                                        onChange={e => setDraft(slot.task_slot, { prompt_mode: e.target.value as TaskDraft['prompt_mode'] })}
                                                        className="input w-full"
                                                    >
                                                        <option value="merge_global">继承全局并追加</option>
                                                        <option value="override_global">仅用当前任务提示</option>
                                                    </select>
                                                    <button
                                                        onClick={() => task ? saveTaskForSlot(task) : createTaskForSlot(slot.task_slot)}
                                                        className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 text-sm"
                                                        disabled={savingSlot === slot.task_slot}
                                                    >
                                                        <Save className="w-4 h-4" />
                                                        保存提示偏好
                                                    </button>
                                                </div>
                                                <textarea
                                                    value={draft.custom_prompt}
                                                    onChange={e => setDraft(slot.task_slot, { custom_prompt: e.target.value })}
                                                    className="input w-full min-h-[88px] resize-y mt-3"
                                                    placeholder="例如：更关注开盘情绪、资金承接和政策催化。"
                                                />
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>

                            <div className="card space-y-4">
                                <div>
                                    <h3 className="font-semibold text-slate-900 dark:text-slate-100">自定义循环任务</h3>
                                    <p className="text-xs text-slate-400 mt-1">固定为短线、长期各一个任务位，可配置时间、周期和偏好提示。</p>
                                </div>
                                <div className="space-y-3">
                                    {CUSTOM_SLOTS.map(slot => {
                                        const task = getTask(slot.task_slot)
                                        const draft = drafts[slot.task_slot] || createDefaultDraft(slot.task_slot)
                                        return (
                                            <div key={slot.task_slot} className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 bg-white dark:bg-slate-800/40">
                                                <div className="flex items-center gap-3">
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            <span className="font-medium text-slate-900 dark:text-slate-100">{slot.title}</span>
                                                            <span className="text-xs px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400">{slot.horizonLabel}</span>
                                                            {task && <span className="text-xs px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400">{task.frequency}</span>}
                                                        </div>
                                                        {task?.consecutive_failures >= 3 && (
                                                            <div className="flex items-center gap-1 mt-1.5 text-[10px] text-amber-600 dark:text-amber-400">
                                                                <AlertTriangle className="w-3 h-3" />
                                                                连续失败 {task.consecutive_failures} 次，已自动停用
                                                            </div>
                                                        )}
                                                    </div>
                                                    {!task ? (
                                                        <button onClick={() => createTaskForSlot(slot.task_slot)} className="btn-primary h-9 px-3 text-sm" disabled={savingSlot === slot.task_slot}>
                                                            {savingSlot === slot.task_slot ? <Loader2 className="w-4 h-4 animate-spin" /> : '创建'}
                                                        </button>
                                                    ) : (
                                                        <div className="flex items-center gap-2">
                                                            <button
                                                                onClick={() => toggleTaskActive(task)}
                                                                className={`relative w-10 h-6 rounded-full transition-colors ${task.is_active ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`}
                                                            >
                                                                <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${task.is_active ? 'translate-x-5' : 'translate-x-1'}`} />
                                                            </button>
                                                            <button onClick={() => deleteTask(task)} className="p-2 text-slate-400 hover:text-red-500">
                                                                <Trash2 className="w-4 h-4" />
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>

                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                                                    <select
                                                        value={draft.frequency}
                                                        onChange={e => setDraft(slot.task_slot, { frequency: e.target.value as TaskDraft['frequency'] })}
                                                        className="input w-full"
                                                    >
                                                        <option value="daily">每天</option>
                                                        <option value="weekly">每周</option>
                                                        <option value="monthly">每月</option>
                                                    </select>
                                                    <input
                                                        type="time"
                                                        value={draft.trigger_time}
                                                        onChange={e => setDraft(slot.task_slot, { trigger_time: e.target.value })}
                                                        className="input w-full"
                                                    />
                                                    {draft.frequency === 'weekly' && (
                                                        <select
                                                            value={draft.day_of_week ?? 0}
                                                            onChange={e => setDraft(slot.task_slot, { day_of_week: Number(e.target.value) })}
                                                            className="input w-full"
                                                        >
                                                            {WEEKDAY_OPTIONS.map((label, idx) => (
                                                                <option key={label} value={idx}>{label}</option>
                                                            ))}
                                                        </select>
                                                    )}
                                                    {draft.frequency === 'monthly' && (
                                                        <input
                                                            type="number"
                                                            min={1}
                                                            max={31}
                                                            value={draft.day_of_month ?? 1}
                                                            onChange={e => setDraft(slot.task_slot, { day_of_month: Number(e.target.value) })}
                                                            className="input w-full"
                                                        />
                                                    )}
                                                    <select
                                                        value={draft.prompt_mode}
                                                        onChange={e => setDraft(slot.task_slot, { prompt_mode: e.target.value as TaskDraft['prompt_mode'] })}
                                                        className="input w-full md:col-span-2"
                                                    >
                                                        <option value="merge_global">继承全局并追加</option>
                                                        <option value="override_global">仅用当前任务提示</option>
                                                    </select>
                                                </div>
                                                <textarea
                                                    value={draft.custom_prompt}
                                                    onChange={e => setDraft(slot.task_slot, { custom_prompt: e.target.value })}
                                                    className="input w-full min-h-[96px] resize-y mt-3"
                                                    placeholder="例如：长期任务更关注估值安全边际、行业景气和机构持仓变化。"
                                                />
                                                <div className="flex items-center justify-between mt-3">
                                                    {task?.last_report_id && task.last_run_status === 'success' ? (
                                                        <button
                                                            onClick={() => navigate(`/reports?report=${task.last_report_id}`)}
                                                            className="text-xs text-blue-500 hover:text-blue-600 flex items-center gap-1"
                                                        >
                                                            查看最近报告 →
                                                        </button>
                                                    ) : <span />}
                                                    <button
                                                        onClick={() => task ? saveTaskForSlot(task) : createTaskForSlot(slot.task_slot)}
                                                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 text-sm"
                                                        disabled={savingSlot === slot.task_slot}
                                                    >
                                                        {savingSlot === slot.task_slot ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                                        保存任务
                                                    </button>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>

                            <div className="card">
                                <div className="flex items-center gap-2 mb-3">
                                    <Clock className="w-5 h-5 text-emerald-500" />
                                    <h2 className="font-semibold text-slate-900 dark:text-slate-100">当前股票已创建任务 ({selectedTasks.length}/5)</h2>
                                </div>
                                {selectedTasks.length === 0 ? (
                                    <p className="text-sm text-slate-400">当前股票还没有已创建的定时任务。</p>
                                ) : (
                                    <div className="space-y-2">
                                        {selectedTasks.map(task => (
                                            <div key={task.id} className="rounded-lg bg-slate-50 dark:bg-slate-800/50 px-3 py-2 flex items-center gap-3">
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{task.task_label}</p>
                                                    <p className="text-xs text-slate-400">
                                                        {task.task_type === 'market_window' ? '交易日窗口' : `自定义${task.horizon === 'medium' ? '长期' : '短线'}`} · {task.trigger_time}
                                                        {task.frequency !== 'trading_day' ? ` · ${task.frequency}` : ''}
                                                    </p>
                                                </div>
                                                <span className={`text-xs px-2 py-0.5 rounded ${task.is_active ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' : 'bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-300'}`}>
                                                    {task.is_active ? '启用中' : '已停用'}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
