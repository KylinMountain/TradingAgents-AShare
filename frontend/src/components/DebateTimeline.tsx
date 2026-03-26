import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { DebateMessage } from '@/types'

// Agent metadata for debate participants
const DEBATE_AGENT_META: Record<string, { emoji: string; label: string; dotCls: string; borderCls: string; bgCls: string; textCls: string }> = {
    'Bull Researcher':       { emoji: '🐂', label: '多头研究员',  dotCls: 'bg-emerald-500', borderCls: 'border-emerald-500/30', bgCls: 'bg-emerald-500/5',  textCls: 'text-emerald-400' },
    'Bear Researcher':       { emoji: '🐻', label: '空头研究员',  dotCls: 'bg-rose-500',    borderCls: 'border-rose-500/30',    bgCls: 'bg-rose-500/5',     textCls: 'text-rose-400' },
    'Research Manager':      { emoji: '🏛️', label: '研究总监',    dotCls: 'bg-blue-500',    borderCls: 'border-blue-500/30',    bgCls: 'bg-blue-500/5',     textCls: 'text-blue-400' },
    'Aggressive Analyst':    { emoji: '🔥', label: '激进派',      dotCls: 'bg-red-500',     borderCls: 'border-red-500/30',     bgCls: 'bg-red-500/5',      textCls: 'text-red-400' },
    'Neutral Analyst':       { emoji: '⚖️', label: '中性派',      dotCls: 'bg-slate-500',   borderCls: 'border-slate-500/30',   bgCls: 'bg-slate-500/5',    textCls: 'text-slate-400' },
    'Conservative Analyst':  { emoji: '🛡️', label: '稳健派',      dotCls: 'bg-amber-500',   borderCls: 'border-amber-500/30',   bgCls: 'bg-amber-500/5',    textCls: 'text-amber-400' },
    'Portfolio Manager':     { emoji: '🏛️', label: '风控裁决',    dotCls: 'bg-blue-500',    borderCls: 'border-blue-500/30',    bgCls: 'bg-blue-500/5',     textCls: 'text-blue-400' },
}

interface DebateTimelineProps {
    messages: DebateMessage[]
    debate: 'research' | 'risk'
}

export default function DebateTimeline({ messages, debate }: DebateTimelineProps) {
    if (messages.length === 0) {
        return (
            <div className="flex items-center justify-center h-full text-slate-500 dark:text-slate-400">
                <div className="text-center">
                    <div className="text-3xl mb-3">{debate === 'research' ? '🐂⚔️🐻' : '🔥⚖️🛡️'}</div>
                    <p className="text-sm">辩论尚未开始</p>
                </div>
            </div>
        )
    }

    // Separate verdict and speech messages
    const speeches = messages.filter(m => !m.isVerdict)
    const verdict = messages.find(m => m.isVerdict)

    // Group speeches by round
    const rounds = new Map<number, DebateMessage[]>()
    for (const msg of speeches) {
        const list = rounds.get(msg.round) || []
        list.push(msg)
        rounds.set(msg.round, list)
    }
    const sortedRounds = [...rounds.entries()].sort(([a], [b]) => a - b)

    return (
        <div className="space-y-1">
            {sortedRounds.map(([round, msgs]) => (
                <div key={round}>
                    {/* Round separator */}
                    <div className="flex items-center gap-3 my-4">
                        <div className="flex-1 h-px bg-amber-500/20" />
                        <span className="text-xs font-bold text-amber-500 bg-amber-500/10 px-3 py-0.5 rounded-full">
                            Round {round}
                        </span>
                        <div className="flex-1 h-px bg-amber-500/20" />
                    </div>

                    {/* Speech cards */}
                    <div className="space-y-3 pl-4 relative">
                        {/* Timeline line */}
                        <div className="absolute left-[7px] top-2 bottom-2 w-0.5 bg-slate-700/50" />

                        {msgs.map((msg, i) => {
                            const meta = DEBATE_AGENT_META[msg.agent] || {
                                emoji: '💬', label: msg.agent, dotCls: 'bg-slate-500',
                                borderCls: 'border-slate-500/30', bgCls: 'bg-slate-500/5', textCls: 'text-slate-400',
                            }
                            return (
                                <div key={`${round}-${msg.agent}-${i}`} className="relative">
                                    {/* Timeline dot */}
                                    <div className={`absolute -left-4 top-3 w-2.5 h-2.5 rounded-full ${meta.dotCls} ring-2 ring-slate-900 z-10`} />

                                    {/* Speech card */}
                                    <div className={`ml-2 rounded-lg border ${meta.borderCls} ${meta.bgCls} p-4`}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-base">{meta.emoji}</span>
                                            <span className={`text-sm font-bold ${meta.textCls}`}>{meta.label}</span>
                                            {msg.horizon && (
                                                <span className="text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">
                                                    {msg.horizon === 'short' ? '短线' : '中线'}
                                                </span>
                                            )}
                                        </div>
                                        <div className="prose dark:prose-invert prose-sm max-w-none text-sm leading-relaxed">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {msg.content}
                                            </ReactMarkdown>
                                        </div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            ))}

            {/* Verdict card */}
            {verdict && (
                <div className="mt-6">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="flex-1 h-px bg-blue-500/30" />
                        <span className="text-xs font-bold text-blue-400 bg-blue-500/10 px-3 py-0.5 rounded-full">
                            裁决
                        </span>
                        <div className="flex-1 h-px bg-blue-500/30" />
                    </div>
                    <div className="rounded-lg border border-blue-500/40 bg-slate-900/80 p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-base">🏛️</span>
                            <span className="text-sm font-bold text-blue-400">
                                {debate === 'research' ? '研究总监裁决' : '风控裁决'}
                            </span>
                        </div>
                        <div className="prose dark:prose-invert prose-sm max-w-none text-sm leading-relaxed">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {verdict.content}
                            </ReactMarkdown>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
