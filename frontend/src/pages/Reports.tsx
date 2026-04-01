import { FileText, Download, Trash2, Search, ChevronLeft, ChevronRight, Loader2, History, Clock3 } from 'lucide-react'
import { useState, useEffect, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import TaskProgressBanner from '@/components/TaskProgressBanner'
import { api } from '@/services/api'
import type { Report, ReportDetail } from '@/types'
import DecisionCard from '@/components/DecisionCard'
import ReportViewer from '@/components/ReportViewer'
import RiskRadar from '@/components/RiskRadar'
import KeyMetrics from '@/components/KeyMetrics'
import { useAuthStore } from '@/stores/authStore'
import { advanceProgress, getReportRunProgress, getTaskStatusLabel } from '@/utils/progressFeedback'

type ProgressState = {
    status: 'idle' | 'loading' | 'success' | 'error'
    progress: number
    detail: string | null
}

const IDLE_PROGRESS: ProgressState = {
    status: 'idle',
    progress: 0,
    detail: null,
}

const parseDecision = (decisionText?: string): { action: 'add' | 'reduce' | 'hold'; label: string } => {
    if (!decisionText) return { action: 'hold', label: '观望' }
    const text = decisionText.toUpperCase()
    if (text.includes('BUY') || text.includes('增持') || text.includes('买入')) return { action: 'add', label: '增持' }
    if (text.includes('SELL') || text.includes('减持') || text.includes('卖出')) return { action: 'reduce', label: '减持' }
    return { action: 'hold', label: '持有' }
}

const getDecisionColor = (decision?: string) => {
    const { action } = parseDecision(decision)
    if (action === 'add') return 'text-red-600 dark:text-red-400'
    if (action === 'reduce') return 'text-green-600 dark:text-green-400'
    return 'text-slate-600 dark:text-slate-400'
}

function getQueueHint(report: Pick<Report, 'status' | 'waiting_ahead_count' | 'scheduled_running_count' | 'scheduled_concurrency_limit'>): string | null {
    if (report.status !== 'pending') return null

    const waitingAhead = report.waiting_ahead_count ?? 0
    const runningCount = report.scheduled_running_count
    const limit = report.scheduled_concurrency_limit

    if (runningCount != null && limit != null) {
        return `前方还有 ${waitingAhead} 项等待，当前 ${runningCount}/${limit} 个任务执行中`
    }

    return `前方还有 ${waitingAhead} 项等待`
}

function ActiveReportStatus({ report }: { report: Report }) {
    const progress = getReportRunProgress({
        status: report.status,
        createdAt: report.created_at,
    })
    const isPending = report.status === 'pending'
    const label = isPending ? '排队中' : '分析中'
    const toneCls = isPending
        ? 'text-slate-500 dark:text-slate-300'
        : 'text-blue-600 dark:text-blue-300'
    const barCls = isPending
        ? 'from-slate-400 via-slate-500 to-slate-600'
        : 'from-cyan-500 via-blue-500 to-indigo-500'
    const queueHint = getQueueHint(report)

    return (
        <div className="min-w-[148px] space-y-2">
            <div className={`flex items-center gap-1.5 text-xs font-medium ${toneCls}`}>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>{label}</span>
                <span className="ml-auto tabular-nums">{progress}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                <div
                    className={`h-full rounded-full bg-gradient-to-r ${barCls} transition-[width] duration-700 ease-out`}
                    style={{ width: `${progress}%` }}
                />
            </div>
            {queueHint ? (
                <p className="text-[11px] leading-4 text-slate-400">{queueHint}</p>
            ) : null}
        </div>
    )
}

function ActiveDetailStatusCard({ report }: { report: ReportDetail }) {
    const progress = getReportRunProgress({
        status: report.status,
        createdAt: report.created_at,
    })
    const isPending = report.status === 'pending'
    const title = isPending ? '排队处理中...' : '深度分析中...'
    const queueHint = getQueueHint(report)
    const detail = isPending
        ? (queueHint || '任务已进入队列，正在等待分析资源。')
        : '正在汇总各路 Agent 的观点，请稍后。'

    return (
        <div className="card h-full min-h-[320px] p-8">
            <div className="flex h-full flex-col justify-center">
                <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 text-blue-500 dark:bg-blue-500/10 dark:text-blue-300">
                    <Clock3 className="h-7 w-7" />
                </div>
                <div className="mx-auto w-full max-w-[280px] text-center">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">{title}</h3>
                    <p className="mt-2 text-sm text-slate-500">{detail}</p>
                    <div className="mt-6 text-left">
                        <div className="mb-2 flex items-center justify-between text-sm">
                            <span className="font-medium text-slate-600 dark:text-slate-300">当前进度</span>
                            <span className="font-semibold tabular-nums text-blue-600 dark:text-blue-300">{progress}%</span>
                        </div>
                        <div className="h-2.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                            <div
                                className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-500 transition-[width] duration-700 ease-out"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    </div>
                    <p className="mt-4 text-xs text-slate-400">
                        页面会自动刷新任务状态，完成后这里会直接切换为分析结果。
                    </p>
                </div>
            </div>
        </div>
    )
}

const formatScheduledFrequency = (frequency?: string) => {
    if (frequency === 'trading_day') return '交易日'
    if (frequency === 'daily') return '每天'
    if (frequency === 'weekly') return '每周'
    if (frequency === 'monthly') return '每月'
    return frequency || '-'
}

const renderStatusBadge = (report: Report) => {
    switch (report.status) {
        case 'pending':
            return <ActiveReportStatus report={report} />
        case 'running':
            return <ActiveReportStatus report={report} />
        case 'failed':
            return (
                <div className="group relative flex items-center gap-1.5 text-rose-500" title={report.error?.split('\n')[0]}>
                    <div className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                    <span className="text-xs font-medium">任务失败</span>
                </div>
            )
        default:
            const { label } = parseDecision(report.decision)
            return (
                <span className={`font-medium ${getDecisionColor(report.decision)}`}>
                    {label}
                </span>
            )
    }
}

function exportReport(report: ReportDetail) {
    const sections = [
        { key: 'market_report', title: '市场分析报告' },
        { key: 'sentiment_report', title: '舆情分析报告' },
        { key: 'news_report', title: '新闻分析报告' },
        { key: 'fundamentals_report', title: '基本面分析报告' },
        { key: 'investment_plan', title: '研究团队决策' },
        { key: 'trader_investment_plan', title: '交易团队计划' },
        { key: 'final_trade_decision', title: '最终交易决策' },
    ]
    const text = sections
        .filter(s => report[s.key as keyof ReportDetail])
        .map(s => `## ${s.title}\n\n${report[s.key as keyof ReportDetail]}`)
        .join('\n\n---\n\n')
    const blob = new Blob([text], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `analysis-${report.symbol}-${report.trade_date}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}

export default function Reports() {
    const { user } = useAuthStore()
    const [searchParams, setSearchParams] = useSearchParams()
    const PAGE_SIZE = 20
    const [searchQuery, setSearchQuery] = useState('')
    const [page, setPage] = useState(0)
    const [reports, setReports] = useState<Report[]>([])
    const [total, setTotal] = useState(0)
    const [selectedReport, setSelectedReport] = useState<ReportDetail | null>(null)
    const [loading, setLoading] = useState(false)
    const [detailLoading, setDetailLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [deleting, setDeleting] = useState<string | null>(null)
    const [batchDeleting, setBatchDeleting] = useState(false)
    const [symbolHistory, setSymbolHistory] = useState<Report[]>([])
    const [listProgress, setListProgress] = useState<ProgressState>(IDLE_PROGRESS)
    const [detailProgress, setDetailProgress] = useState<ProgressState>(IDLE_PROGRESS)
    const [selectedReportIds, setSelectedReportIds] = useState<string[]>([])

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

    useEffect(() => {
        if (listProgress.status !== 'loading') return

        const timer = window.setInterval(() => {
            setListProgress((prev) => prev.status === 'loading'
                ? { ...prev, progress: advanceProgress(prev.progress) }
                : prev)
        }, 180)

        return () => window.clearInterval(timer)
    }, [listProgress.status])

    useEffect(() => {
        if (detailProgress.status !== 'loading') return

        const timer = window.setInterval(() => {
            setDetailProgress((prev) => prev.status === 'loading'
                ? { ...prev, progress: advanceProgress(prev.progress) }
                : prev)
        }, 180)

        return () => window.clearInterval(timer)
    }, [detailProgress.status])

    const fetchReports = useCallback(async (targetPage: number, options?: { silent?: boolean }) => {
        const silent = options?.silent === true
        if (!silent) {
            setLoading(true)
            setError(null)
            setListProgress({
                status: 'loading',
                progress: 12,
                detail: `正在加载第 ${targetPage + 1} 页报告列表...`,
            })
        }
        try {
            const response = await api.getReports(undefined, targetPage * PAGE_SIZE, PAGE_SIZE)
            setReports(response.reports)
            setTotal(response.total)
            if (!silent) {
                setListProgress({
                    status: 'success',
                    progress: 100,
                    detail: `已获取 ${response.reports.length} 条报告记录`,
                })
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : '获取报告失败'
            if (!silent) {
                setError(message)
                setListProgress({
                    status: 'error',
                    progress: 100,
                    detail: message,
                })
            }
        } finally {
            if (!silent) {
                setLoading(false)
            }
        }
    }, [])

    useEffect(() => { fetchReports(page) }, [fetchReports, page])

    const handleDelete = async (e: React.MouseEvent, reportId: string) => {
        e.stopPropagation()
        if (!confirm('确定要删除这份报告吗？')) return
        setDeleting(reportId)
        try {
            await api.deleteReport(reportId)
            setReports(prev => prev.filter(r => r.id !== reportId))
            setSelectedReportIds(prev => prev.filter(id => id !== reportId))
            setTotal(prev => {
                const newTotal = prev - 1
                // Go to prev page if current page is now empty
                if (reports.length === 1 && page > 0) setPage(p => p - 1)
                return newTotal
            })
        } catch (err) {
            alert(err instanceof Error ? err.message : '删除失败')
        } finally {
            setDeleting(null)
        }
    }

    const toggleSelectReport = (reportId: string) => {
        setSelectedReportIds(prev => prev.includes(reportId)
            ? prev.filter(id => id !== reportId)
            : [...prev, reportId])
    }

    const toggleSelectAllFiltered = () => {
        if (allFilteredSelected) {
            setSelectedReportIds(prev => prev.filter(id => !filteredReportIds.includes(id)))
            return
        }
        setSelectedReportIds(prev => Array.from(new Set([...prev, ...filteredReportIds])))
    }

    const handleBatchDelete = async () => {
        if (!hasSelectedReports) {
            alert('请先勾选要批量删除的报告')
            return
        }
        if (!confirm(`确定要删除选中的 ${selectedCount} 份报告吗？`)) return

        setBatchDeleting(true)
        try {
            const response = await api.deleteReportsBatch(selectedReportIds)
            const deletedIdSet = new Set(response.deleted_ids)
            setReports(prev => prev.filter(report => !deletedIdSet.has(report.id)))
            setSelectedReportIds([])
            setTotal(prev => Math.max(0, prev - response.deleted_ids.length))
            if (response.deleted_ids.length > 0 && reports.length === response.deleted_ids.length && page > 0) {
                setPage(prev => prev - 1)
            }
            if (response.missing_ids.length > 0) {
                alert(`已删除 ${response.deleted_ids.length} 份报告，另有 ${response.missing_ids.length} 份不存在或已被删除。`)
            }
        } catch (err) {
            alert(err instanceof Error ? err.message : '批量删除失败')
        } finally {
            setBatchDeleting(false)
        }
    }

    const loadReportDetail = useCallback(async (
        reportId: string,
        options?: { silent?: boolean; preserveHistory?: boolean },
    ) => {
        const silent = options?.silent === true
        const preserveHistory = options?.preserveHistory === true

        if (!silent) {
            setDetailLoading(true)
            if (!preserveHistory) {
                setSymbolHistory([])
            }
            setDetailProgress({
                status: 'loading',
                progress: 14,
                detail: preserveHistory ? '正在恢复你刚刚打开的报告...' : '正在打开报告详情...',
            })
        }

        try {
            const detail = await api.getReport(reportId)
            setSelectedReport(detail)
            setReports(prev => prev.map(report => report.id === detail.id ? { ...report, ...detail } : report))

            if (!silent || !preserveHistory) {
                const history = await api.getReports(detail.symbol, 0, 20)
                setSymbolHistory(history.reports)
            } else {
                setSymbolHistory(prev => prev.map(report => report.id === detail.id ? { ...report, ...detail } : report))
            }

            if (!silent) {
                setSearchParams({ report: reportId })
                setDetailProgress({
                    status: 'success',
                    progress: 100,
                    detail: `${detail.name || detail.symbol} 报告已就绪`,
                })
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : '获取报告详情失败'
            if (!silent) {
                setDetailProgress({
                    status: 'error',
                    progress: 100,
                    detail: message,
                })
                alert(message)
            }
            throw err
        } finally {
            if (!silent) {
                setDetailLoading(false)
            }
        }
    }, [setSearchParams])

    const handleSelectReport = async (report: Pick<Report, 'id' | 'symbol'>) => {
        try {
            await loadReportDetail(report.id)
        } catch {}
    }

    useEffect(() => {
        const reportId = searchParams.get('report')
        if (!reportId || selectedReport?.id === reportId) return
        void loadReportDetail(reportId, { preserveHistory: true })
    }, [loadReportDetail, searchParams, selectedReport?.id])

    const filteredReports = reports.filter(r => {
        const q = searchQuery.toLowerCase()
        return r.symbol.toLowerCase().includes(q) || (r.name?.toLowerCase().includes(q) ?? false)
    })
    const filteredReportIds = useMemo(() => filteredReports.map(report => report.id), [filteredReports])
    const selectedReportIdSet = useMemo(() => new Set(selectedReportIds), [selectedReportIds])
    const selectedCount = selectedReportIds.length
    const hasSelectedReports = selectedCount > 0
    const allFilteredSelected = filteredReportIds.length > 0 && filteredReportIds.every(id => selectedReportIdSet.has(id))
    const hasActiveReport = reports.some(report => report.status === 'pending' || report.status === 'running')

    useEffect(() => {
        const currentPageIds = new Set(reports.map(report => report.id))
        setSelectedReportIds(prev => prev.filter(id => currentPageIds.has(id)))
    }, [reports])

    useEffect(() => {
        if (loading || detailLoading || selectedReport || !hasActiveReport) return

        const timer = window.setInterval(() => {
            void fetchReports(page, { silent: true })
        }, 4000)

        return () => window.clearInterval(timer)
    }, [detailLoading, fetchReports, hasActiveReport, loading, page, selectedReport])

    useEffect(() => {
        if (!selectedReport || detailLoading) return
        if (selectedReport.status !== 'pending' && selectedReport.status !== 'running') return

        const timer = window.setInterval(() => {
            void loadReportDetail(selectedReport.id, { silent: true, preserveHistory: true })
        }, 4000)

        return () => window.clearInterval(timer)
    }, [detailLoading, loadReportDetail, selectedReport])

    // ─── 详情视图 ────────────────────────────────────────────────────────────
    if (detailLoading) {
        return (
            <div className="space-y-6">
                <TaskProgressBanner
                    status={detailProgress.status}
                    progress={detailProgress.progress}
                    label={getTaskStatusLabel('report-detail', detailProgress.status === 'idle' ? 'loading' : detailProgress.status)}
                    detail={detailProgress.detail}
                />
                <div className="flex items-center justify-center py-24">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                </div>
            </div>
        )
    }

    if (selectedReport) {
        const { action } = parseDecision(selectedReport.decision)
        const selectedReportProgressStatus = selectedReport.status === 'pending' || selectedReport.status === 'running'
            ? 'loading'
            : selectedReport.status === 'failed'
                ? 'error'
                : 'success'
        const selectedReportProgressValue = getReportRunProgress({
            status: selectedReport.status,
            createdAt: selectedReport.created_at,
        })
        const selectedReportProgressDetail = selectedReport.status === 'failed'
            ? (selectedReport.error || '任务执行失败')
            : selectedReport.status === 'completed'
                ? `${selectedReport.name || selectedReport.symbol} 报告已完成`
                : selectedReport.status === 'pending'
                    ? (getQueueHint(selectedReport) || '任务排队中 · 进度会自动刷新')
                    : '多智能体正在协同分析 · 进度会自动刷新'

        return (
            <div className="space-y-6">
                <TaskProgressBanner
                    status={selectedReportProgressStatus}
                    progress={selectedReportProgressValue}
                    label={selectedReportProgressStatus === 'loading'
                        ? (selectedReport.status === 'pending' ? '报告任务排队中...' : '报告生成中...')
                        : getTaskStatusLabel('report-detail', selectedReportProgressStatus)}
                    detail={selectedReportProgressDetail}
                />
                {/* 返回按钮 + 标题 */}
                <div className="flex items-center gap-4">

                    <button
                        onClick={() => {
                            setSelectedReport(null)
                            setSearchParams({})
                        }}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                    >
                        <ChevronLeft className="w-4 h-4" />
                        返回列表
                    </button>
                    <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                        {selectedReport.name || selectedReport.symbol} 分析报告
                        {selectedReport.name && selectedReport.name !== selectedReport.symbol && (
                            <span className="ml-2 text-base font-normal text-slate-400">{selectedReport.symbol}</span>
                        )}
                    </h1>
                    <button
                        onClick={() => exportReport(selectedReport)}
                        className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                    >
                        <Download className="w-4 h-4" />
                        导出 Markdown
                    </button>
                </div>

                {/* 元信息 */}
                <div className="flex items-center gap-4 text-sm text-slate-500">
                    <span>分析日期：{selectedReport.trade_date}</span>
                    <span>生成时间：{selectedReport.created_at ? new Date(selectedReport.created_at).toLocaleString('zh-CN') : '-'}</span>
                    {selectedReport.report_source === 'scheduled' && (
                        <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                            定时报告 · {formatScheduledFrequency(selectedReport.scheduled_frequency)}
                        </span>
                    )}
                </div>

                {/* 历史决策时间线 */}
                {symbolHistory.length > 1 && (
                    <div className="card">
                        <div className="flex items-center gap-2 mb-3">
                            <History className="w-4 h-4 text-slate-400" />
                            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">{selectedReport.name || selectedReport.symbol} 历史决策</h3>
                        </div>
                        <div className="flex items-center gap-2 overflow-x-auto pb-1">
                            {symbolHistory.slice().reverse().map(r => {
                                const { action: a } = parseDecision(r.decision)
                                const color = a === 'add' ? 'bg-red-500' : a === 'reduce' ? 'bg-green-500' : 'bg-slate-400'
                                const isCurrent = r.id === selectedReport.id
                                return (
                                    <button
                                        key={r.id}
                                        onClick={() => !isCurrent && handleSelectReport(r)}
                                        className={`flex flex-col items-center gap-1 shrink-0 px-2 py-1.5 rounded-lg transition-colors ${isCurrent ? 'bg-blue-50 dark:bg-blue-500/10' : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'}`}
                                    >
                                        <div className={`w-3 h-3 rounded-full ${color}`} />
                                        <span className="text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap">{r.trade_date}</span>
                                        {r.confidence != null && <span className="text-xs text-slate-400">{r.confidence}%</span>}
                                    </button>
                                )
                            })}
                        </div>
                    </div>
                )}

                {/* 主体：概要卡片 + 报告全文 */}
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
                    {selectedReport.status === 'completed' ? (
                        <DecisionCard
                            symbol={selectedReport.symbol}
                            name={selectedReport.name}
                            decision={action}
                            direction={selectedReport.direction}
                            confidence={selectedReport.confidence ?? undefined}
                            targetPrice={selectedReport.target_price ?? undefined}
                            stopLoss={selectedReport.stop_loss_price ?? undefined}
                            reasoning={selectedReport.final_trade_decision?.slice(0, 300) ?? undefined}
                        />
                    ) : selectedReport.status === 'failed' ? (
                        <div className="card h-full flex flex-col items-center justify-center p-8 text-center min-h-[320px]">
                            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-500 dark:bg-rose-500/10 dark:text-rose-300">
                                <Trash2 className="h-6 w-6" />
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">分析失败</h3>
                            <p className="mt-2 max-w-[240px] text-sm text-slate-500">
                                {selectedReport.error?.slice(0, 80) || '未知错误'}
                            </p>
                        </div>
                    ) : (
                        <ActiveDetailStatusCard report={selectedReport} />
                    )}
                    <RiskRadar items={selectedReport.risk_items ?? undefined} />
                    <KeyMetrics items={selectedReport.key_metrics ?? undefined} />
                </div>

                <div className="card">
                    <ReportViewer reportData={selectedReport} />
                </div>
            </div>
        )
    }

    // ─── 列表视图 ────────────────────────────────────────────────────────────
    return (
        <div className="space-y-6">
            <TaskProgressBanner
                status={listProgress.status}
                progress={listProgress.progress}
                label={getTaskStatusLabel('reports', listProgress.status === 'idle' ? 'success' : listProgress.status)}
                detail={listProgress.detail}
            />
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">历史报告</h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-1">
                        {user?.email ? `${user.email} 的私有分析记录 · 共 ${total} 份` : `共 ${total} 份分析报告`}
                    </p>
                </div>
            </div>

            {/* 搜索 */}
            <div className="card">
                <div className="flex flex-col gap-4">
                    <div className="relative max-w-md">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={e => setSearchQuery(e.target.value)}
                            placeholder="搜索股票代码或名称..."
                            className="input w-full pl-10"
                        />
                    </div>

                    <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-800/50">
                        <div className="flex flex-wrap items-center gap-3">
                            <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                                <input
                                    type="checkbox"
                                    checked={allFilteredSelected}
                                    onChange={toggleSelectAllFiltered}
                                    disabled={filteredReports.length === 0 || batchDeleting}
                                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                                />
                                全选当前页
                            </label>
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-sm ring-1 ring-slate-200 dark:bg-slate-900 dark:text-slate-200 dark:ring-slate-700">
                                已选 {selectedCount} 份
                            </span>
                            <button
                                type="button"
                                onClick={() => setSelectedReportIds([])}
                                disabled={!hasSelectedReports || batchDeleting}
                                className="text-xs text-slate-500 transition-colors hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40 dark:text-slate-400 dark:hover:text-slate-200"
                            >
                                清空选择
                            </button>
                            <button
                                type="button"
                                onClick={() => void handleBatchDelete()}
                                disabled={!hasSelectedReports || batchDeleting}
                                className="ml-auto inline-flex items-center gap-2 rounded-xl bg-rose-500 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-rose-600 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                {batchDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                                批量删除
                            </button>
                        </div>
                        {!hasSelectedReports && (
                            <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                                勾选报告后，可以对当前页结果进行批量删除。
                            </p>
                        )}
                    </div>
                </div>
            </div>

            {/* 加载中 */}
            {loading && (
                <div className="card py-12">
                    <div className="flex flex-col items-center gap-4">
                        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                        <p className="text-slate-500">加载报告中...</p>
                    </div>
                </div>
            )}

            {/* 错误 */}
            {error && !loading && (
                <div className="card py-12 text-center">
                    <p className="text-red-500 mb-4">{error}</p>
                    <button
                        onClick={() => fetchReports(page)}
                        className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                    >
                        重试
                    </button>
                </div>
            )}

            {/* 报告表格 */}
            {!loading && !error && (
                <div className="card overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-slate-200 dark:border-slate-700">
                                    <th className="py-3 px-4 text-left">
                                        <input
                                            type="checkbox"
                                            checked={allFilteredSelected}
                                            onChange={toggleSelectAllFiltered}
                                            disabled={filteredReports.length === 0 || batchDeleting}
                                            className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                                            aria-label="全选当前页报告"
                                        />
                                    </th>
                                    {['股票', '分析日期', '决策建议', '置信度', '目标价/止损价', '生成时间', '操作'].map(h => (
                                        <th key={h} className={`py-3 px-4 text-sm font-medium text-slate-500 dark:text-slate-400 ${h === '操作' ? 'text-right' : 'text-left'}`}>
                                            {h}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                                {filteredReports.map((report) => {
                                    return (
                                        <tr
                                            key={report.id}
                                            className={`transition-colors cursor-pointer ${selectedReportIdSet.has(report.id)
                                                ? 'bg-blue-50/60 dark:bg-blue-500/10'
                                                : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
                                            }`}
                                            onClick={() => handleSelectReport(report)}
                                        >
                                            <td className="py-3 px-4">
                                                <input
                                                    type="checkbox"
                                                    checked={selectedReportIdSet.has(report.id)}
                                                    onChange={() => toggleSelectReport(report.id)}
                                                    onClick={e => e.stopPropagation()}
                                                    disabled={batchDeleting}
                                                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                                                    aria-label={`选择报告 ${report.name || report.symbol}`}
                                                />
                                            </td>
                                            <td className="py-3 px-4">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-500/10 flex items-center justify-center">
                                                        <FileText className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                                    </div>
                                                    <div>
                                                        <p className="font-medium text-slate-900 dark:text-slate-100">{report.name || report.symbol}</p>
                                                        {report.name && report.name !== report.symbol && (
                                                            <p className="text-xs text-slate-400 dark:text-slate-500">{report.symbol}</p>
                                                        )}
                                                        {report.report_source === 'scheduled' && (
                                                            <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-0.5">
                                                                定时任务 · {formatScheduledFrequency(report.scheduled_frequency)}
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="py-3 px-4 text-slate-600 dark:text-slate-400">{report.trade_date}</td>
                                            <td className="py-3 px-4">
                                                {renderStatusBadge(report)}
                                            </td>
                                            <td className="py-3 px-4">
                                                {report.confidence != null ? (
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-16 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full bg-blue-500 rounded-full"
                                                                style={{ width: `${report.confidence}%` }}
                                                            />
                                                        </div>
                                                        <span className="text-sm text-slate-600 dark:text-slate-400">{report.confidence}%</span>
                                                    </div>
                                                ) : (
                                                    <span className="text-slate-400">-</span>
                                                )}
                                            </td>
                                            <td className="py-3 px-4 text-sm text-slate-600 dark:text-slate-400">
                                                {report.target_price != null ? `¥${report.target_price}` : '-'} / {report.stop_loss_price != null ? `¥${report.stop_loss_price}` : '-'}
                                            </td>
                                            <td className="py-3 px-4 text-sm text-slate-500 dark:text-slate-400">
                                                {report.created_at ? new Date(report.created_at).toLocaleString('zh-CN') : '-'}
                                            </td>
                                            <td className="py-3 px-4">
                                                <div className="flex items-center justify-end gap-2">
                                                    <button
                                                        className="p-2 text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                                                        onClick={e => { e.stopPropagation(); handleSelectReport(report) }}
                                                        title="查看详情"
                                                    >
                                                        <FileText className="w-4 h-4" />
                                                    </button>
                                                    <button
                                                        className="p-2 text-slate-400 hover:text-red-600 dark:hover:text-red-400 transition-colors disabled:opacity-50"
                                                        onClick={e => handleDelete(e, report.id)}
                                                        disabled={deleting === report.id || batchDeleting}
                                                        title="删除"
                                                    >
                                                        {deleting === report.id
                                                            ? <Loader2 className="w-4 h-4 animate-spin" />
                                                            : <Trash2 className="w-4 h-4" />
                                                        }
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>

                    {filteredReports.length === 0 && (
                        <div className="text-center py-12">
                            <FileText className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-4" />
                            <p className="text-slate-500 dark:text-slate-400">
                                {searchQuery ? '没有匹配的报告' : '暂无报告'}
                            </p>
                            <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
                                在分析页面生成新的报告
                            </p>
                        </div>
                    )}

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 dark:border-slate-700">
                            <span className="text-sm text-slate-500 dark:text-slate-400">
                                第 {page + 1} / {totalPages} 页，共 {total} 条
                            </span>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setPage(p => p - 1)}
                                    disabled={page === 0}
                                    className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                >
                                    <ChevronLeft className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={() => setPage(p => p + 1)}
                                    disabled={page >= totalPages - 1}
                                    className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                >
                                    <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
