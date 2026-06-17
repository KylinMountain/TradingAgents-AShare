import { useEffect, useState } from 'react'
import { Brain, TrendingUp, TrendingDown, AlertTriangle, Loader2, RefreshCw } from 'lucide-react'
import type { StrategyDecisionResponse } from '@/types'
import { api } from '@/services/api'

interface Props {
    symbol: string
    name?: string
}

const actionConfig: Record<string, { label: string; color: string; icon: typeof TrendingUp }> = {
    '加仓': { label: '加仓', color: 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/30', icon: TrendingUp },
    '重仓跟进': { label: '重仓跟进', color: 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/30', icon: TrendingUp },
    '减仓': { label: '减仓', color: 'bg-orange-100 dark:bg-orange-500/20 text-orange-700 dark:text-orange-400 border-orange-200 dark:border-orange-500/30', icon: TrendingDown },
    '清仓': { label: '清仓', color: 'bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-500/30', icon: AlertTriangle },
    '观望': { label: '观望', color: 'bg-slate-100 dark:bg-slate-700/50 text-slate-700 dark:text-slate-400 border-slate-200 dark:border-slate-600', icon: Brain },
    '机会进场': { label: '机会进场', color: 'bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/30', icon: TrendingUp },
    '风险回避': { label: '风险回避', color: 'bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-500/30', icon: AlertTriangle },
}

const phaseColors: Record<string, string> = {
    '吸筹': 'text-green-600 dark:text-green-400',
    '底部筑底': 'text-green-600 dark:text-green-400',
    '上涨趋势': 'text-red-600 dark:text-red-400',
    '顶部筑顶': 'text-orange-600 dark:text-orange-400',
    '派发': 'text-orange-600 dark:text-orange-400',
    '下跌趋势': 'text-red-600 dark:text-red-400',
}

const confidenceColors: Record<string, string> = {
    '高': 'bg-green-100 dark:bg-green-800/30 text-green-700 dark:text-green-400',
    '中': 'bg-yellow-100 dark:bg-yellow-800/30 text-yellow-700 dark:text-yellow-400',
    '低': 'bg-slate-100 dark:bg-slate-800/30 text-slate-600 dark:text-slate-400',
}

export default function StrategyDecisionCard({ symbol, name = '' }: Props) {
    const [data, setData] = useState<StrategyDecisionResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleAnalyze = async () => {
        setLoading(true)
        setError(null)
        try {
            const result = await api.getStrategyDecision(symbol)
            setData(result)
        } catch (e: any) {
            setError(e?.message || '分析失败')
        } finally {
            setLoading(false)
        }
    }

    // Reset when symbol changes
    useEffect(() => {
        setData(null)
        setError(null)
    }, [symbol])

    const actionCfg = data ? (actionConfig[data.final_action] || actionConfig['观望']) : null

    return (
        <div className="card overflow-hidden flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-purple-500" />
                    <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                        量价趋势分析
                    </span>
                </div>
                <div className="flex items-center gap-1.5">
                    {data && (
                        <button
                            onClick={handleAnalyze}
                            disabled={loading}
                            className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            title="重新分析"
                        >
                            <RefreshCw className={`w-3 h-3 text-slate-400 hover:text-purple-500 ${loading ? 'animate-spin' : ''}`} />
                        </button>
                    )}
                    {data && (
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${confidenceColors[data.confidence] || confidenceColors['中']}`}>
                            {data.confidence}置信度
                        </span>
                    )}
                </div>
            </div>

            {/* Body */}
            <div className="flex-1 p-3 space-y-3">
                {/* Idle state */}
                {!data && !loading && !error && (
                    <div className="flex flex-col items-center justify-center py-6 gap-3">
                        <Brain className="w-8 h-8 text-slate-300 dark:text-slate-600" />
                        <p className="text-xs text-slate-400 dark:text-slate-500 text-center">
                            威科夫量价趋势分析<br />快速技术面决策 ~3s
                        </p>
                        <button
                            onClick={handleAnalyze}
                            className="px-4 py-1.5 text-xs font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors"
                        >
                            开始分析
                        </button>
                    </div>
                )}

                {/* Loading */}
                {loading && (
                    <div className="flex flex-col items-center justify-center py-6 gap-3">
                        <Loader2 className="w-6 h-6 text-purple-500 animate-spin" />
                        <p className="text-xs text-slate-400 dark:text-slate-500">分析中...</p>
                    </div>
                )}

                {/* Error */}
                {error && (
                    <div className="flex flex-col items-center justify-center py-4 gap-2">
                        <p className="text-xs text-red-500">{error}</p>
                        <button
                            onClick={handleAnalyze}
                            className="flex items-center gap-1 px-3 py-1 text-xs text-purple-600 hover:text-purple-700"
                        >
                            <RefreshCw className="w-3 h-3" />
                            重试
                        </button>
                    </div>
                )}

                {/* Result */}
                {data && (
                    <>
                        {/* Phase + Action */}
                        <div className="flex items-start justify-between">
                            <div className="min-w-0">
                                {(name || data.name) && (
                                    <p className="text-xs text-slate-400 truncate">{name || data.name}</p>
                                )}
                                <span className={`text-sm font-bold ${phaseColors[data.phase] || 'text-slate-600'}`}>
                                    {data.phase}
                                </span>
                            </div>
                            {actionCfg && (
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border ${actionCfg.color}`}>
                                    <actionCfg.icon className="w-3 h-3" />
                                    {actionCfg.label}
                                </span>
                            )}
                        </div>

                        {/* Checklist + Confidence */}
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                            {data.checklist_score}
                        </div>

                        {/* Summary */}
                        <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                            {data.summary}
                        </p>

                        {/* Details */}
                        <div className="space-y-3 pt-2 border-t border-slate-100 dark:border-slate-800">
                            {/* Phase reasoning */}
                            <div>
                                <p className="text-xs font-medium text-slate-500 mb-1">阶段判断</p>
                                <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                                    {data.phase_reasoning}
                                </p>
                            </div>

                            {/* Effort vs Result */}
                            <div>
                                <p className="text-xs font-medium text-slate-500 mb-1">努力与结果</p>
                                <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                                    {data.effort_result}
                                </p>
                            </div>

                            {/* Paths */}
                            {data.paths && Object.keys(data.paths).length > 0 && (
                                <div>
                                    <p className="text-xs font-medium text-slate-500 mb-1">路径推演</p>
                                    <div className="space-y-1">
                                        {data.paths.bullish && (
                                            <p className="text-xs text-green-600 dark:text-green-400">
                                                ▲ {data.paths.bullish}
                                            </p>
                                        )}
                                        {data.paths.neutral && (
                                            <p className="text-xs text-slate-500">
                                                ─ {data.paths.neutral}
                                            </p>
                                        )}
                                        {data.paths.bearish && (
                                            <p className="text-xs text-red-500">
                                                ▼ {data.paths.bearish}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}
