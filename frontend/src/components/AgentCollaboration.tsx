import { useMemo, useCallback, memo } from 'react'
import {
    ReactFlow,
    Handle,
    Position,
    MarkerType,
    type Node,
    type Edge,
    type NodeProps,
    type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useAnalysisStore } from '@/stores/analysisStore'
import type { AgentStatus } from '@/types'
import {
    TrendingUp, MessageCircle, Newspaper, Calculator,
    BarChart2, DollarSign, ArrowBigUp, ArrowBigDown,
    Brain, Briefcase, Flame, Scale, Shield, CheckCircle2, Loader2,
    Activity,
} from 'lucide-react'
import { extractVerdict, type Verdict } from '@/utils/reportText'

// ── Agent 元数据 ──────────────────────────────────────────────────────────────

interface AgentMeta {
    name: string
    label: string
    goal: string
    section?: string
    debate?: 'research' | 'risk'
    Icon: React.FC<{ className?: string }>
    badgeBg: string
    badgeText: string
}

const META: AgentMeta[] = [
    { name: 'Market Analyst', label: '技术面', goal: '技术指标与价格形态分析', section: 'market_report', Icon: TrendingUp, badgeBg: 'bg-blue-100 dark:bg-blue-500/20', badgeText: 'text-blue-600 dark:text-blue-400' },
    { name: 'Social Analyst', label: '舆情', goal: '舆论情绪与社交媒体分析', section: 'sentiment_report', Icon: MessageCircle, badgeBg: 'bg-fuchsia-100 dark:bg-fuchsia-500/20', badgeText: 'text-fuchsia-600 dark:text-fuchsia-400' },
    { name: 'News Analyst', label: '新闻', goal: '政策资讯与行业动态分析', section: 'news_report', Icon: Newspaper, badgeBg: 'bg-cyan-100 dark:bg-cyan-500/20', badgeText: 'text-cyan-600 dark:text-cyan-400' },
    { name: 'Fundamentals Analyst', label: '基本面', goal: '财务报表与估值分析', section: 'fundamentals_report', Icon: Calculator, badgeBg: 'bg-emerald-100 dark:bg-emerald-500/20', badgeText: 'text-emerald-600 dark:text-emerald-400' },
    { name: 'Macro Analyst', label: '宏观', goal: '板块轮动与政策驱动分析', section: 'macro_report', Icon: BarChart2, badgeBg: 'bg-violet-100 dark:bg-violet-500/20', badgeText: 'text-violet-600 dark:text-violet-400' },
    { name: 'Smart Money Analyst', label: '主力资金', goal: '机构资金行为与龙虎榜', section: 'smart_money_report', Icon: DollarSign, badgeBg: 'bg-amber-100 dark:bg-amber-500/20', badgeText: 'text-amber-600 dark:text-amber-400' },
    { name: 'Volume Price Analyst', label: '量价', goal: '成交量与价格形态分析', section: 'volume_price_report', Icon: Activity, badgeBg: 'bg-rose-100 dark:bg-rose-500/20', badgeText: 'text-rose-600 dark:text-rose-400' },
    { name: 'Bull Researcher', label: '多头', goal: '评估投资价值与上行潜力', section: 'investment_plan', debate: 'research', Icon: ArrowBigUp, badgeBg: 'bg-emerald-100 dark:bg-emerald-500/20', badgeText: 'text-emerald-600 dark:text-emerald-400' },
    { name: 'Bear Researcher', label: '空头', goal: '评估下行风险与潜在危机', section: 'investment_plan', debate: 'research', Icon: ArrowBigDown, badgeBg: 'bg-rose-100 dark:bg-rose-500/20', badgeText: 'text-rose-600 dark:text-rose-400' },
    { name: 'Research Manager', label: '研究总监', goal: '综合多空论据形成投资计划', section: 'investment_plan', debate: 'research', Icon: Brain, badgeBg: 'bg-indigo-100 dark:bg-indigo-500/20', badgeText: 'text-indigo-600 dark:text-indigo-400' },
    { name: 'Trader', label: '交易员', goal: '将研究结论转化为可执行指令', section: 'trader_investment_plan', Icon: Briefcase, badgeBg: 'bg-orange-100 dark:bg-orange-500/20', badgeText: 'text-orange-600 dark:text-orange-400' },
    { name: 'Aggressive Analyst', label: '激进', goal: '高风险高收益策略约束', section: 'final_trade_decision', debate: 'risk', Icon: Flame, badgeBg: 'bg-red-100 dark:bg-red-500/20', badgeText: 'text-red-600 dark:text-red-400' },
    { name: 'Neutral Analyst', label: '中性', goal: '均衡风险收益策略约束', section: 'final_trade_decision', debate: 'risk', Icon: Scale, badgeBg: 'bg-slate-100 dark:bg-slate-500/20', badgeText: 'text-slate-600 dark:text-slate-400' },
    { name: 'Conservative Analyst', label: '稳健', goal: '低风险保守策略约束', section: 'final_trade_decision', debate: 'risk', Icon: Shield, badgeBg: 'bg-amber-100 dark:bg-amber-500/20', badgeText: 'text-amber-600 dark:text-amber-400' },
    { name: 'Portfolio Manager', label: '组合经理', goal: '综合裁决形成最终决策', section: 'final_trade_decision', debate: 'risk', Icon: CheckCircle2, badgeBg: 'bg-teal-100 dark:bg-teal-500/20', badgeText: 'text-teal-600 dark:text-teal-400' },
]

const STATUS_LABEL: Record<AgentStatus, string> = {
    pending: '待命', in_progress: '分析中', completed: '完成', skipped: '跳过', error: '异常',
}

const VERDICT_COLORS: Record<string, string> = {
    '看多': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
    '偏多': 'bg-teal-100 text-teal-700 dark:bg-teal-500/20 dark:text-teal-300',
    '中性': 'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400',
    '偏空': 'bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-300',
    '看空': 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
    '谨慎': 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300', // 向后兼容旧报告
    _default: 'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400',
}

// ── 流程图布局 ────────────────────────────────────────────────────────────────

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
    // 左列：数据源分析师（间距 110，verdict 展开后不重叠）
    'Market Analyst':       { x: 0, y: 0 },
    'Social Analyst':       { x: 0, y: 110 },
    'News Analyst':         { x: 0, y: 220 },
    'Fundamentals Analyst': { x: 0, y: 330 },
    'Macro Analyst':        { x: 0, y: 440 },
    'Smart Money Analyst':  { x: 0, y: 550 },
    'Volume Price Analyst': { x: 0, y: 660 },
    // 研究团队（靠近左侧分析师）
    'Bull Researcher':      { x: 470, y: 80 },
    'Research Manager':     { x: 630, y: 240 },
    'Bear Researcher':      { x: 470, y: 400 },
    // 交易员
    'Trader':               { x: 890, y: 240 },
    // 风控团队
    'Aggressive Analyst':   { x: 1180, y: 80 },
    'Neutral Analyst':      { x: 1180, y: 240 },
    'Conservative Analyst': { x: 1180, y: 400 },
    // 组合经理
    'Portfolio Manager':    { x: 1470, y: 240 },
}

// 需要额外 handle 的节点（用于辩论连线）
const BOTTOM_HANDLE_NODES = new Set(['Bull Researcher'])
const TOP_HANDLE_NODES = new Set(['Bear Researcher'])

// 边定义
interface EdgeDef {
    source: string
    target: string
    sourceHandle?: string
    targetHandle?: string
    label?: string
    bidirectional?: boolean
    thin?: boolean
}

const EDGE_DEFS: EdgeDef[] = [
    // 数据源 → 多空研究员
    ...['Market Analyst', 'Social Analyst', 'News Analyst', 'Fundamentals Analyst', 'Macro Analyst', 'Smart Money Analyst', 'Volume Price Analyst']
        .map(s => ({ source: s, target: 'Bull Researcher', thin: true } as EdgeDef)),
    ...['Market Analyst', 'Social Analyst', 'News Analyst', 'Fundamentals Analyst', 'Macro Analyst', 'Smart Money Analyst', 'Volume Price Analyst']
        .map(s => ({ source: s, target: 'Bear Researcher', thin: true } as EdgeDef)),
    // 多空辩论（双向）
    { source: 'Bull Researcher', target: 'Bear Researcher', sourceHandle: 'bottom', targetHandle: 'top', label: '辩论', bidirectional: true },
    // 研究员 → 研究总监
    { source: 'Bull Researcher', target: 'Research Manager' },
    { source: 'Bear Researcher', target: 'Research Manager' },
    // 研究总监 → 交易员
    { source: 'Research Manager', target: 'Trader', label: '投资计划' },
    // 交易员 → 风控
    { source: 'Trader', target: 'Aggressive Analyst' },
    { source: 'Trader', target: 'Neutral Analyst', label: '交易方案' },
    { source: 'Trader', target: 'Conservative Analyst' },
    // 风控 → 组合经理
    { source: 'Aggressive Analyst', target: 'Portfolio Manager' },
    { source: 'Neutral Analyst', target: 'Portfolio Manager' },
    { source: 'Conservative Analyst', target: 'Portfolio Manager' },
]

// ── 分组标签节点 ──────────────────────────────────────────────────────────────

interface GroupLabelDef {
    id: string
    label: string
    position: { x: number; y: number }
    width: number
    height: number
}

const GROUP_LABELS: GroupLabelDef[] = [
    { id: 'group-sources', label: '技术分析', position: { x: -16, y: -30 }, width: 248, height: 870 },
    { id: 'group-research', label: '研究团队', position: { x: 454, y: 44 }, width: 410, height: 450 },
    { id: 'group-risk', label: '风控团队', position: { x: 1164, y: 44 }, width: 248, height: 450 },
]

// ── 自定义节点组件 ────────────────────────────────────────────────────────────

interface AgentNodeData {
    meta: AgentMeta
    status: AgentStatus
    verdict: Verdict | null
    isParticipating: boolean
    selected: boolean
    [key: string]: unknown
}

type AgentFlowNode = Node<AgentNodeData, 'agent'>
type GroupLabelNodeData = {
    label: string
    width: number
    height: number
    [key: string]: unknown
}
type GroupLabelFlowNode = Node<GroupLabelNodeData, 'groupLabel'>

function AgentNodeComponent({ data }: NodeProps<AgentFlowNode>) {
    const { meta, status, verdict, isParticipating, selected } = data
    const active = status === 'in_progress'
    const done = status === 'completed'
    const skipped = status === 'skipped'
    const { Icon } = meta

    return (
        <div
            className={[
                'px-4 py-3 rounded-xl border transition-all duration-300 min-w-[210px] max-w-[218px]',
                !isParticipating ? 'opacity-30 grayscale' : '',
                selected
                    ? 'border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-500/10 shadow-lg ring-2 ring-blue-400/30'
                    : active
                    ? 'border-blue-400 dark:border-blue-500/60 bg-white dark:bg-slate-800 shadow-[0_0_14px_rgba(59,130,246,0.25)]'
                    : done
                    ? 'border-emerald-300 dark:border-emerald-500/50 bg-white dark:bg-slate-800/80 shadow-sm'
                    : skipped
                    ? 'border-slate-100 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 opacity-40'
                    : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm',
            ].join(' ')}
        >
            {/* Handles */}
            <Handle type="target" position={Position.Left} id="left"
                className="!w-2 !h-2 !bg-slate-300 dark:!bg-slate-600 !border-0 !min-w-0 !min-h-0" />
            <Handle type="source" position={Position.Right} id="right"
                className="!w-2 !h-2 !bg-slate-300 dark:!bg-slate-600 !border-0 !min-w-0 !min-h-0" />

            {BOTTOM_HANDLE_NODES.has(meta.name) && (
                <Handle type="source" position={Position.Bottom} id="bottom"
                    className="!w-2 !h-2 !bg-slate-300 dark:!bg-slate-600 !border-0 !min-w-0 !min-h-0" />
            )}
            {TOP_HANDLE_NODES.has(meta.name) && (
                <Handle type="target" position={Position.Top} id="top"
                    className="!w-2 !h-2 !bg-slate-300 dark:!bg-slate-600 !border-0 !min-w-0 !min-h-0" />
            )}

            {/* 第一行：图标 + 标签 + 状态 */}
            <div className="flex items-center gap-2.5">
                <div className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${meta.badgeBg}`}>
                    {active
                        ? <Loader2 className={`w-[18px] h-[18px] animate-spin ${meta.badgeText}`} />
                        : <Icon className={`w-[18px] h-[18px] ${meta.badgeText}`} />}
                </div>
                <span className={`text-[15px] font-bold flex-1 leading-tight ${active ? 'text-blue-600 dark:text-blue-400' : 'text-slate-800 dark:text-slate-200'}`}>
                    {meta.label}
                </span>
                <span className={[
                    'shrink-0 text-[11px] px-2 py-0.5 rounded-full font-bold',
                    active ? 'bg-blue-600 text-white animate-pulse'
                        : done ? 'bg-emerald-500 text-white'
                        : 'bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500',
                ].join(' ')}>
                    {STATUS_LABEL[status]}
                </span>
            </div>

            {/* 第二行：分析中动画 */}
            {active && (
                <div className="flex items-center gap-2 mt-2">
                    <span className="flex gap-1">
                        <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                        <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                        <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" />
                    </span>
                    <span className="text-[12px] text-blue-600 dark:text-blue-400 font-bold">研判中...</span>
                </div>
            )}

            {/* 第二行：完成后的判定结果 */}
            {done && verdict && (
                <div className="flex items-start gap-2 mt-2 min-w-0">
                    <span className={`shrink-0 mt-0.5 text-[11px] font-black px-2 py-0.5 rounded-full leading-none ${VERDICT_COLORS[verdict.direction] ?? VERDICT_COLORS._default}`}>
                        {verdict.direction}
                    </span>
                    <span className="text-[12px] text-slate-500 dark:text-slate-400 leading-snug line-clamp-2">
                        {verdict.reason}
                    </span>
                </div>
            )}

            {done && !verdict && (
                <div className="flex items-center gap-1.5 mt-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                    <span className="text-[12px] text-emerald-600 dark:text-emerald-400 font-bold">完成</span>
                </div>
            )}
        </div>
    )
}

// 分组背景标签节点
function GroupLabelNode({ data }: NodeProps<GroupLabelFlowNode>) {
    return (
        <div
            className="rounded-2xl border-2 border-dashed border-slate-200 dark:border-slate-700/60 pointer-events-none"
            style={{ width: data.width, height: data.height }}
        >
            <div className="absolute -top-3 left-4 px-2 bg-white dark:bg-slate-900">
                <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest">
                    {data.label}
                </span>
            </div>
        </div>
    )
}

const nodeTypes: NodeTypes = {
    agent: memo(AgentNodeComponent),
    groupLabel: memo(GroupLabelNode),
}

// ── 主组件 ────────────────────────────────────────────────────────────────────

interface AgentCollaborationProps {
    onSelectSection: (section?: string) => void
    onOpenDebate: (debate: 'research' | 'risk') => void
    selectedSection?: string
}

export default function AgentCollaboration({ onSelectSection, onOpenDebate, selectedSection }: AgentCollaborationProps) {
    const { agents, isAnalyzing, streamingSections, report, currentHorizon } = useAnalysisStore()

    const cards = useMemo(() => META.map((meta) => {
        const agent = agents.find(a => a.name === meta.name)
        const streamState = meta.section ? streamingSections[meta.section] : undefined
        const stored = meta.section ? (report?.[meta.section as keyof typeof report] as string | undefined) : undefined
        const src = streamState?.displayed || stored || ''
        const isParticipating = isAnalyzing ? (agent ? agent.status !== 'skipped' : false) : true

        return {
            meta,
            status: (agent?.status ?? 'pending') as AgentStatus,
            isStreaming: !!streamState?.isTyping,
            verdict: extractVerdict(src),
            isParticipating,
        }
    }), [agents, report, streamingSections, isAnalyzing])

    const cardMap = useMemo(() => new Map(cards.map(c => [c.meta.name, c])), [cards])
    const doneN = cards.filter(c => c.status === 'completed').length
    const participatingCount = cards.filter(c => c.status !== 'skipped').length

    // 构建 React Flow 节点
    const nodes: (AgentFlowNode | GroupLabelFlowNode)[] = useMemo(() => {
        const agentNodes: AgentFlowNode[] = cards.map(card => ({
            id: card.meta.name,
            type: 'agent',
            position: NODE_POSITIONS[card.meta.name] ?? { x: 0, y: 0 },
            data: {
                meta: card.meta,
                status: card.status,
                verdict: card.verdict,
                isParticipating: card.isParticipating,
                selected: !!card.meta.section && card.meta.section === selectedSection,
            } satisfies AgentNodeData,
        }))

        const labelNodes: GroupLabelFlowNode[] = GROUP_LABELS.map(g => ({
            id: g.id,
            type: 'groupLabel',
            position: g.position,
            data: { label: g.label, width: g.width, height: g.height },
            selectable: false,
            draggable: false,
            zIndex: -1,
        }))

        return [...labelNodes, ...agentNodes]
    }, [cards, selectedSection])

    // 构建 React Flow 边
    const edges: Edge[] = useMemo(() => {
        return EDGE_DEFS.map((def, i) => {
            const sourceCard = cardMap.get(def.source)
            const targetCard = cardMap.get(def.target)
            const sourceDone = sourceCard?.status === 'completed'
            const targetActive = targetCard?.status === 'in_progress'

            const color = sourceDone ? '#10b981' : targetActive ? '#3b82f6' : '#cbd5e1'

            return {
                id: `e-${i}`,
                source: def.source,
                target: def.target,
                sourceHandle: def.sourceHandle ?? 'right',
                targetHandle: def.targetHandle ?? 'left',
                type: 'default',
                animated: targetActive,
                label: def.label,
                labelStyle: { fontSize: 10, fontWeight: 600, fill: '#64748b' },
                labelBgStyle: { fill: 'white', fillOpacity: 0.85 },
                labelBgPadding: [4, 2] as [number, number],
                labelBgBorderRadius: 4,
                style: {
                    stroke: color,
                    strokeWidth: def.thin ? 1 : 1.5,
                    opacity: def.thin ? 0.6 : 1,
                },
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color,
                    width: 16,
                    height: 16,
                },
                ...(def.bidirectional && {
                    markerStart: {
                        type: MarkerType.ArrowClosed,
                        color,
                        width: 16,
                        height: 16,
                    },
                }),
            } satisfies Edge
        })
    }, [cardMap])

    // 节点点击
    const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
        const card = cardMap.get(node.id)
        if (!card) return
        if (card.status !== 'completed' && card.status !== 'in_progress') return

        if (card.meta.debate) {
            onOpenDebate(card.meta.debate)
            if (card.meta.section) onSelectSection(card.meta.section)
        } else if (card.meta.section) {
            onSelectSection(card.meta.section === selectedSection ? undefined : card.meta.section)
        }
    }, [cardMap, selectedSection, onSelectSection, onOpenDebate])

    return (
        <section className="card relative overflow-hidden bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
            {/* 标题栏 */}
            <div className="flex items-center justify-between mb-2 relative z-10 border-b border-slate-100 dark:border-slate-800 pb-4">
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

            {/* React Flow 画布 */}
            <div className="h-[820px] w-full">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    nodeTypes={nodeTypes}
                    onNodeClick={handleNodeClick}
                    defaultViewport={{ x: 20, y: 20, zoom: 1 }}
                    nodesDraggable={false}
                    nodesConnectable={false}
                    nodesFocusable={false}
                    edgesFocusable={false}
                    panOnDrag
                    panOnScroll={false}
                    zoomOnScroll={false}
                    zoomOnPinch={false}
                    zoomOnDoubleClick={false}
                    preventScrolling={false}
                    translateExtent={[[-40, -40], [1730, 800]]}
                    proOptions={{ hideAttribution: true }}
                />
            </div>
        </section>
    )
}
