import { Newspaper } from 'lucide-react'
import type { BriefingNewsBriefing } from '@/types'

interface Props {
    data?: BriefingNewsBriefing | null
}

export default function NewsBoard({ data }: Props) {
    if (!data || data.error) return null
    const items = data.大事速递
    if (!items || items.length === 0) return null

    return (
        <div className="max-h-[55vh] overflow-y-auto rounded-xl border border-purple-200 bg-purple-50/50 p-3 sm:p-4 dark:border-purple-800/30 dark:bg-purple-950/20">
            <h3 className="text-xs sm:text-sm font-semibold text-purple-700 dark:text-purple-400 mb-2 sm:mb-3 flex items-center gap-2">
                <Newspaper className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-purple-500" />
                全球大事早报
            </h3>

            <div className="space-y-2">
                {items.map((item, idx) => (
                    <div key={idx} className="rounded-lg border border-purple-100 bg-white p-2.5 dark:border-purple-800/20 dark:bg-slate-800/50">
                        <div className="flex items-start gap-2">
                            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-purple-100 dark:bg-purple-900/30 text-[10px] font-bold text-purple-600 dark:text-purple-400 flex items-center justify-center">
                                {idx + 1}
                            </span>
                            <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium text-slate-800 dark:text-slate-200 mb-1">{item.核心内容}</p>
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-[10px] text-slate-500 dark:text-slate-400">{item.影响分析}</span>
                                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                                        item.逻辑强度 === '高' ? 'bg-red-100 text-red-600 dark:bg-red-950/30 dark:text-red-400' :
                                        item.逻辑强度 === '中' ? 'bg-amber-100 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400' :
                                        'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
                                    }`}>
                                        强度: {item.逻辑强度}
                                    </span>
                                    {item.理由 && (
                                        <span className="text-[10px] text-slate-400">{item.理由}</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {data.综述 && (
                <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">{data.综述}</p>
            )}
        </div>
    )
}
