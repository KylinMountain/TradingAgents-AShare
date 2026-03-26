import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { useAnalysisStore } from '@/stores/analysisStore'
import DebateTimeline from './DebateTimeline'

const DEBATE_TITLES: Record<string, { title: string; emoji: string }> = {
    research: { title: '多空辩论', emoji: '🐂⚔️🐻' },
    risk: { title: '风控三方辩论', emoji: '🔥⚖️🛡️' },
}

const DEBATE_PARTICIPANTS: Record<string, { emoji: string; label: string; cls: string }[]> = {
    research: [
        { emoji: '🐂', label: '多头', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
        { emoji: '🐻', label: '空头', cls: 'bg-rose-500/15 text-rose-400 border-rose-500/30' },
        { emoji: '🏛️', label: '研究总监', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
    ],
    risk: [
        { emoji: '🔥', label: '激进', cls: 'bg-red-500/15 text-red-400 border-red-500/30' },
        { emoji: '⚖️', label: '中性', cls: 'bg-slate-500/15 text-slate-400 border-slate-500/30' },
        { emoji: '🛡️', label: '稳健', cls: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
        { emoji: '🏛️', label: '风控', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
    ],
}

interface DebateDrawerProps {
    debate: 'research' | 'risk' | null
    onClose: () => void
}

export default function DebateDrawer({ debate, onClose }: DebateDrawerProps) {
    const debateMessages = useAnalysisStore(s => s.debateMessages)
    const scrollRef = useRef<HTMLDivElement>(null)
    const messages = debate ? (debateMessages[debate] || []) : []
    const meta = debate ? DEBATE_TITLES[debate] : null
    const participants = debate ? DEBATE_PARTICIPANTS[debate] : []

    // Auto-scroll on new messages
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
        }
    }, [messages.length])

    return (
        <>
            {/* Backdrop */}
            <div
                className={`fixed inset-0 bg-black/40 z-40 transition-opacity duration-300 ${debate ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
                onClick={onClose}
            />

            {/* Drawer */}
            <div className={`fixed top-0 right-0 h-full w-1/2 max-w-[720px] min-w-[400px] bg-slate-900 border-l border-slate-700 shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-out ${debate ? 'translate-x-0' : 'translate-x-full'}`}>
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
                    <div className="flex items-center gap-3">
                        <span className="text-lg">{meta?.emoji}</span>
                        <h2 className="text-lg font-bold text-white tracking-tight">{meta?.title}</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Participant pills */}
                <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-800/50">
                    {participants.map(p => (
                        <span key={p.label} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${p.cls}`}>
                            <span>{p.emoji}</span>
                            <span>{p.label}</span>
                        </span>
                    ))}
                </div>

                {/* Scrollable timeline */}
                <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-5 py-4">
                    {debate && <DebateTimeline messages={messages} debate={debate} />}
                </div>
            </div>
        </>
    )
}
