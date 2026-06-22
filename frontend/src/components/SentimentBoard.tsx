import { Globe } from 'lucide-react'
import type { BriefingSentimentReport } from '@/types'

interface Props {
    data?: BriefingSentimentReport | null
}

export default function SentimentBoard({ data }: Props) {
    if (!data || data.error) return null

    const sections = [
        { label: '美股', content: data.美股复盘 },
        { label: '中概股', content: data.中概股表现 },
        { label: '港股', content: data.港股表现 },
        { label: 'A50与汇率', content: data.A50与汇率 },
    ].filter(s => s.content)

    const sentimentColor = data.市场情绪 === 'risk-on'
        ? 'text-red-500 bg-red-50 dark:bg-red-950/20'
        : data.市场情绪 === 'risk-off'
        ? 'text-green-500 bg-green-50 dark:bg-green-950/20'
        : 'text-slate-500 bg-slate-50 dark:bg-slate-800/50'

    return (
        <div className="max-h-[55vh] overflow-y-auto rounded-xl border border-blue-200 bg-blue-50/50 p-3 sm:p-4 dark:border-blue-800/30 dark:bg-blue-950/20">
            <h3 className="text-xs sm:text-sm font-semibold text-blue-700 dark:text-blue-400 mb-2 sm:mb-3 flex items-center gap-2">
                <Globe className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-blue-500" />
                隔夜外围市场复盘
            </h3>

            {sections.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
                    {sections.map((s, i) => (
                        <div key={i} className="rounded-lg border border-blue-100 bg-white p-2.5 dark:border-blue-800/20 dark:bg-slate-800/50">
                            <div className="text-[10px] text-slate-400 mb-1">{s.label}</div>
                            <div className="text-xs text-slate-700 dark:text-slate-300">{s.content}</div>
                        </div>
                    ))}
                </div>
            )}

            {data.市场情绪 && (
                <div className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium mb-2 ${sentimentColor}`}>
                    <span className="text-[10px] text-slate-400">情绪</span>
                    {data.市场情绪}
                </div>
            )}

            {data.A股开盘预判 && (
                <div className="rounded-lg border border-blue-100 bg-white p-2.5 dark:border-blue-800/20 dark:bg-slate-800/50 mb-2">
                    <div className="text-[10px] text-slate-400 mb-1">A股开盘预判</div>
                    <div className="text-xs text-slate-700 dark:text-slate-300">{data.A股开盘预判}</div>
                </div>
            )}

            {data.核心结论 && (
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300">{data.核心结论}</p>
            )}
        </div>
    )
}
