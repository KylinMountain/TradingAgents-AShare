import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import type { ConceptBoard } from '@/types'

const TYPE_STYLES: Record<string, { bg: string; text: string }> = {
    '行业': { bg: 'bg-blue-50', text: 'text-blue-700' },
    '概念': { bg: 'bg-orange-50', text: 'text-orange-700' },
    '地域': { bg: 'bg-slate-50', text: 'text-slate-600' },
    '板块': { bg: 'bg-purple-50', text: 'text-purple-700' },
}

const DEFAULT_STYLE = { bg: 'bg-slate-50', text: 'text-slate-600' }

interface ConceptTagsProps {
    concepts: ConceptBoard[]
    onRefresh?: () => void
    loading?: boolean
    maxVisible?: number
}

export function ConceptTags({ concepts, onRefresh, loading, maxVisible = 5 }: ConceptTagsProps) {
    const [expanded, setExpanded] = useState(false)

    if (!concepts || concepts.length === 0) {
        return onRefresh ? (
            <button
                onClick={onRefresh}
                disabled={loading}
                className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors"
                title="获取概念板块"
            >
                <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                <span>获取概念</span>
            </button>
        ) : null
    }

    const visible = expanded ? concepts : concepts.slice(0, maxVisible)
    const hiddenCount = concepts.length - maxVisible

    return (
        <div className="flex flex-wrap items-center gap-1">
            {visible.map((c, i) => {
                const style = TYPE_STYLES[c.type] || DEFAULT_STYLE
                return (
                    <span
                        key={`${c.type}-${c.name}-${i}`}
                        className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${style.bg} ${style.text}`}
                        title={c.type}
                    >
                        {c.name}
                    </span>
                )
            })}
            {!expanded && hiddenCount > 0 && (
                <button
                    onClick={() => setExpanded(true)}
                    className="text-[10px] text-slate-400 hover:text-slate-600 transition-colors"
                >
                    +{hiddenCount}
                </button>
            )}
            {expanded && concepts.length > maxVisible && (
                <button
                    onClick={() => setExpanded(false)}
                    className="text-[10px] text-slate-400 hover:text-slate-600 transition-colors"
                >
                    收起
                </button>
            )}
            {onRefresh && (
                <button
                    onClick={onRefresh}
                    disabled={loading}
                    className="inline-flex items-center text-[10px] text-slate-400 hover:text-slate-600 transition-colors ml-0.5"
                    title="刷新概念板块"
                >
                    <RefreshCw className={`w-2.5 h-2.5 ${loading ? 'animate-spin' : ''}`} />
                </button>
            )}
        </div>
    )
}
