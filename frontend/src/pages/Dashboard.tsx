import { TrendingUp, Activity, FileText, CheckCircle, ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '@/services/api'
import { useAnalysisStore } from '@/stores/analysisStore'
import { useAuthStore } from '@/stores/authStore'
import type { Report, TrackingBoardResponse } from '@/types'

export default function Dashboard() {
    const { agents, isAnalyzing } = useAnalysisStore()
    const { user } = useAuthStore()
    const [reportTotal, setReportTotal] = useState<number | null>(null)
    const [recentReports, setRecentReports] = useState<Report[]>([])
    const [trackingBoard, setTrackingBoard] = useState<TrackingBoardResponse | null>(null)
    const [dashboardError, setDashboardError] = useState<string | null>(null)
    const navigate = useNavigate()

    const completedAgents = agents.filter(a => a.status === 'completed').length
    const inProgressAgents = agents.filter(a => a.status === 'in_progress').length

    useEffect(() => {
        if (!user?.id) return
        let cancelled = false

        api.getReports(undefined, 0, 5)
            .then(res => {
                if (cancelled) return
                setReportTotal(res.total)
                setRecentReports(res.reports)
            })
            .catch(error => {
                if (cancelled) return
                console.error('Failed to load recent reports:', error)
                setReportTotal(null)
                setDashboardError(prev => prev || (error instanceof Error ? error.message : '加载控制台数据失败'))
            })

        api.getDashboardTrackingBoard()
            .then(res => {
                if (cancelled) return
                setTrackingBoard(res)
            })
            .catch(error => {
                if (cancelled) return
                console.error('Failed to load tracking board summary:', error)
                setTrackingBoard(null)
                setDashboardError(prev => prev || (error instanceof Error ? error.message : '加载跟踪看板摘要失败'))
            })

        return () => {
            cancelled = true
        }
    }, [user?.id])

    return (
        <div className="space-y-6">
            {dashboardError && (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
                    {dashboardError}
                </div>
            )}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">控制台</h1>
                    <p className="mt-1 text-slate-500 dark:text-slate-400">
                        {user?.email ? `当前账户：${user.email}` : '欢迎使用 TradingAgents 智能分析系统'}
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatCard
                    icon={Activity}
                    label="Agent 状态"
                    value={`${inProgressAgents} 进行中`}
                    subValue={`${completedAgents} 已完成`}
                    color="blue"
                />
                <StatCard
                    icon={CheckCircle}
                    label="分析任务"
                    value={isAnalyzing ? '分析中' : '空闲'}
                    subValue={isAnalyzing ? '请稍候...' : '准备就绪'}
                    color={isAnalyzing ? 'orange' : 'green'}
                />
                <StatCard
                    icon={FileText}
                    label="累计报告"
                    value={reportTotal !== null ? `${reportTotal}` : '-'}
                    subValue="份分析报告"
                    color="purple"
                />
                <StatCard
                    icon={TrendingUp}
                    label="系统状态"
                    value="正常"
                    subValue="所有服务运行中"
                    color="green"
                />
            </div>

            <TrackingBoardSummary
                trackingBoard={trackingBoard}
                onOpen={() => navigate('/tracking-board')}
            />

            <div className="card">
                <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-slate-100">快速开始</h2>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <QuickActionCard
                        title="开始新分析"
                        description="输入股票代码，启动多 Agent 智能分析"
                        action="开始分析"
                        onClick={() => navigate('/analysis')}
                    />
                    <QuickActionCard
                        title="查看历史报告"
                        description="浏览已完成的分析报告"
                        action="查看报告"
                        onClick={() => navigate('/reports')}
                    />
                    <QuickActionCard
                        title="系统设置"
                        description="配置 API 和分析参数"
                        action="打开设置"
                        onClick={() => navigate('/settings')}
                    />
                </div>
            </div>

            <div className="card">
                <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">最近分析</h2>
                    {recentReports.length > 0 && (
                        <button
                            onClick={() => navigate('/reports')}
                            className="flex items-center gap-1 text-sm text-blue-600 hover:underline dark:text-blue-400"
                        >
                            查看全部 <ArrowRight className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                {recentReports.length === 0 ? (
                    <p className="py-8 text-center text-slate-400 dark:text-slate-500">
                        暂无分析记录，
                        <button onClick={() => navigate('/analysis')} className="text-blue-500 hover:underline">
                            开始新分析
                        </button>
                    </p>
                ) : (
                    <div className="divide-y divide-slate-100 dark:divide-slate-700">
                        {recentReports.map(report => {
                            const decisionColor = report.decision?.toUpperCase().includes('BUY') || report.decision?.includes('增持')
                                ? 'text-red-600 dark:text-red-400'
                                : report.decision?.toUpperCase().includes('SELL') || report.decision?.includes('减持')
                                    ? 'text-green-600 dark:text-green-400'
                                    : 'text-slate-500 dark:text-slate-400'
                            return (
                                <div
                                    key={report.id}
                                    className="mx-[-1rem] flex cursor-pointer items-center justify-between px-4 py-3 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
                                    onClick={() => navigate(`/reports?report=${report.id}`)}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-500/10">
                                            <FileText className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                                        </div>
                                        <div>
                                            <p className="font-medium text-slate-900 dark:text-slate-100 text-sm">{report.name || report.symbol}</p>
                                            <p className="text-xs text-slate-400 dark:text-slate-500">{report.trade_date}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <span className={`text-sm font-medium ${decisionColor}`}>
                                            {report.decision || '-'}
                                        </span>
                                        {report.confidence != null && (
                                            <span className="text-xs text-slate-400">{report.confidence}%</span>
                                        )}
                                        <p className="hidden text-xs text-slate-400 dark:text-slate-500 sm:block">
                                            {report.created_at ? new Date(report.created_at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                                        </p>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}
            </div>
        </div>
    )
}

function TrackingBoardSummary({
    trackingBoard,
    onOpen,
}: {
    trackingBoard: TrackingBoardResponse | null
    onOpen: () => void
}) {
    const itemCount = trackingBoard?.items.length ?? 0
    const quotedCount = trackingBoard?.items.filter(item => item.quote_source).length ?? 0
    const latestQuoteTime = trackingBoard?.items
        .map(item => item.quote_time)
        .filter((value): value is string => Boolean(value))[0] ?? null

    return (
        <div className="card">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">跟踪看板摘要</h2>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                        控制台仅展示元数据，持仓明细、区间图和交易建议请进入完整看板查看。
                    </p>
                </div>
                <button
                    type="button"
                    onClick={onOpen}
                    className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
                >
                    查看完整看板
                    <ArrowRight className="h-4 w-4" />
                </button>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                <MetaCard
                    label="跟踪标的"
                    value={`${itemCount} 只`}
                    subValue={trackingBoard?.account_id ? `账户 ${trackingBoard.account_id}` : '尚未读取到账户信息'}
                />
                <MetaCard
                    label="价格覆盖"
                    value={itemCount > 0 ? `${quotedCount}/${itemCount}` : '--'}
                    subValue={trackingBoard ? `刷新间隔 ${trackingBoard.refresh_interval_seconds}s` : '等待看板数据'}
                />
                <MetaCard
                    label="最近更新"
                    value={formatDashboardTime(latestQuoteTime)}
                    subValue={trackingBoard?.previous_trade_date ? `上一交易日 ${trackingBoard.previous_trade_date}` : '暂无交易日信息'}
                />
                <MetaCard
                    label="数据来源"
                    value="新浪财经"
                    subValue={itemCount > 0 ? '明细已收起，点击进入查看' : '同步后这里会显示摘要'}
                />
            </div>
        </div>
    )
}

function MetaCard({
    label,
    value,
    subValue,
}: {
    label: string
    value: string
    subValue: string
}) {
    return (
        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 dark:border-slate-700 dark:bg-slate-800/40">
            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{subValue}</p>
        </div>
    )
}

function formatDashboardTime(value?: string | null): string {
    if (!value) return '--'
    const parsed = new Date(value.replace(' ', 'T'))
    if (Number.isNaN(parsed.getTime())) return value
    return parsed.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    })
}

interface StatCardProps {
    icon: React.ComponentType<{ className?: string }>
    label: string
    value: string
    subValue: string
    color: 'blue' | 'green' | 'orange' | 'purple' | 'red'
}

function StatCard({ icon: Icon, label, value, subValue, color }: StatCardProps) {
    const colorClasses = {
        blue: 'bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400',
        green: 'bg-green-100 dark:bg-green-500/10 text-green-600 dark:text-green-400',
        orange: 'bg-orange-100 dark:bg-orange-500/10 text-orange-600 dark:text-orange-400',
        purple: 'bg-purple-100 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400',
        red: 'bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-400',
    }

    return (
        <div className="card card-hover">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
                    <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
                    <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{subValue}</p>
                </div>
                <div className={`rounded-lg p-3 ${colorClasses[color]}`}>
                    <Icon className="h-5 w-5" />
                </div>
            </div>
        </div>
    )
}

interface QuickActionCardProps {
    title: string
    description: string
    action: string
    onClick: () => void
}

function QuickActionCard({ title, description, action, onClick }: QuickActionCardProps) {
    return (
        <button
            onClick={onClick}
            className="block w-full rounded-lg border border-slate-200 bg-white p-4 text-left transition-all duration-200 hover:border-blue-400 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800/30 dark:hover:border-blue-500 dark:hover:bg-slate-800/50"
        >
            <h3 className="font-medium text-slate-900 dark:text-slate-100">{title}</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>
            <span className="mt-3 inline-block text-sm text-blue-600 dark:text-blue-400">
                {action} →
            </span>
        </button>
    )
}
