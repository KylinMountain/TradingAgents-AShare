import { useState, useEffect, useRef } from 'react'
import { FlaskConical, Play, Trash2, ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus, RefreshCw } from 'lucide-react'
import { getBaseUrl } from '@/services/api'

interface BacktestRecord {
    date: string
    action: 'BUY' | 'SELL' | 'HOLD'
    entry_price?: number
    exit_price?: number
    return_pct?: number
    decision_summary?: string
    error?: string
}

interface BacktestStats {
    total_signals: number
    win_rate: number | null
    avg_return_pct: number | null
    best_return_pct: number | null
    worst_return_pct: number | null
}

interface BacktestJob {
    job_id: string
    symbol: string
    start_date: string
    end_date: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    created_at: string
    total_dates: number
    completed_dates: number
    records: BacktestRecord[]
    stats: BacktestStats | null
    error: string | null
    hold_days: number
    sample_interval: number
}

const ANALYSTS = [
    { id: 'market', label: '技术分析' },
    { id: 'news', label: '新闻分析' },
    { id: 'fundamentals', label: '基本面' },
    { id: 'sentiment', label: '情绪分析' },
    { id: 'macro', label: '宏观板块' },
    { id: 'smart_money', label: '主力资金' },
]

function actionBadge(action: string) {
    if (action === 'BUY') return <span className="px-1.5 py-0.5 text-xs rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 font-medium">买入</span>
    if (action === 'SELL') return <span className="px-1.5 py-0.5 text-xs rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 font-medium">卖出</span>
    return <span className="px-1.5 py-0.5 text-xs rounded bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400 font-medium">持有</span>
}

function returnColor(pct?: number | null) {
    if (pct == null) return 'text-slate-400'
    if (pct > 0) return 'text-green-600 dark:text-green-400'
    if (pct < 0) return 'text-red-600 dark:text-red-400'
    return 'text-slate-500'
}

export default function Backtest() {
    const [symbol, setSymbol] = useState('')
    const [startDate, setStartDate] = useState(() => {
        const d = new Date(); d.setMonth(d.getMonth() - 3); return d.toISOString().slice(0, 10)
    })
    const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10))
    const [holdDays, setHoldDays] = useState(5)
    const [sampleInterval, setSampleInterval] = useState(7)
    const [analysts, setAnalysts] = useState<string[]>(['market', 'news', 'fundamentals', 'sentiment', 'macro', 'smart_money'])
    const [submitting, setSubmitting] = useState(false)
    const [jobs, setJobs] = useState<BacktestJob[]>([])
    const [expandedJob, setExpandedJob] = useState<string | null>(null)
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

    const fetchJobs = async () => {
        try {
            const res = await fetch(`${getBaseUrl()}/v1/backtest`)
            const data = await res.json()
            setJobs(data.jobs || [])
        } catch { }
    }

    useEffect(() => {
        fetchJobs()
        pollingRef.current = setInterval(fetchJobs, 3000)
        return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
    }, [])

    const toggleAnalyst = (id: string) => {
        setAnalysts(prev => prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id])
    }

    const handleSubmit = async () => {
        if (!symbol.trim() || analysts.length === 0) return
        setSubmitting(true)
        try {
            const res = await fetch(`${getBaseUrl()}/v1/backtest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol.trim().toUpperCase(),
                    start_date: startDate,
                    end_date: endDate,
                    selected_analysts: analysts,
                    hold_days: holdDays,
                    sample_interval: sampleInterval,
                }),
            })
            if (res.ok) {
                const data = await res.json()
                setExpandedJob(data.job_id)
                await fetchJobs()
            }
        } finally {
            setSubmitting(false)
        }
    }

    const handleDelete = async (jobId: string, e: React.MouseEvent) => {
        e.stopPropagation()
        await fetch(`${getBaseUrl()}/v1/backtest/${jobId}`, { method: 'DELETE' })
        setJobs(prev => prev.filter(j => j.job_id !== jobId))
        if (expandedJob === jobId) setExpandedJob(null)
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">历史回测</h1>
                <p className="text-slate-500 dark:text-slate-400 mt-1">对历史日期逐一运行 AI 分析，评估决策准确率</p>
            </div>

            {/* Config Panel */}
            <div className="card space-y-4">
                <div className="flex items-center gap-2">
                    <FlaskConical className="w-5 h-5 text-purple-500" />
                    <h2 className="font-semibold text-slate-900 dark:text-slate-100">新建回测</h2>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="col-span-2 md:col-span-1">
                        <label className="block text-xs text-slate-500 mb-1">股票代码</label>
                        <input
                            value={symbol}
                            onChange={e => setSymbol(e.target.value)}
                            placeholder="如 600519.SH"
                            className="input w-full"
                            maxLength={20}
                        />
                    </div>
                    <div>
                        <label className="block text-xs text-slate-500 mb-1">开始日期</label>
                        <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="input w-full" />
                    </div>
                    <div>
                        <label className="block text-xs text-slate-500 mb-1">结束日期</label>
                        <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="input w-full" />
                    </div>
                    <div>
                        <label className="block text-xs text-slate-500 mb-1">持仓天数</label>
                        <input type="number" min={1} max={30} value={holdDays} onChange={e => setHoldDays(Number(e.target.value))} className="input w-full" />
                    </div>
                    <div>
                        <label className="block text-xs text-slate-500 mb-1">采样间隔（天）</label>
                        <input type="number" min={1} max={30} value={sampleInterval} onChange={e => setSampleInterval(Number(e.target.value))} className="input w-full" />
                    </div>
                </div>

                <div>
                    <label className="block text-xs text-slate-500 mb-2">选择分析师</label>
                    <div className="flex flex-wrap gap-2">
                        {ANALYSTS.map(a => (
                            <button
                                key={a.id}
                                onClick={() => toggleAnalyst(a.id)}
                                className={`px-3 py-1 text-sm rounded-full border transition-colors ${analysts.includes(a.id)
                                    ? 'bg-blue-500 border-blue-500 text-white'
                                    : 'border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-blue-400'
                                    }`}
                            >
                                {a.label}
                            </button>
                        ))}
                    </div>
                </div>

                <button
                    onClick={handleSubmit}
                    disabled={submitting || !symbol.trim() || analysts.length === 0}
                    className="btn-primary flex items-center gap-2 disabled:opacity-50"
                >
                    <Play className="w-4 h-4" />
                    {submitting ? '提交中...' : '开始回测'}
                </button>
            </div>

            {/* Jobs List */}
            {jobs.length > 0 && (
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <h2 className="font-semibold text-slate-900 dark:text-slate-100">回测任务</h2>
                        <button onClick={fetchJobs} className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors">
                            <RefreshCw className="w-4 h-4" />
                        </button>
                    </div>

                    {jobs.map(job => (
                        <div key={job.job_id} className="card">
                            {/* Job header */}
                            <div
                                className="flex items-center gap-3 cursor-pointer"
                                onClick={() => setExpandedJob(expandedJob === job.job_id ? null : job.job_id)}
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <span className="font-medium text-slate-900 dark:text-slate-100">{job.symbol}</span>
                                        <span className="text-xs text-slate-400">{job.start_date} ~ {job.end_date}</span>
                                        <StatusBadge status={job.status} />
                                    </div>
                                    {job.status === 'running' && (
                                        <div className="mt-1.5">
                                            <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                                                <span>{job.completed_dates} / {job.total_dates} 个交易日</span>
                                            </div>
                                            <div className="h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-blue-500 transition-all duration-500"
                                                    style={{ width: job.total_dates > 0 ? `${(job.completed_dates / job.total_dates) * 100}%` : '0%' }}
                                                />
                                            </div>
                                        </div>
                                    )}
                                    {job.status === 'completed' && job.stats && (
                                        <div className="flex flex-wrap gap-3 mt-1 text-xs">
                                            <span className="text-slate-500">信号数: <b className="text-slate-700 dark:text-slate-300">{job.stats.total_signals}</b></span>
                                            {job.stats.win_rate != null && (
                                                <span className="text-slate-500">胜率: <b className={job.stats.win_rate >= 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>{job.stats.win_rate}%</b></span>
                                            )}
                                            {job.stats.avg_return_pct != null && (
                                                <span className="text-slate-500">平均收益: <b className={returnColor(job.stats.avg_return_pct)}>{job.stats.avg_return_pct > 0 ? '+' : ''}{job.stats.avg_return_pct}%</b></span>
                                            )}
                                            {job.stats.best_return_pct != null && (
                                                <span className="text-slate-500">最佳: <b className="text-green-600 dark:text-green-400">+{job.stats.best_return_pct}%</b></span>
                                            )}
                                            {job.stats.worst_return_pct != null && (
                                                <span className="text-slate-500">最差: <b className="text-red-600 dark:text-red-400">{job.stats.worst_return_pct}%</b></span>
                                            )}
                                        </div>
                                    )}
                                </div>

                                <div className="flex items-center gap-1 shrink-0">
                                    <button
                                        onClick={(e) => handleDelete(job.job_id, e)}
                                        className="p-1.5 text-slate-400 hover:text-red-500 transition-colors"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                    {expandedJob === job.job_id ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                                </div>
                            </div>

                            {/* Expanded records */}
                            {expandedJob === job.job_id && job.records.length > 0 && (
                                <div className="mt-4 border-t border-slate-100 dark:border-slate-700 pt-4">
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="text-xs text-slate-500 border-b border-slate-100 dark:border-slate-700">
                                                    <th className="text-left pb-2 pr-4">日期</th>
                                                    <th className="text-left pb-2 pr-4">信号</th>
                                                    <th className="text-right pb-2 pr-4">买入价</th>
                                                    <th className="text-right pb-2 pr-4">卖出价</th>
                                                    <th className="text-right pb-2">收益</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
                                                {job.records.map((r, i) => (
                                                    <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                                                        <td className="py-2 pr-4 text-slate-600 dark:text-slate-400 font-mono text-xs">{r.date}</td>
                                                        <td className="py-2 pr-4">{actionBadge(r.action)}</td>
                                                        <td className="py-2 pr-4 text-right text-slate-600 dark:text-slate-400">
                                                            {r.entry_price != null ? `¥${r.entry_price}` : '—'}
                                                        </td>
                                                        <td className="py-2 pr-4 text-right text-slate-600 dark:text-slate-400">
                                                            {r.exit_price != null ? `¥${r.exit_price}` : '—'}
                                                        </td>
                                                        <td className={`py-2 text-right font-medium ${returnColor(r.return_pct)}`}>
                                                            {r.return_pct != null ? (
                                                                <span className="flex items-center justify-end gap-0.5">
                                                                    {r.return_pct > 0 ? <TrendingUp className="w-3 h-3" /> : r.return_pct < 0 ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                                                                    {r.return_pct > 0 ? '+' : ''}{r.return_pct}%
                                                                </span>
                                                            ) : r.error ? (
                                                                <span className="text-xs text-red-400" title={r.error}>错误</span>
                                                            ) : '—'}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

function StatusBadge({ status }: { status: BacktestJob['status'] }) {
    const map = {
        pending: 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400',
        running: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
        completed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
        failed: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
    }
    const labels = { pending: '等待中', running: '运行中', completed: '已完成', failed: '失败' }
    return <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${map[status]}`}>{labels[status]}</span>
}
