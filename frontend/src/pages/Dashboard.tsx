import { TrendingUp, Activity, FileText, CheckCircle, ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAnalysisStore } from '@/stores/analysisStore'
import { api } from '@/services/api'
import type { Report } from '@/types'
import { useAuthStore } from '@/stores/authStore'

export default function Dashboard() {
    const { agents, isAnalyzing } = useAnalysisStore()
    const { user } = useAuthStore()
    const [reportTotal, setReportTotal] = useState<number | null>(null)
    const [recentReports, setRecentReports] = useState<Report[]>([])
    const navigate = useNavigate()

    const completedAgents = agents.filter(a => a.status === 'completed').length
    const inProgressAgents = agents.filter(a => a.status === 'in_progress').length

    useEffect(() => {
        api.getReports(undefined, 0, 5)
            .then(res => {
                setReportTotal(res.total)
                setRecentReports(res.reports)
            })
            .catch(() => setReportTotal(null))
    }, [user?.id])

    return (
        <div className="space-y-6">
            {/* Welcome Section */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">控制台</h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-1">
                        {user?.email ? `当前账户：${user.email}` : '欢迎使用 TradingAgents 智能分析系统'}
                    </p>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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

            {/* Quick Actions */}
            <div className="card">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">快速开始</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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

            {/* Recent Reports */}
            <div className="card">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">最近分析</h2>
                    {recentReports.length > 0 && (
                        <button
                            onClick={() => navigate('/reports')}
                            className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                        >
                            查看全部 <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                    )}
                </div>

                {recentReports.length === 0 ? (
                    <p className="text-slate-400 dark:text-slate-500 text-center py-8">暂无分析记录，<button onClick={() => navigate('/analysis')} className="text-blue-500 hover:underline">开始新分析</button></p>
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
                                    className="flex items-center justify-between py-3 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 -mx-4 px-4 transition-colors"
                                    onClick={() => navigate(`/reports?report=${report.id}`)}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-500/10 flex items-center justify-center">
                                            <FileText className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                        </div>
                                        <div>
                                            <p className="font-medium text-slate-900 dark:text-slate-100 text-sm">{report.symbol}</p>
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
                                        <p className="text-xs text-slate-400 dark:text-slate-500 hidden sm:block">
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
                    <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{value}</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">{subValue}</p>
                </div>
                <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
                    <Icon className="w-5 h-5" />
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
            className="block w-full text-left p-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/30 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-all duration-200"
        >
            <h3 className="font-medium text-slate-900 dark:text-slate-100">{title}</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{description}</p>
            <span className="inline-block mt-3 text-sm text-blue-600 dark:text-blue-400">
                {action} →
            </span>
        </button>
    )
}
