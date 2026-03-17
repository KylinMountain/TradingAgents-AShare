import { useMemo } from 'react'
import { useAnalysisStore } from '@/stores/analysisStore'
import type { AgentStatus } from '@/types'
import {
    TrendingUp, MessageCircle, Newspaper, Calculator,
    BarChart2, DollarSign, Swords, ArrowBigUp, ArrowBigDown,
    Brain, Briefcase, Flame, Scale, Shield, CheckCircle2, Loader2,
} from 'lucide-react'
import { extractVerdict, type Verdict } from '@/utils/reportText'

// ── Agent 元数据 (保持原有色彩与中文) ──────────────────────────────────────────

interface AgentMeta {
    name: string
    label: string
    goal: string
    section?: string
    Icon: React.FC<{ className?: string }>
    badgeBg: string
    badgeText: string
    sumBorder: string
    sumBg: string
    sumText: string
    activePill: string
}

const META: AgentMeta[] = [
    {
        name: 'Market Analyst', label: '技术面', goal: '技术指标与价格形态分析',
        section: 'market_report', Icon: TrendingUp,
        badgeBg: 'bg-blue-100 dark:bg-blue-500/20', badgeText: 'text-blue-600 dark:text-blue-400',
        sumBorder: 'border-blue-200 dark:border-blue-500/40', sumBg: 'bg-blue-50 dark:bg-blue-500/5', sumText: 'text-blue-700 dark:text-blue-300',
        activePill: 'bg-blue-500 text-white',
    },
    {
        name: 'Social Analyst', label: '舆情', goal: '舆论情绪与社交媒体分析',
        section: 'sentiment_report', Icon: MessageCircle,
        badgeBg: 'bg-fuchsia-100 dark:bg-fuchsia-500/20', badgeText: 'text-fuchsia-600 dark:text-fuchsia-400',
        sumBorder: 'border-fuchsia-200 dark:border-fuchsia-500/40', sumBg: 'bg-fuchsia-50 dark:bg-fuchsia-500/5', sumText: 'text-fuchsia-700 dark:text-fuchsia-300',
        activePill: 'bg-fuchsia-500 text-white',
    },
    {
        name: 'News Analyst', label: '新闻', goal: '政策资讯与行业动态分析',
        section: 'news_report', Icon: Newspaper,
        badgeBg: 'bg-cyan-100 dark:bg-cyan-500/20', badgeText: 'text-cyan-600 dark:text-cyan-400',
        sumBorder: 'border-cyan-200 dark:border-cyan-500/40', sumBg: 'bg-cyan-50 dark:bg-cyan-500/5', sumText: 'text-cyan-700 dark:text-cyan-300',
        activePill: 'bg-cyan-500 text-white',
    },
    {
        name: 'Fundamentals Analyst', label: '基本面', goal: '财务报表与估值分析',
        section: 'fundamentals_report', Icon: Calculator,
        badgeBg: 'bg-emerald-100 dark:bg-emerald-500/20', badgeText: 'text-emerald-600 dark:text-emerald-400',
        sumBorder: 'border-emerald-200 dark:border-emerald-500/40', sumBg: 'bg-emerald-50 dark:bg-emerald-500/5', sumText: 'text-emerald-700 dark:text-emerald-300',
        activePill: 'bg-emerald-500 text-white',
    },
    {
        name: 'Macro Analyst', label: '宏观', goal: '板块轮动与政策驱动分析',
        section: 'macro_report', Icon: BarChart2,
        badgeBg: 'bg-violet-100 dark:bg-violet-500/20', badgeText: 'text-violet-600 dark:text-violet-400',
        sumBorder: 'border-violet-200 dark:border-violet-500/40', sumBg: 'bg-violet-50 dark:bg-violet-500/5', sumText: 'text-violet-700 dark:text-violet-300',
        activePill: 'bg-violet-500 text-white',
    },
    {
        name: 'Smart Money Analyst', label: '主力资金', goal: '机构资金行为与龙虎榜',
        section: 'smart_money_report', Icon: DollarSign,
        badgeBg: 'bg-amber-100 dark:bg-amber-500/20', badgeText: 'text-amber-600 dark:text-amber-400',
        sumBorder: 'border-amber-200 dark:border-amber-500/40', sumBg: 'bg-amber-50 dark:bg-amber-500/5', sumText: 'text-amber-700 dark:text-amber-300',
        activePill: 'bg-amber-500 text-white',
    },
    {
        name: 'Game Theory Manager', label: '博弈裁判', goal: '主力与散户预期差裁判',
        section: 'game_theory_report', Icon: Swords,
        badgeBg: 'bg-rose-100 dark:bg-rose-500/20', badgeText: 'text-rose-600 dark:text-rose-400',
        sumBorder: 'border-rose-200 dark:border-rose-500/40', sumBg: 'bg-rose-50 dark:bg-rose-500/5', sumText: 'text-rose-700 dark:text-rose-300',
        activePill: 'bg-rose-500 text-white',
    },
    {
        name: 'Bull Researcher', label: '多头', goal: '评估投资价值与上行潜力',
        section: 'investment_plan', Icon: ArrowBigUp,
        badgeBg: 'bg-emerald-100 dark:bg-emerald-500/20', badgeText: 'text-emerald-600 dark:text-emerald-400',
        sumBorder: 'border-emerald-200 dark:border-emerald-500/40', sumBg: 'bg-emerald-50 dark:bg-emerald-500/5', sumText: 'text-emerald-700 dark:text-emerald-300',
        activePill: 'bg-emerald-500 text-white',
    },
    {
        name: 'Bear Researcher', label: '空头', goal: '评估下行风险与潜在危机',
        section: 'investment_plan', Icon: ArrowBigDown,
        badgeBg: 'bg-rose-100 dark:bg-rose-500/20', badgeText: 'text-rose-600 dark:text-rose-400',
        sumBorder: 'border-rose-200 dark:border-rose-500/40', sumBg: 'bg-rose-50 dark:bg-rose-500/5', sumText: 'text-rose-700 dark:text-rose-300',
        activePill: 'bg-rose-500 text-white',
    },
    {
        name: 'Research Manager', label: '研究总监', goal: '综合多空论据形成投资计划',
        section: 'investment_plan', Icon: Brain,
        badgeBg: 'bg-indigo-100 dark:bg-indigo-500/20', badgeText: 'text-indigo-600 dark:text-indigo-400',
        sumBorder: 'border-indigo-200 dark:border-indigo-500/40', sumBg: 'bg-indigo-50 dark:bg-indigo-500/5', sumText: 'text-indigo-700 dark:text-indigo-300',
        activePill: 'bg-indigo-500 text-white',
    },
    {
        name: 'Trader', label: '交易员', goal: '将研究结论转化为可执行指令',
        section: 'trader_investment_plan', Icon: Briefcase,
        badgeBg: 'bg-orange-100 dark:bg-orange-500/20', badgeText: 'text-orange-600 dark:text-orange-400',
        sumBorder: 'border-orange-200 dark:border-orange-500/40', sumBg: 'bg-orange-50 dark:bg-orange-500/5', sumText: 'text-orange-700 dark:text-orange-300',
        activePill: 'bg-orange-500 text-white',
    },
    {
        name: 'Aggressive Analyst', label: '激进', goal: '高风险高收益策略约束',
        section: 'final_trade_decision', Icon: Flame,
        badgeBg: 'bg-red-100 dark:bg-red-500/20', badgeText: 'text-red-600 dark:text-red-400',
        sumBorder: 'border-red-200 dark:border-red-500/40', sumBg: 'bg-red-50 dark:bg-red-500/5', sumText: 'text-red-700 dark:text-red-300',
        activePill: 'bg-red-500 text-white',
    },
    {
        name: 'Neutral Analyst', label: '中性', goal: '均衡风险收益策略约束',
        section: 'final_trade_decision', Icon: Scale,
        badgeBg: 'bg-slate-100 dark:bg-slate-500/20', badgeText: 'text-slate-600 dark:text-slate-400',
        sumBorder: 'border-slate-200 dark:border-slate-500/40', sumBg: 'bg-slate-50 dark:bg-slate-500/5', sumText: 'text-slate-600 dark:text-slate-300',
        activePill: 'bg-slate-600 text-white',
    },
    {
        name: 'Conservative Analyst', label: '稳健', goal: '低风险保守策略约束',
        section: 'final_trade_decision', Icon: Shield,
        badgeBg: 'bg-amber-100 dark:bg-amber-500/20', badgeText: 'text-amber-600 dark:text-amber-400',
        sumBorder: 'border-amber-200 dark:border-amber-500/40', sumBg: 'bg-amber-50 dark:bg-amber-500/5', sumText: 'text-amber-700 dark:text-amber-300',
        activePill: 'bg-amber-500 text-white',
    },
    {
        name: 'Portfolio Manager', label: '组合经理', goal: '综合裁决形成最终决策',
        section: 'final_trade_decision', Icon: CheckCircle2,
        badgeBg: 'bg-teal-100 dark:bg-teal-500/20', badgeText: 'text-teal-600 dark:text-teal-400',
        sumBorder: 'border-teal-200 dark:border-teal-500/40', sumBg: 'bg-teal-50 dark:bg-teal-500/5', sumText: 'text-teal-700 dark:text-teal-300',
        activePill: 'bg-teal-500 text-white',
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

const VERDICT_COLORS: Record<string, string> = {
    '看多': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
    '看空': 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
    '中性': 'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400',
    '谨慎': 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
    _default: 'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400',
}

// ── 子组件：Agent 卡片 (恢复原始比例与高对比度) ──────────────────────────────────

interface CardData extends AgentMeta { 
    status: AgentStatus; 
    isStreaming: boolean; 
    verdict: Verdict | null;
    description?: string;
    isParticipating: boolean; 
}

function AgentCard({ card, selected, onClick }: { card: CardData; selected?: boolean; onClick?: () => void }) {
    const active  = card.status === 'in_progress'
    const done    = card.status === 'completed'
    const skipped = card.status === 'skipped'
    const participating = card.isParticipating
    const clickable = !!card.section && (done || active)
    const { Icon } = card

    // Helper to parse description into verdict format
    const displayVerdict = useMemo(() => {
        if (card.verdict) return card.verdict
        if (card.description) {
            const parts = card.description.split(/[:：]/)
            if (parts.length >= 2) {
                return { direction: parts[0].trim(), reason: parts.slice(1).join(':').trim() }
            }
            return { direction: '结论', reason: card.description }
        }
        return null
    }, [card.verdict, card.description])

    return (
        <button
            type="button"
            disabled={!clickable}
            onClick={() => clickable && onClick?.()}
            className={[
                'group relative w-full text-left rounded-xl border transition-all duration-300 overflow-hidden',
                !participating ? 'grayscale opacity-30 scale-95 border-slate-100 dark:border-slate-800' : 'opacity-100',
                selected
                    ? 'border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-500/10 shadow-lg ring-2 ring-blue-400/30'
                    : active
                    ? 'border-blue-400/60 dark:border-blue-500/60 bg-white dark:bg-slate-800 shadow-[0_0_12px_rgba(59,130,246,0.2)] z-10'
                    : done
                    ? 'border-emerald-300 dark:border-emerald-500/50 bg-emerald-50/30 dark:bg-slate-800/60 shadow-sm'
                    : skipped
                    ? 'border-slate-100 dark:border-slate-800 bg-transparent opacity-40'
                    : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm',
                clickable ? 'cursor-pointer hover:border-slate-400 dark:hover:border-slate-500' : 'cursor-default',
            ].join(' ')}
        >
            <div className="p-4 relative z-10">
                <div className="flex items-start gap-3 mb-3">
                    <div className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-500 ${active ? 'scale-110 shadow-blue-400/20' : ''} ${card.badgeBg}`}>
                        {active
                            ? <Loader2 className={`w-5 h-5 animate-spin ${card.badgeText}`} />
                            : <Icon className={`w-5 h-5 ${card.badgeText}`} />
                        }
                    </div>
                    <div className="min-w-0 flex-1 pt-0.5">
                        <div className={`text-[14px] font-bold leading-tight transition-colors ${active ? 'text-blue-600 dark:text-blue-400' : 'text-slate-900 dark:text-slate-100'}`}>
                            {card.label}
                        </div>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight mt-1 line-clamp-1">
                            {card.goal}
                        </div>
                    </div>
                    <span className={[
                        'shrink-0 mt-0.5 text-[10px] px-2 py-0.5 rounded-full font-bold transition-all duration-300 shadow-sm',
                        active  ? 'bg-blue-600 text-white animate-pulse'
                        : done  ? 'bg-emerald-500 text-white'
                        : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400',
                    ].join(' ')}>
                        {STATUS_LABEL[card.status]}
                    </span>
                </div>

                {(done || active) && (
                    <div className={`rounded-lg border px-3 py-2.5 transition-all duration-500 ${card.sumBorder} ${card.sumBg}`}>
                        {active ? (
                            <div className="flex items-center gap-2 py-0.5">
                                <span className="flex gap-1">
                                    <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                                    <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                                    <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" />
                                </span>
                                <span className="text-[11px] font-bold text-blue-600 dark:text-blue-400 tracking-wide">智能体正全力研判...</span>
                            </div>
                        ) : displayVerdict ? (
                            <div className="flex items-start gap-2 min-w-0">
                                <span className={`shrink-0 text-[10px] font-black px-2 py-0.5 rounded-full leading-tight shadow-sm ${VERDICT_COLORS[displayVerdict.direction] ?? VERDICT_COLORS._default}`}>
                                    {displayVerdict.direction}
                                </span>
                                <span className={`text-[12px] font-medium leading-[1.4] ${card.sumText} line-clamp-2`}>
                                    {displayVerdict.reason}
                                </span>
                            </div>
                        ) : (
                            <div className="flex items-center gap-1.5">
                                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                                <span className="text-[12px] text-emerald-600 dark:text-emerald-400 font-bold">交付深度研报完成</span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </button>
    )
}

// ── 主组件 ────────────────────────────────────────────────────────────────────

interface AgentCollaborationProps {
    onSelectSection: (section?: string) => void
    selectedSection?: string
}

export default function AgentCollaboration({ onSelectSection, selectedSection }: AgentCollaborationProps) {
    const { agents, isAnalyzing, streamingSections, report, currentHorizon } = useAnalysisStore()

    const cards = useMemo(() => META.map((meta) => {
        const agent       = agents.find(a => a.name === meta.name)
        const streamState = meta.section ? streamingSections[meta.section] : undefined
        const stored      = meta.section ? (report?.[meta.section as keyof typeof report] as string | undefined) : undefined
        const src         = streamState?.displayed || stored || ''
        
        // 判定 Agent 是否参与：如果是分析中，且不是 skipped
        const isParticipating = isAnalyzing ? (agent ? agent.status !== 'skipped' : false) : true

        return {
            ...meta,
            status:      (agent?.status ?? 'pending') as AgentStatus,
            description: agent?.description,
            isStreaming: !!streamState?.isTyping,
            verdict:     extractVerdict(src),
            isParticipating,
        }
    }), [agents, report, streamingSections, isAnalyzing])

    const cardMap = new Map(cards.map(c => [c.name, c]))
    const doneN = cards.filter(c => c.status === 'completed').length
    // 进度分母：排除 skipped，无论是否正在分析
    const participatingCount = cards.filter(c => c.status !== 'skipped').length

    return (
        <section className="card relative overflow-hidden bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
            {/* 标题栏 */}
            <div className="flex items-center justify-between mb-8 relative z-10 border-b border-slate-100 dark:border-slate-800 pb-4">
                <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${isAnalyzing ? 'bg-blue-500 animate-pulse shadow-[0_0_12px_#3b82f6]' : 'bg-slate-300'}`} />
                    <h3 className="text-lg font-black text-slate-900 dark:text-white tracking-tighter uppercase">
                        TradingAgents 协同工作流
                    </h3>
                </div>
                {isAnalyzing && (
                    <div className="flex items-center gap-4">
                        {currentHorizon && (
                            <span className={`px-3 py-1 rounded-full text-[11px] font-black tracking-widest border animate-in fade-in duration-300 ${
                                currentHorizon === 'short'
                                ? 'bg-blue-600/10 text-blue-600 dark:text-blue-400 border-blue-400/30'
                                : 'bg-purple-600/10 text-purple-600 dark:text-purple-400 border-purple-400/30'
                            }`}>
                                {currentHorizon === 'short' ? '⚡ 短线视角' : '🔭 中线视角'}
                            </span>
                        )}
                        <div className="text-right">
                            <div className="text-2xl font-black text-blue-600 dark:text-blue-400 tabular-nums">
                                {participatingCount > 0 ? Math.round((doneN / participatingCount) * 100) : 0}%
                            </div>
                            <p className="text-[10px] font-black text-slate-400 uppercase tracking-tighter">分析总进度</p>
                        </div>
                    </div>
                )}
            </div>

            <div className="space-y-8 relative z-10">
                {GROUPS.map((group, gi) => {
                    const gc = group.agents.map(n => cardMap.get(n)).filter(Boolean) as CardData[]
                    const anyParticipating = gc.some(c => c.isParticipating)
                    const anyAct = gc.some(c => c.status === 'in_progress')
                    const allDone = gc.every(c => !c.isParticipating || c.status === 'completed' || c.status === 'skipped')
                    
                    const nextGroupParticipating = gi < GROUPS.length - 1 && GROUPS[gi+1].agents.some(n => cardMap.get(n)?.isParticipating)

                    if (isAnalyzing && !anyParticipating) return null

                    return (
                        <div key={group.title} className="animate-in fade-in duration-700">
                            {/* 分组标题与预判光流 */}
                            <div className="flex items-center gap-4 mb-5">
                                <div className={`relative flex items-center justify-center w-8 h-8 rounded-xl text-[12px] font-black transition-all duration-500 shadow-sm ${
                                    anyAct ? 'bg-blue-600 text-white rotate-6 shadow-blue-400/40' : 
                                    allDone && anyParticipating ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-400 dark:bg-slate-800'
                                }`}>
                                    {gi + 1}
                                    {anyAct && <div className="absolute inset-0 rounded-xl border-2 border-blue-500 animate-ping opacity-30" />}
                                </div>
                                <span className={`text-sm font-black uppercase tracking-widest transition-colors duration-300 ${
                                    anyAct  ? 'text-blue-600 dark:text-blue-400'
                                    : allDone && anyParticipating ? 'text-emerald-600 dark:text-emerald-400'
                                    : 'text-slate-500 dark:text-slate-400'
                                }`}>
                                    {group.title}
                                </span>
                                <div className="relative flex-1 h-[2px] bg-slate-100 dark:bg-slate-800/50 rounded-full overflow-hidden">
                                    {/* 核心修复：预判流动连线，只要分析中且属于路径即全线开启流动 */}
                                    {isAnalyzing && anyParticipating && nextGroupParticipating && (
                                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-500 to-transparent animate-flowing-light" 
                                             style={{ backgroundSize: '200% 100%' }} />
                                    )}
                                    {allDone && anyParticipating && (
                                        <div className="absolute inset-0 bg-emerald-500/40 shadow-[0_0_10px_#10b981]" />
                                    )}
                                </div>
                            </div>

                            {/* Agent 磁贴网格 */}
                            <div className={`grid gap-5 ${group.cols}`}>
                                {gc.map(card => (
                                    <AgentCard
                                        key={card.name}
                                        card={card}
                                        selected={!!card.section && card.section === selectedSection}
                                        onClick={() => card.section && onSelectSection?.(card.section === selectedSection ? undefined : card.section)}
                                    />
                                ))}
                            </div>
                        </div>
                    )
                })}
            </div>

            <style dangerouslySetInnerHTML={{ __html: `
                @keyframes flowing-light {
                    0% { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                }
                .animate-flowing-light {
                    animation: flowing-light 2s linear infinite;
                }
                @keyframes gradient-x {
                    0% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                    100% { background-position: 0% 50%; }
                }
                .animate-gradient-x {
                    background-size: 200% 200%;
                    animation: gradient-x 8s ease infinite;
                }
            `}} />
        </section>
    )
}
