import { useMemo } from 'react'
import { useAnalysisStore } from '@/stores/analysisStore'
import type { AgentStatus } from '@/types'
import {
    TrendingUp, MessageCircle, Newspaper, Calculator,
    BarChart2, DollarSign, Swords, ArrowBigUp, ArrowBigDown,
    Brain, Briefcase, Flame, Scale, Shield, CheckCircle2, Loader2,
    ArrowRight,
} from 'lucide-react'
import { extractVerdict, type Verdict } from '@/utils/reportText'

// ── Agent metadata ────────────────────────────────────────────────────────────

interface AgentMeta {
    name: string
    label: string
    goal: string
    section?: string
    Icon: React.FC<{ className?: string }>
    // badge
    badgeBg: string       // light bg  /  dark:bg
    badgeText: string     // light text / dark:text
    // summary box
    sumBorder: string
    sumBg: string
    sumText: string
    // status pill (active)
    activePill: string
}

const META: AgentMeta[] = [
    {
        name: 'Market Analyst', label: '技术面', goal: '技术指标与价格形态分析',
        section: 'market_report', Icon: TrendingUp,
        badgeBg: 'bg-blue-100 dark:bg-blue-500/20', badgeText: 'text-blue-600 dark:text-blue-400',
        sumBorder: 'border-blue-200 dark:border-blue-500/40', sumBg: 'bg-blue-50 dark:bg-blue-500/5', sumText: 'text-blue-700 dark:text-blue-300',
        activePill: 'bg-blue-100 text-blue-600 dark:bg-blue-500/20 dark:text-blue-300',
    },
    {
        name: 'Social Analyst', label: '舆情', goal: '舆论情绪与社交媒体分析',
        section: 'sentiment_report', Icon: MessageCircle,
        badgeBg: 'bg-fuchsia-100 dark:bg-fuchsia-500/20', badgeText: 'text-fuchsia-600 dark:text-fuchsia-400',
        sumBorder: 'border-fuchsia-200 dark:border-fuchsia-500/40', sumBg: 'bg-fuchsia-50 dark:bg-fuchsia-500/5', sumText: 'text-fuchsia-700 dark:text-fuchsia-300',
        activePill: 'bg-fuchsia-100 text-fuchsia-600 dark:bg-fuchsia-500/20 dark:text-fuchsia-300',
    },
    {
        name: 'News Analyst', label: '新闻', goal: '政策资讯与行业动态分析',
        section: 'news_report', Icon: Newspaper,
        badgeBg: 'bg-cyan-100 dark:bg-cyan-500/20', badgeText: 'text-cyan-600 dark:text-cyan-400',
        sumBorder: 'border-cyan-200 dark:border-cyan-500/40', sumBg: 'bg-cyan-50 dark:bg-cyan-500/5', sumText: 'text-cyan-700 dark:text-cyan-300',
        activePill: 'bg-cyan-100 text-cyan-600 dark:bg-cyan-500/20 dark:text-cyan-300',
    },
    {
        name: 'Fundamentals Analyst', label: '基本面', goal: '财务报表与估值分析',
        section: 'fundamentals_report', Icon: Calculator,
        badgeBg: 'bg-emerald-100 dark:bg-emerald-500/20', badgeText: 'text-emerald-600 dark:text-emerald-400',
        sumBorder: 'border-emerald-200 dark:border-emerald-500/40', sumBg: 'bg-emerald-50 dark:bg-emerald-500/5', sumText: 'text-emerald-700 dark:text-emerald-300',
        activePill: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-300',
    },
    {
        name: 'Macro Analyst', label: '宏观', goal: '板块轮动与政策驱动分析',
        section: 'macro_report', Icon: BarChart2,
        badgeBg: 'bg-violet-100 dark:bg-violet-500/20', badgeText: 'text-violet-600 dark:text-violet-400',
        sumBorder: 'border-violet-200 dark:border-violet-500/40', sumBg: 'bg-violet-50 dark:bg-violet-500/5', sumText: 'text-violet-700 dark:text-violet-300',
        activePill: 'bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-300',
    },
    {
        name: 'Smart Money Analyst', label: '主力资金', goal: '机构资金行为与龙虎榜',
        section: 'smart_money_report', Icon: DollarSign,
        badgeBg: 'bg-amber-100 dark:bg-amber-500/20', badgeText: 'text-amber-600 dark:text-amber-400',
        sumBorder: 'border-amber-200 dark:border-amber-500/40', sumBg: 'bg-amber-50 dark:bg-amber-500/5', sumText: 'text-amber-700 dark:text-amber-300',
        activePill: 'bg-amber-100 text-amber-600 dark:bg-amber-500/20 dark:text-amber-300',
    },
    {
        name: 'Game Theory Manager', label: '博弈裁判', goal: '主力与散户预期差裁判',
        section: 'game_theory_report', Icon: Swords,
        badgeBg: 'bg-rose-100 dark:bg-rose-500/20', badgeText: 'text-rose-600 dark:text-rose-400',
        sumBorder: 'border-rose-200 dark:border-rose-500/40', sumBg: 'bg-rose-50 dark:bg-rose-500/5', sumText: 'text-rose-700 dark:text-rose-300',
        activePill: 'bg-rose-100 text-rose-600 dark:bg-rose-500/20 dark:text-rose-300',
    },
    {
        name: 'Bull Researcher', label: '多头', goal: '评估投资价值与上行潜力',
        section: 'investment_plan', Icon: ArrowBigUp,
        badgeBg: 'bg-emerald-100 dark:bg-emerald-500/20', badgeText: 'text-emerald-600 dark:text-emerald-400',
        sumBorder: 'border-emerald-200 dark:border-emerald-500/40', sumBg: 'bg-emerald-50 dark:bg-emerald-500/5', sumText: 'text-emerald-700 dark:text-emerald-300',
        activePill: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-300',
    },
    {
        name: 'Bear Researcher', label: '空头', goal: '评估下行风险与潜在危机',
        section: 'investment_plan', Icon: ArrowBigDown,
        badgeBg: 'bg-rose-100 dark:bg-rose-500/20', badgeText: 'text-rose-600 dark:text-rose-400',
        sumBorder: 'border-rose-200 dark:border-rose-500/40', sumBg: 'bg-rose-50 dark:bg-rose-500/5', sumText: 'text-rose-700 dark:text-rose-300',
        activePill: 'bg-rose-100 text-rose-600 dark:bg-rose-500/20 dark:text-rose-300',
    },
    {
        name: 'Research Manager', label: '研究总监', goal: '综合多空论据形成投资计划',
        section: 'investment_plan', Icon: Brain,
        badgeBg: 'bg-indigo-100 dark:bg-indigo-500/20', badgeText: 'text-indigo-600 dark:text-indigo-400',
        sumBorder: 'border-indigo-200 dark:border-indigo-500/40', sumBg: 'bg-indigo-50 dark:bg-indigo-500/5', sumText: 'text-indigo-700 dark:text-indigo-300',
        activePill: 'bg-indigo-100 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-300',
    },
    {
        name: 'Trader', label: '交易员', goal: '将研究结论转化为可执行指令',
        section: 'trader_investment_plan', Icon: Briefcase,
        badgeBg: 'bg-orange-100 dark:bg-orange-500/20', badgeText: 'text-orange-600 dark:text-orange-400',
        sumBorder: 'border-orange-200 dark:border-orange-500/40', sumBg: 'bg-orange-50 dark:bg-orange-500/5', sumText: 'text-orange-700 dark:text-orange-300',
        activePill: 'bg-orange-100 text-orange-600 dark:bg-orange-500/20 dark:text-orange-300',
    },
    {
        name: 'Aggressive Analyst', label: '激进', goal: '高风险高收益策略约束',
        section: 'final_trade_decision', Icon: Flame,
        badgeBg: 'bg-red-100 dark:bg-red-500/20', badgeText: 'text-red-600 dark:text-red-400',
        sumBorder: 'border-red-200 dark:border-red-500/40', sumBg: 'bg-red-50 dark:bg-red-500/5', sumText: 'text-red-700 dark:text-red-300',
        activePill: 'bg-red-100 text-red-600 dark:bg-red-500/20 dark:text-red-300',
    },
    {
        name: 'Neutral Analyst', label: '中性', goal: '均衡风险收益策略约束',
        section: 'final_trade_decision', Icon: Scale,
        badgeBg: 'bg-slate-100 dark:bg-slate-500/20', badgeText: 'text-slate-600 dark:text-slate-400',
        sumBorder: 'border-slate-200 dark:border-slate-500/40', sumBg: 'bg-slate-50 dark:bg-slate-500/5', sumText: 'text-slate-600 dark:text-slate-300',
        activePill: 'bg-slate-100 text-slate-600 dark:bg-slate-500/20 dark:text-slate-300',
    },
    {
        name: 'Conservative Analyst', label: '稳健', goal: '低风险保守策略约束',
        section: 'final_trade_decision', Icon: Shield,
        badgeBg: 'bg-amber-100 dark:bg-amber-500/20', badgeText: 'text-amber-600 dark:text-amber-400',
        sumBorder: 'border-amber-200 dark:border-amber-500/40', sumBg: 'bg-amber-50 dark:bg-amber-500/5', sumText: 'text-amber-700 dark:text-amber-300',
        activePill: 'bg-amber-100 text-amber-600 dark:bg-amber-500/20 dark:text-amber-300',
    },
    {
        name: 'Portfolio Manager', label: '组合经理', goal: '综合裁决形成最终决策',
        section: 'final_trade_decision', Icon: CheckCircle2,
        badgeBg: 'bg-teal-100 dark:bg-teal-500/20', badgeText: 'text-teal-600 dark:text-teal-400',
        sumBorder: 'border-teal-200 dark:border-teal-500/40', sumBg: 'bg-teal-50 dark:bg-teal-500/5', sumText: 'text-teal-700 dark:text-teal-300',
        activePill: 'bg-teal-100 text-teal-600 dark:bg-teal-500/20 dark:text-teal-300',
    },
]

const GROUPS = [
    { title: '分析团队', cols: 'grid-cols-3', agents: ['Market Analyst','Social Analyst','News Analyst','Fundamentals Analyst','Macro Analyst','Smart Money Analyst'] },
    { title: '博弈裁判', cols: 'grid-cols-1', agents: ['Game Theory Manager'] },
    { title: '多空辩论', cols: 'grid-cols-3', agents: ['Bull Researcher','Bear Researcher','Research Manager'] },
    { title: '交易执行', cols: 'grid-cols-1', agents: ['Trader'] },
    { title: '风控裁决', cols: 'grid-cols-4', agents: ['Aggressive Analyst','Neutral Analyst','Conservative Analyst','Portfolio Manager'] },
]

const STATUS_LABEL: Record<AgentStatus, string> = {
    pending: '待命', in_progress: '分析中', completed: '完成', skipped: '跳过', error: '异常',
}

// ── Single agent card ─────────────────────────────────────────────────────────

interface CardData extends AgentMeta { status: AgentStatus; isStreaming: boolean; verdict: Verdict | null }

const VERDICT_COLORS: Record<string, string> = {
    '看多': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
    '看空': 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
    '中性': 'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400',
    '谨慎': 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
    // fallback for any unrecognized value
    _default: 'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400',
}

function AgentCard({ card, selected, onClick }: { card: CardData; selected?: boolean; onClick?: () => void }) {
    const active  = card.status === 'in_progress'
    const done    = card.status === 'completed'
    const skipped = card.status === 'skipped'
    const clickable = !!card.section && (done || active)
    const { Icon } = card

    return (
        <button
            type="button"
            disabled={!clickable}
            onClick={() => clickable && onClick?.()}
            className={[
                'group w-full text-left rounded-xl border transition-all duration-200 overflow-hidden',
                selected
                    ? 'border-blue-400 dark:border-blue-500 bg-blue-50/60 dark:bg-blue-500/10 shadow-md ring-1 ring-blue-300/50 dark:ring-blue-500/30'
                    : active
                    ? 'border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-sm'
                    : done
                    ? 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60'
                    : skipped
                    ? 'border-slate-100 dark:border-slate-800 bg-transparent opacity-40'
                    : 'border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-800/20 opacity-55',
                clickable ? 'cursor-pointer hover:border-slate-400 dark:hover:border-slate-500 hover:shadow-md' : 'cursor-default',
            ].join(' ')}
        >
            <div className="p-3">
                {/* Icon badge + label + status */}
                <div className="flex items-start gap-2.5 mb-2.5">
                    <div className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${card.badgeBg}`}>
                        {active
                            ? <Loader2 className={`w-5 h-5 animate-spin ${card.badgeText}`} />
                            : <Icon className={`w-5 h-5 ${card.badgeText}`} />
                        }
                    </div>
                    <div className="min-w-0 flex-1 pt-0.5">
                        <div className={`text-[13px] font-semibold leading-tight ${card.badgeText}`}>
                            {card.label}
                        </div>
                        <div className="text-[11px] text-slate-400 dark:text-slate-500 leading-tight mt-0.5 line-clamp-1">
                            {card.goal}
                        </div>
                    </div>
                    {/* status pill */}
                    <span className={[
                        'shrink-0 mt-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium',
                        active  ? card.activePill
                        : done  ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400'
                        : skipped ? 'bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500'
                        : 'bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500',
                    ].join(' ')}>
                        {STATUS_LABEL[card.status]}
                    </span>
                </div>

                {/* Key Points Summary */}
                {(done || active) && (
                    <div className={`rounded-lg border px-2.5 py-2 ${card.sumBorder} ${card.sumBg}`}>
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1.5">
                            Key Points
                        </p>
                        {active ? (
                            <div className="flex items-center gap-1.5">
                                <Loader2 className={`w-3 h-3 animate-spin shrink-0 ${card.badgeText}`} />
                                <span className={`text-[11px] ${card.sumText}`}>正在生成分析...</span>
                            </div>
                        ) : card.verdict ? (
                            <div className="flex items-start gap-1.5 min-w-0">
                                <span className={`shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-tight ${VERDICT_COLORS[card.verdict.direction] ?? VERDICT_COLORS._default}`}>
                                    {card.verdict.direction}
                                </span>
                                <span className={`text-[11px] leading-[1.4] ${card.sumText}`}>
                                    {card.verdict.reason}
                                </span>
                            </div>
                        ) : (
                            <div className="flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />
                                <span className="text-[11px] text-emerald-600 dark:text-emerald-400">分析完成</span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </button>
    )
}

// ── Main component ────────────────────────────────────────────────────────────

interface AgentCollaborationProps {
    onSelectSection?: (section?: string) => void
    selectedSection?: string
}

export default function AgentCollaboration({ onSelectSection, selectedSection }: AgentCollaborationProps) {
    const { agents, isAnalyzing, streamingSections, report } = useAnalysisStore()

    const cards = useMemo(() => META.map((meta) => {
        const agent       = agents.find(a => a.name === meta.name)
        const streamState = meta.section ? streamingSections[meta.section] : undefined
        const stored      = meta.section ? (report?.[meta.section as keyof typeof report] as string | undefined) : undefined
        const src         = streamState?.displayed || stored || ''
        return {
            ...meta,
            status:      (agent?.status ?? 'pending') as AgentStatus,
            isStreaming: !!streamState?.isTyping,
            verdict:     extractVerdict(src),
        }
    }), [agents, report, streamingSections])

    const done15  = cards.filter(c => c.status === 'completed' || c.status === 'skipped').length
    const cardMap = new Map(cards.map(c => [c.name, c]))

    return (
        <section className="card">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                        TradingAgents 协同研判台
                    </h3>
                    <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                        15 席位 · 5 阶段串行流水线 · 分析团队并行产出
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs tabular-nums text-slate-400 dark:text-slate-500">{done15} / 15</span>
                    {isAnalyzing && (
                        <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs bg-blue-100 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            运行中
                        </span>
                    )}
                </div>
            </div>

            <div className="space-y-3">
                {GROUPS.map((group, gi) => {
                    const gc       = group.agents.map(n => cardMap.get(n)).filter(Boolean) as CardData[]
                    const doneN    = gc.filter(c => c.status === 'completed').length
                    const anyAct   = gc.some(c => c.status === 'in_progress')
                    const allDone  = gc.every(c => c.status === 'completed' || c.status === 'skipped')

                    return (
                        <div key={group.title}>
                            {/* Group header */}
                            <div className="flex items-center gap-2 mb-2">
                                <span className={[
                                    'text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center shrink-0',
                                    anyAct  ? 'bg-blue-100 text-blue-600 dark:bg-blue-500/25 dark:text-blue-400'
                                    : allDone ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/25 dark:text-emerald-400'
                                    : 'bg-slate-100 text-slate-400 dark:bg-slate-700/50 dark:text-slate-500',
                                ].join(' ')}>
                                    {gi + 1}
                                </span>
                                <span className={`text-xs font-semibold ${
                                    anyAct  ? 'text-slate-800 dark:text-slate-200'
                                    : allDone ? 'text-emerald-600 dark:text-emerald-400'
                                    : 'text-slate-400 dark:text-slate-500'
                                }`}>
                                    {group.title}
                                </span>
                                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-700/60" />
                                <span className="text-[10px] tabular-nums text-slate-400 dark:text-slate-600">
                                    {doneN}/{gc.length}
                                </span>
                                {allDone && (
                                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                                )}
                            </div>

                            {/* Cards grid */}
                            <div className={`grid gap-2 ${group.cols}`}>
                                {gc.map(card => (
                                    <AgentCard
                                        key={card.name}
                                        card={card}
                                        selected={!!card.section && card.section === selectedSection}
                                        onClick={() => {
                                            if (card.section === selectedSection) {
                                                onSelectSection?.(undefined)
                                            } else {
                                                onSelectSection?.(card.section)
                                            }
                                        }}
                                    />
                                ))}
                            </div>

                            {/* Arrow between groups */}
                            {gi < GROUPS.length - 1 && (
                                <div className="flex items-center justify-center mt-3 gap-1 text-slate-300 dark:text-slate-700">
                                    <div className="h-px w-16 bg-slate-200 dark:bg-slate-700" />
                                    <ArrowRight className="w-3.5 h-3.5" />
                                    <div className="h-px w-16 bg-slate-200 dark:bg-slate-700" />
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>
        </section>
    )
}
