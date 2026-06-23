import { Lightbulb } from 'lucide-react'
import type { BriefingOpportunityReport } from '@/types'

interface Props {
    data?: BriefingOpportunityReport | null
    date?: string
}

export default function OpportunityBoard({ data, date }: Props) {
    if (!data || data.error) return null
    const items = data.热点预测
    if (!items || items.length === 0) return null

    return (
        <div className="max-h-[55vh] overflow-y-auto rounded-xl border border-amber-200 bg-amber-50/50 p-3 sm:p-4 dark:border-amber-800/30 dark:bg-amber-950/20">
            <h3 className="text-xs sm:text-sm font-semibold text-amber-700 dark:text-amber-400 mb-2 sm:mb-3 flex items-center gap-2">
                <Lightbulb className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-amber-500" />
                盘前机会早报
                {date && <span className="ml-auto text-[10px] sm:text-xs font-normal text-amber-400">{date}</span>}
            </h3>

            <div className="space-y-3">
                {items.map((item, idx) => (
                    <div key={idx} className="rounded-lg border border-amber-100 bg-white p-3 dark:border-amber-800/20 dark:bg-slate-800/50">
                        <div className="flex items-center gap-2 mb-1.5">
                            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{item.概念名称}</span>
                            {item.强度评级 && (
                                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                                    item.强度评级 === '高' ? 'bg-red-100 text-red-600 dark:bg-red-950/30 dark:text-red-400' :
                                    item.强度评级 === '中' ? 'bg-amber-100 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400' :
                                    'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
                                }`}>
                                    {item.强度评级}
                                </span>
                            )}
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">{item.逻辑}</p>
                        {item.关注标的 && item.关注标的.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                                {item.关注标的.map((s, i) => (
                                    <span key={i} className="inline-flex items-center gap-1 text-xs bg-slate-100 dark:bg-slate-700/50 px-2 py-0.5 rounded">
                                        <span className="font-mono text-slate-600 dark:text-slate-300">{s.代码}</span>
                                        <span className="font-medium text-slate-800 dark:text-slate-200">{s.名称}</span>
                                        <span className="text-slate-400">|</span>
                                        <span className="text-slate-500 dark:text-slate-400">{s.理由}</span>
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {data.综述 && (
                <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">{data.综述}</p>
            )}
        </div>
    )
}
