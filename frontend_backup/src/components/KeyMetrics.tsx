import { BarChart3 } from 'lucide-react'
import type { KeyMetric } from '@/types'

const STATUS_COLOR = {
    good: 'text-rose-400',
    neutral: 'text-slate-200',
    bad: 'text-emerald-400',
}

export default function KeyMetrics({ items }: { items?: KeyMetric[] }) {
    const metrics: KeyMetric[] = items ?? []

    return (
        <div className="card p-4">
            <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 rounded-lg bg-blue-500/20">
                    <BarChart3 className="w-4 h-4 text-blue-400" />
                </div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">关键指标速览</h3>
            </div>

            {metrics.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-6 text-center">
                    <BarChart3 className="w-8 h-8 text-slate-600 mb-2" />
                    <p className="text-xs text-slate-500">分析完成后展示关键指标</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {metrics.map((metric) => (
                        <div
                            key={metric.name}
                            className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-700/30 last:border-0"
                        >
                            <span className="text-sm text-slate-400">{metric.name}</span>
                            <span className={`text-sm font-medium ${STATUS_COLOR[metric.status]}`}>
                                {metric.value}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
