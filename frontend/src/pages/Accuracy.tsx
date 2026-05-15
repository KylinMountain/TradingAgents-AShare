import { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, TrendingDown, CheckCircle, XCircle, RefreshCw, Target, Activity } from 'lucide-react'
import { api } from '@/services/api'

interface AccuracyStats {
    count: number
    correct: number
    accuracy: number
    avg_return: number
    max_return: number
    min_return: number
    buy_count: number
    buy_accuracy: number
    sell_count: number
    sell_accuracy: number
}

interface ConfidenceStats {
    high: AccuracyStats
    medium: AccuracyStats
    low: AccuracyStats
}

interface SymbolStats {
    [key: string]: {
        count: number
        accuracy_20d: number
        avg_return_20d: number
    }
}

interface AccuracySummary {
    total: number
    horizon_5d: AccuracyStats
    horizon_10d: AccuracyStats
    horizon_20d: AccuracyStats
    by_confidence: ConfidenceStats
    by_symbol: SymbolStats
    message?: string
}

interface BacktestItem {
    id: string
    report_id: string
    symbol: string
    signal_date: string
    decision: string
    confidence: number
    signal_price: number
    target_price: number | null
    return_5d: number | null
    correct_5d: boolean | null
    return_10d: number | null
    correct_10d: boolean | null
    return_20d: number | null
    correct_20d: boolean | null
}

function ProgressBar({ value, color }: { value: number; color: string }) {
    return (
        <div className="w-full bg-slate-100 rounded-full h-2">
            <div className={`h-2 rounded-full ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
        </div>
    )
}

function HorizonPanel({ label, stats, icon }: { label: string; stats: AccuracyStats; icon: React.ReactNode }) {
    if (!stats || stats.count === 0) return null
    return (
        <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
            <div className="flex items-center gap-3 mb-4">
                {icon}
                <h3 className="text-lg font-semibold text-slate-800">{label}</h3>
                <span className="text-sm text-slate-400">({stats.count}条信号)</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
                <div>
                    <div className="text-sm text-slate-500 mb-1">准确率</div>
                    <div className="flex items-center gap-2">
                        <span className="text-3xl font-bold text-slate-800">{stats.accuracy}%</span>
                        <span className="text-sm text-slate-400">({stats.correct}/{stats.count})</span>
                    </div>
                    <ProgressBar value={stats.accuracy} color={stats.accuracy >= 60 ? 'bg-emerald-500' : stats.accuracy >= 40 ? 'bg-amber-500' : 'bg-red-500'} />
                </div>
                <div>
                    <div className="text-sm text-slate-500 mb-1">平均收益</div>
                    <div className={`text-3xl font-bold ${stats.avg_return >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                        {stats.avg_return > 0 ? '+' : ''}{stats.avg_return}%
                    </div>
                </div>
            </div>
            <div className="grid grid-cols-4 gap-3 mt-4 pt-4 border-t border-slate-100">
                <div className="text-center">
                    <div className="text-xs text-slate-400">最大</div>
                    <div className="text-sm font-semibold text-emerald-600">+{stats.max_return}%</div>
                </div>
                <div className="text-center">
                    <div className="text-xs text-slate-400">最小</div>
                    <div className="text-sm font-semibold text-red-500">{stats.min_return}%</div>
                </div>
                <div className="text-center">
                    <div className="text-xs text-slate-400">买入准确</div>
                    <div className="text-sm font-semibold text-slate-700">{stats.buy_accuracy}%</div>
                </div>
                <div className="text-center">
                    <div className="text-xs text-slate-400">卖出准确</div>
                    <div className="text-sm font-semibold text-slate-700">{stats.sell_accuracy}%</div>
                </div>
            </div>
        </div>
    )
}

export default function Accuracy() {
    const [summary, setSummary] = useState<AccuracySummary | null>(null)
    const [details, setDetails] = useState<BacktestItem[]>([])
    const [loading, setLoading] = useState(true)
    const [backfilling, setBackfilling] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [message, setMessage] = useState<string | null>(null)

    const loadData = async () => {
        try {
            setLoading(true)
            const [sum, det] = await Promise.all([
                api.getAccuracySummary(),
                api.getAccuracyDetails(),
            ])
            setSummary(sum)
            setDetails(det.results || [])
            setError(null)
        } catch (e: any) {
            setError(e?.message || '加载数据失败')
        } finally {
            setLoading(false)
        }
    }

    const handleBackfill = async () => {
        try {
            setBackfilling(true)
            setMessage('正在对历史信号进行回测验证，可能需要几分钟...')
            await api.runAccuracyBackfill()
            setMessage('回测完成！正在刷新数据...')
            await loadData()
            setMessage(null)
        } catch (e: any) {
            setError(e?.message || '回测失败')
            setMessage(null)
        } finally {
            setBackfilling(false)
        }
    }

    useEffect(() => { loadData() }, [])

    return (
        <div className="max-w-6xl mx-auto p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-800">信号准确率</h1>
                    <p className="text-sm text-slate-500 mt-1">历史交易信号回测验证，评估各引擎分析准确度</p>
                </div>
                <button
                    onClick={handleBackfill}
                    disabled={backfilling}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors text-sm font-medium"
                >
                    <RefreshCw className={`w-4 h-4 ${backfilling ? 'animate-spin' : ''}`} />
                    {backfilling ? '回测中...' : '运行回测'}
                </button>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
            )}
            {message && (
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-700 px-4 py-3 rounded-lg text-sm">{message}</div>
            )}

            {loading ? (
                <div className="flex items-center justify-center py-20 text-slate-400">加载中...</div>
            ) : !summary || summary.total === 0 ? (
                <div className="bg-white rounded-xl p-12 shadow-sm border border-slate-100 text-center">
                    <BarChart3 className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-slate-600 mb-2">暂无回测数据</h3>
                    <p className="text-sm text-slate-400 mb-6">
                        {summary?.message || '完成至少一次股票分析并点击"运行回测"，系统会自动计算信号准确率'}
                    </p>
                    <button
                        onClick={handleBackfill}
                        disabled={backfilling}
                        className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium"
                    >
                        <RefreshCw className={`w-4 h-4 ${backfilling ? 'animate-spin' : ''}`} />
                        首次回测
                    </button>
                </div>
            ) : (
                <>
                    {/* Horizon comparison */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <HorizonPanel label="5日信号" stats={summary.horizon_5d} icon={<Activity className="w-5 h-5 text-blue-500" />} />
                        <HorizonPanel label="10日信号" stats={summary.horizon_10d} icon={<Target className="w-5 h-5 text-indigo-500" />} />
                        <HorizonPanel label="20日信号" stats={summary.horizon_20d} icon={<BarChart3 className="w-5 h-5 text-purple-500" />} />
                    </div>

                    {/* Confidence level analysis */}
                    {summary.by_confidence && summary.by_confidence.high.count > 0 && (
                        <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
                            <h3 className="text-lg font-semibold text-slate-800 mb-4">按置信度分析（10日维度）</h3>
                            <div className="grid grid-cols-3 gap-6">
                                <div className="text-center">
                                    <div className="text-sm text-slate-500 mb-1">高置信度 (≥70)</div>
                                    <div className={`text-2xl font-bold ${(summary.by_confidence.high.accuracy || 0) >= 60 ? 'text-emerald-600' : 'text-red-500'}`}>
                                        {summary.by_confidence.high.accuracy}%
                                    </div>
                                    <div className="text-xs text-slate-400">{summary.by_confidence.high.count}条</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-sm text-slate-500 mb-1">中置信度 (40-69)</div>
                                    <div className={`text-2xl font-bold ${(summary.by_confidence.medium.accuracy || 0) >= 60 ? 'text-emerald-600' : 'text-red-500'}`}>
                                        {summary.by_confidence.medium.accuracy}%
                                    </div>
                                    <div className="text-xs text-slate-400">{summary.by_confidence.medium.count}条</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-sm text-slate-500 mb-1">低置信度 (&lt;40)</div>
                                    <div className={`text-2xl font-bold ${(summary.by_confidence.low.accuracy || 0) >= 60 ? 'text-emerald-600' : 'text-red-500'}`}>
                                        {summary.by_confidence.low.accuracy}%
                                    </div>
                                    <div className="text-xs text-slate-400">{summary.by_confidence.low.count}条</div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Signal details table */}
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
                        <div className="px-6 py-4 border-b border-slate-100">
                            <h3 className="text-lg font-semibold text-slate-800">信号明细</h3>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-slate-100 bg-slate-50">
                                        <th className="text-left px-4 py-3 font-medium text-slate-500">股票</th>
                                        <th className="text-left px-4 py-3 font-medium text-slate-500">日期</th>
                                        <th className="text-center px-4 py-3 font-medium text-slate-500">信号</th>
                                        <th className="text-center px-4 py-3 font-medium text-slate-500">置信度</th>
                                        <th className="text-right px-4 py-3 font-medium text-slate-500">信号价</th>
                                        <th className="text-right px-4 py-3 font-medium text-slate-500">目标价</th>
                                        <th className="text-center px-4 py-3 font-medium text-slate-500">5日</th>
                                        <th className="text-center px-4 py-3 font-medium text-slate-500">10日</th>
                                        <th className="text-center px-4 py-3 font-medium text-slate-500">20日</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {details.map((item) => (
                                        <tr key={item.id} className="border-b border-slate-50 hover:bg-slate-50/50">
                                            <td className="px-4 py-3 font-medium text-slate-700">{item.symbol}</td>
                                            <td className="px-4 py-3 text-slate-500">{item.signal_date}</td>
                                            <td className="px-4 py-3 text-center">
                                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                                                    item.decision === 'BUY' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                                                }`}>
                                                    {item.decision === 'BUY' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                                    {item.decision}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 text-center">
                                                <span className={`text-sm font-medium ${
                                                    item.confidence >= 70 ? 'text-emerald-600' : item.confidence >= 40 ? 'text-amber-600' : 'text-red-500'
                                                }`}>{item.confidence}</span>
                                            </td>
                                            <td className="px-4 py-3 text-right text-slate-700">{item.signal_price?.toFixed(2)}</td>
                                            <td className="px-4 py-3 text-right text-slate-500">{item.target_price?.toFixed(2) || '-'}</td>
                                            {(['5d', '10d', '20d'] as const).map((h) => {
                                                const ret = item[`return_${h}` as keyof BacktestItem] as number | null
                                                const correct = item[`correct_${h}` as keyof BacktestItem] as boolean | null
                                                if (ret === null) return <td key={h} className="px-4 py-3 text-center text-slate-300">-</td>
                                                return (
                                                    <td key={h} className="px-4 py-3 text-center">
                                                        <div className="flex items-center justify-center gap-1">
                                                            {correct ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500" /> : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                                                            <span className={ret >= 0 ? 'text-emerald-600' : 'text-red-500'}>
                                                                {ret > 0 ? '+' : ''}{ret}%
                                                            </span>
                                                        </div>
                                                    </td>
                                                )
                                            })}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {details.length === 0 && (
                                <div className="text-center py-8 text-slate-400 text-sm">暂无明细数据</div>
                            )}
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
