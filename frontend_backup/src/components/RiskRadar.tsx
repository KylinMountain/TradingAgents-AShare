import { AlertTriangle, Shield, AlertCircle } from 'lucide-react'
import type { RiskItem } from '@/types'

const LEVEL_CONFIG = {
    high: { color: 'text-rose-400', bg: 'bg-rose-500/20', label: '高风险', icon: AlertTriangle },
    medium: { color: 'text-amber-400', bg: 'bg-amber-500/20', label: '中风险', icon: AlertCircle },
    low: { color: 'text-emerald-400', bg: 'bg-emerald-500/20', label: '低风险', icon: Shield },
}

export default function RiskRadar({ items }: { items?: RiskItem[] }) {
    const risks: RiskItem[] = items ?? []

    return (
        <div className="card p-4">
            <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 rounded-lg bg-amber-500/20">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                </div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">风险雷达</h3>
            </div>

            {risks.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-6 text-center">
                    <Shield className="w-8 h-8 text-slate-600 mb-2" />
                    <p className="text-xs text-slate-500">分析完成后展示风险评估</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {risks.map((risk, i) => {
                        const config = LEVEL_CONFIG[risk.level]
                        return (
                            <div
                                key={i}
                                className="flex items-start justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 gap-2"
                            >
                                <div className="flex-1 min-w-0">
                                    <span className="text-sm text-slate-700 dark:text-slate-300 block truncate">{risk.name}</span>
                                    {risk.description && (
                                        <span className="text-xs text-slate-500 mt-0.5 block line-clamp-2">{risk.description}</span>
                                    )}
                                </div>
                                <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${config.color} ${config.bg}`}>
                                    {config.label}
                                </span>
                            </div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
