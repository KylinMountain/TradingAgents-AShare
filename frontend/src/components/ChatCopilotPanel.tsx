import { FormEvent, useState, useRef, useEffect } from 'react'
import {
    Bot, Loader2, Send, Sparkles, Settings2, ChevronDown, ChevronUp, FileText, ChevronRight,
    TrendingUp, MessageCircle, Newspaper, Calculator, BarChart2, DollarSign,
    Swords, ArrowBigUp, ArrowBigDown, Brain, Briefcase, Flame, Scale, Shield, CheckCircle2,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '@/services/api'
import { useAnalysisStore } from '@/stores/analysisStore'
import type {
    AgentReportEvent,
    AgentSnapshotEvent,
    AgentStatusEvent,
    AnalysisReport,
    ReportChunkEvent,
    Report,
} from '@/types'

interface ChatCopilotPanelProps {
    onSymbolDetected: (symbol: string) => void
    onShowReport?: (section?: string) => void
    initialInput?: string
}

const ANALYST_OPTIONS = [
    { id: 'market', label: '市场分析', description: '技术面' },
    { id: 'social', label: '舆情分析', description: '社交媒体' },
    { id: 'news', label: '新闻分析', description: '财经新闻' },
    { id: 'fundamentals', label: '基本面', description: '财务估值' },
    { id: 'macro', label: '宏观板块', description: '宏观经济' },
    { id: 'smart_money', label: '主力资金', description: '机构动向' },
]

interface StreamEvent {
    event: string
    data: Record<string, unknown>
}

const PRESET_PROMPTS = [
    '分析一下贵州茅台(600519.SH)今天走势',
    '请分析稀土ETF嘉实(516150)在2026-03-03的情况',
    '分析宁德时代300750.SZ，给出交易建议',
]

const REPORT_SECTION_TITLES: Record<string, string> = {
    market_report: '市场分析报告',
    sentiment_report: '舆情分析报告',
    news_report: '新闻分析报告',
    fundamentals_report: '基本面分析报告',
    macro_report: '宏观分析报告',
    smart_money_report: '主力资金分析报告',
    game_theory_report: '博弈裁判报告',
    investment_plan: '研究团队投资计划',
    trader_investment_plan: '交易员计划',
    final_trade_decision: '最终交易决策',
}

// Section → Lucide 图标 + 颜色（与 AGENT_META_MAP 保持一致）
const SECTION_META: Record<string, { Icon: React.FC<{ className?: string }>; iconCls: string; bgCls: string }> = {
    market_report:          { Icon: TrendingUp,    iconCls: 'text-blue-500',    bgCls: 'bg-blue-100 dark:bg-blue-500/20' },
    sentiment_report:       { Icon: MessageCircle, iconCls: 'text-fuchsia-500', bgCls: 'bg-fuchsia-100 dark:bg-fuchsia-500/20' },
    news_report:            { Icon: Newspaper,     iconCls: 'text-cyan-500',    bgCls: 'bg-cyan-100 dark:bg-cyan-500/20' },
    fundamentals_report:    { Icon: Calculator,    iconCls: 'text-emerald-500', bgCls: 'bg-emerald-100 dark:bg-emerald-500/20' },
    macro_report:           { Icon: BarChart2,     iconCls: 'text-violet-500',  bgCls: 'bg-violet-100 dark:bg-violet-500/20' },
    smart_money_report:     { Icon: DollarSign,    iconCls: 'text-amber-500',   bgCls: 'bg-amber-100 dark:bg-amber-500/20' },
    game_theory_report:     { Icon: Swords,        iconCls: 'text-rose-500',    bgCls: 'bg-rose-100 dark:bg-rose-500/20' },
    investment_plan:        { Icon: Brain,         iconCls: 'text-indigo-500',  bgCls: 'bg-indigo-100 dark:bg-indigo-500/20' },
    trader_investment_plan: { Icon: Briefcase,     iconCls: 'text-orange-500',  bgCls: 'bg-orange-100 dark:bg-orange-500/20' },
    final_trade_decision:   { Icon: CheckCircle2,  iconCls: 'text-teal-500',    bgCls: 'bg-teal-100 dark:bg-teal-500/20' },
}

// 与 AgentCollaboration.tsx 保持一致的图标 + 颜色体系
const AGENT_META_MAP: Record<string, { Icon: React.FC<{ className?: string }>; iconCls: string; bgCls: string; label: string }> = {
    'Market Analyst':       { Icon: TrendingUp,   iconCls: 'text-blue-500',    bgCls: 'bg-blue-100 dark:bg-blue-500/20',    label: '技术面' },
    'Social Analyst':       { Icon: MessageCircle, iconCls: 'text-fuchsia-500', bgCls: 'bg-fuchsia-100 dark:bg-fuchsia-500/20', label: '舆情' },
    'News Analyst':         { Icon: Newspaper,     iconCls: 'text-cyan-500',    bgCls: 'bg-cyan-100 dark:bg-cyan-500/20',    label: '新闻' },
    'Fundamentals Analyst': { Icon: Calculator,    iconCls: 'text-emerald-500', bgCls: 'bg-emerald-100 dark:bg-emerald-500/20', label: '基本面' },
    'Macro Analyst':        { Icon: BarChart2,     iconCls: 'text-violet-500',  bgCls: 'bg-violet-100 dark:bg-violet-500/20', label: '宏观' },
    'Smart Money Analyst':  { Icon: DollarSign,    iconCls: 'text-amber-500',   bgCls: 'bg-amber-100 dark:bg-amber-500/20',  label: '主力资金' },
    'Game Theory Manager':  { Icon: Swords,        iconCls: 'text-rose-500',    bgCls: 'bg-rose-100 dark:bg-rose-500/20',    label: '博弈裁判' },
    'Bull Researcher':      { Icon: ArrowBigUp,    iconCls: 'text-emerald-500', bgCls: 'bg-emerald-100 dark:bg-emerald-500/20', label: '多头' },
    'Bear Researcher':      { Icon: ArrowBigDown,  iconCls: 'text-rose-500',    bgCls: 'bg-rose-100 dark:bg-rose-500/20',    label: '空头' },
    'Research Manager':     { Icon: Brain,         iconCls: 'text-indigo-500',  bgCls: 'bg-indigo-100 dark:bg-indigo-500/20', label: '研究总监' },
    'Trader':               { Icon: Briefcase,     iconCls: 'text-orange-500',  bgCls: 'bg-orange-100 dark:bg-orange-500/20', label: '交易员' },
    'Aggressive Analyst':   { Icon: Flame,         iconCls: 'text-red-500',     bgCls: 'bg-red-100 dark:bg-red-500/20',      label: '激进' },
    'Neutral Analyst':      { Icon: Scale,         iconCls: 'text-slate-500',   bgCls: 'bg-slate-100 dark:bg-slate-500/20',  label: '中性' },
    'Conservative Analyst': { Icon: Shield,        iconCls: 'text-amber-500',   bgCls: 'bg-amber-100 dark:bg-amber-500/20',  label: '稳健' },
    'Portfolio Manager':    { Icon: CheckCircle2,  iconCls: 'text-teal-500',    bgCls: 'bg-teal-100 dark:bg-teal-500/20',    label: '组合经理' },
    '意图解析':             { Icon: Bot,            iconCls: 'text-slate-400',   bgCls: 'bg-slate-100 dark:bg-slate-700',     label: '意图解析' },
}

function ReportCard({
    section,
    content,
    streaming,
    onOpen,
}: {
    section: string
    content: string
    streaming: boolean
    onOpen: () => void
}) {
    const title = REPORT_SECTION_TITLES[section] || section
    const meta = SECTION_META[section]
    const preview = content.replace(/^#+\s*/gm, '').replace(/\*\*/g, '').slice(0, 80)

    const IconEl = meta?.Icon || FileText
    const iconCls = meta?.iconCls || 'text-slate-400'
    const bgCls = meta?.bgCls || 'bg-slate-100 dark:bg-slate-700'

    if (streaming) {
        return (
            <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-blue-500/10 border border-blue-500/20 text-sm">
                <span className={`inline-flex items-center justify-center w-7 h-7 rounded-lg ${bgCls} shrink-0`}>
                    <IconEl className={`w-4 h-4 ${iconCls}`} />
                </span>
                <span className="text-blue-300 font-medium text-xs">{title}</span>
                <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0 ml-auto" />
            </div>
        )
    }

    return (
        <button
            onClick={onOpen}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/50 hover:border-blue-400 dark:hover:border-blue-500/40 hover:bg-blue-50 dark:hover:bg-slate-800 transition-all text-left group"
        >
            <span className={`inline-flex items-center justify-center w-7 h-7 rounded-lg ${bgCls} shrink-0`}>
                <IconEl className={`w-4 h-4 ${iconCls}`} />
            </span>
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200 group-hover:text-blue-600 dark:group-hover:text-blue-300 transition-colors">{title}</p>
                <p className="text-xs text-slate-500 truncate mt-0.5">{preview}...</p>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-blue-400 shrink-0 transition-colors" />
        </button>
    )
}

export default function ChatCopilotPanel({ onSymbolDetected, onShowReport, initialInput }: ChatCopilotPanelProps) {
    const [input, setInput] = useState(initialInput || '')
    const [streaming, setStreaming] = useState(false)
    const [showConfig, setShowConfig] = useState(false)
    // Use refs for high-frequency token tracking to avoid re-renders on every token
    const pendingAgentMsgIdsRef = useRef<Set<string>>(new Set())
    const completedAgentMsgIdsRef = useRef<Set<string>>(new Set())
    // Only used to trigger re-render when agent card status actually changes
    const [, forceUpdate] = useState(0)
    const [expandedAgentMsgId, setExpandedAgentMsgId] = useState<string | null>(null)
    const [selectedAnalysts, setSelectedAnalysts] = useState<string[]>(() => {
        try {
            const stored = localStorage.getItem('tradingagents-settings')
            if (!stored) return ['market', 'social', 'news', 'fundamentals', 'macro', 'smart_money']
            const parsed = JSON.parse(stored) as { defaultAnalysts?: string[] }
            if (Array.isArray(parsed.defaultAnalysts) && parsed.defaultAnalysts.length > 0) {
                return parsed.defaultAnalysts
            }
        } catch {}
        return ['market', 'social', 'news', 'fundamentals', 'macro', 'smart_money']
    })
    // track which section IDs have been added to chatMessages and whether they're done
    const streamingReportIds = useRef<Map<string, boolean>>(new Map()) // section → isComplete
    const agentMessageMapRef = useRef<Record<string, string>>({})
    const firstTokenMapRef = useRef<Record<string, boolean>>({})
    const sectionToMsgIdRef = useRef<Record<string, string>>({}) // section → agent bubble msgId
    const typingIndicatorIdRef = useRef<string | null>(null)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const messagesContainerRef = useRef<HTMLDivElement>(null)

    const {
        chatMessages,
        setCurrentJobId,
        setCurrentSymbol,
        setIsAnalyzing,
        setIsConnected,
        setCurrentHorizon,
        updateAgentStatus,
        updateAgentSnapshot,
        addAgentReport,
        addReportChunk,
        addChatMessage,
        appendToChatMessage,
        setMessageContent,
        setReport,
        setStructuredData,
        reset,
    } = useAnalysisStore()

    const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

    const recoverInterruptedJob = async () => {
        const { currentJobId } = useAnalysisStore.getState()
        if (!currentJobId) return false

        pushSystem(`分析流中断，正在回查任务状态：${currentJobId}`)

        for (let attempt = 0; attempt < 8; attempt += 1) {
            const status = await api.getJobStatus(currentJobId)

            if (status.status === 'completed') {
                const result = await api.getJobResult(currentJobId)
                setReport(result.result)

                const symbol = result.result.symbol
                const tradeDate = result.result.trade_date
                if (symbol) {
                    setCurrentSymbol(symbol)
                    onSymbolDetected(symbol)
                }

                try {
                    const history = await api.getReports(symbol, 0, 10)
                    const matched = history.reports.find((item: Report) => item.trade_date === tradeDate) ?? history.reports[0]
                    if (matched) {
                        setStructuredData({
                            riskItems: matched.risk_items,
                            keyMetrics: matched.key_metrics,
                            confidence: matched.confidence,
                            targetPrice: matched.target_price,
                            stopLoss: matched.stop_loss_price,
                        })
                    }
                } catch {
                    // 历史报告回填失败时，至少保留主报告正文
                }

                pushAssistant(
                    `**分析完成（已从中断连接恢复）**\n\n方向倾向：**${String(result.result.direction || '未知')}**\n\n执行动作：**${String(result.decision || 'HOLD')}**\n\n> 免责声明：以上内容由模型基于公开数据与规则生成，仅供研究参考，不构成任何投资建议或收益承诺。`
                )
                return true
            }

            if (status.status === 'failed') {
                pushAssistant(`分析失败：${status.error || 'unknown error'}`)
                return true
            }

            await sleep(1500)
        }

        return false
    }

    useEffect(() => {
        const container = messagesContainerRef.current
        if (!container) return
        container.scrollTo({
            top: container.scrollHeight,
            behavior: 'smooth',
        })
    }, [chatMessages])

    const toggleAnalyst = (id: string) => {
        setSelectedAnalysts((prev) =>
            prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
        )
    }

    const pushAssistant = (content: string) => {
        addChatMessage({
            id: `${Date.now()}-${Math.random()}`,
            role: 'assistant',
            content,
            timestamp: new Date().toISOString(),
        })
    }

    const pushSystem = (content: string) => {
        addChatMessage({
            id: `${Date.now()}-${Math.random()}`,
            role: 'system',
            content,
            timestamp: new Date().toISOString(),
        })
    }

    const parseAndDispatch = (event: StreamEvent) => {
        const { event: eventName, data } = event
        switch (eventName) {
            case 'job.ready':
                setIsConnected(true)
                // 把 typing indicator 换成"解析中"提示，告知用户正在识别标的
                if (typingIndicatorIdRef.current) {
                    setMessageContent(typingIndicatorIdRef.current, '__parsing__')
                }
                break
            case 'job.created': {
                const jobId = String(data.job_id || '')
                const symbol = String(data.symbol || '')
                if (jobId) setCurrentJobId(jobId)
                if (symbol) {
                    setCurrentSymbol(symbol)
                    onSymbolDetected(symbol)
                }
                // 切换 indicator 到"采集数据"阶段
                if (typingIndicatorIdRef.current) {
                    setMessageContent(typingIndicatorIdRef.current, `__status:collecting:${symbol}__`)
                }
                streamingReportIds.current.clear()
                agentMessageMapRef.current = {}
                firstTokenMapRef.current = {}
                sectionToMsgIdRef.current = {}
                pendingAgentMsgIdsRef.current = new Set(); completedAgentMsgIdsRef.current = new Set(); forceUpdate(n => n + 1)
                break
            }
            case 'job.running':
                setIsAnalyzing(true)
                // 切换 indicator 到"分析启动"阶段
                if (typingIndicatorIdRef.current) {
                    setMessageContent(typingIndicatorIdRef.current, '__status:analyzing__')
                }
                break
            case 'agent.horizon_start': {
                const h = String(data.horizon || '')
                setCurrentHorizon(h || null)
                break
            }
            case 'agent.horizon_done':
                // keep currentHorizon until job completes so badge stays visible
                break
            case 'job.completed':
                setCurrentHorizon(null)
                setIsAnalyzing(false)
                pendingAgentMsgIdsRef.current = new Set(); completedAgentMsgIdsRef.current = new Set(); forceUpdate(n => n + 1)
                if (typeof data.result === 'object' && data.result && 'symbol' in data.result) {
                    const symbol = String((data.result as Record<string, unknown>).symbol || '')
                    if (symbol) {
                        setCurrentSymbol(symbol)
                        onSymbolDetected(symbol)
                    }
                }
                setReport((data.result || null) as AnalysisReport | null)
                setStructuredData({
                    riskItems: data.risk_items as never,
                    keyMetrics: data.key_metrics as never,
                    confidence: data.confidence as number | null,
                    targetPrice: data.target_price as number | null,
                    stopLoss: data.stop_loss_price as number | null,
                })
                pushAssistant(
                    `**分析完成**\n\n方向倾向：**${String(data.direction || '未知')}**\n\n执行动作：**${String(data.decision || 'HOLD')}**\n\n> 免责声明：以上内容由模型基于公开数据与规则生成，仅供研究参考，不构成任何投资建议或收益承诺。`
                )
                if ('Notification' in window && Notification.permission === 'granted') {
                    new Notification('TradingAgents 分析完成', {
                        body: data.direction ? `方向：${String(data.direction)} · 动作：${String(data.decision || 'HOLD')}` : '点击查看完整报告',
                        icon: '/favicon.ico',
                    })
                }
                break
            case 'job.failed':
                setCurrentHorizon(null)
                setIsAnalyzing(false)
                pushAssistant(`分析失败：${String(data.error || 'unknown error')}`)
                break
            case 'agent.status': {
                const statusData = data as unknown as { agent: string; status: string; horizon?: string }
                const agentKey2 = `${statusData.agent}-${statusData.horizon || 'main'}`

                if (statusData.status === 'in_progress') {
                    // 第一个 agent 开始工作，移除状态指示器
                    if (typingIndicatorIdRef.current) {
                        useAnalysisStore.setState(state => ({
                            chatMessages: state.chatMessages.filter(m => m.id !== typingIndicatorIdRef.current)
                        }))
                        typingIndicatorIdRef.current = null
                    }

                    const agentName = statusData.agent
                    const horizon = statusData.horizon ? `(${statusData.horizon === 'short' ? '短线' : '中线'})` : ''
                    const msgId = `chat-agent-msg-${agentName}-${statusData.horizon || 'main'}-${Date.now()}`

                    agentMessageMapRef.current[agentKey2] = msgId
                    firstTokenMapRef.current[msgId] = true

                    addChatMessage({
                        id: msgId,
                        role: 'assistant',
                        agent: agentName,
                        content: `**${agentName}** ${horizon} 正在思考并撰写报告中...`,
                        timestamp: new Date().toISOString()
                    })
                    pendingAgentMsgIdsRef.current.add(msgId); forceUpdate(n => n + 1)
                } else if (statusData.status === 'completed' || statusData.status === 'skipped') {
                    // Agent 完成/跳过 → 移出 pending，标记为已完成
                    const existingMsgId = agentMessageMapRef.current[agentKey2]
                    if (existingMsgId) {
                        pendingAgentMsgIdsRef.current.delete(existingMsgId)
                        completedAgentMsgIdsRef.current.add(existingMsgId)
                        forceUpdate(n => n + 1)
                    }
                }
                updateAgentStatus(statusData as unknown as AgentStatusEvent)
                break
            }
            case 'agent.token': {
                const tokenData = data as unknown as { agent: string; report: string; token: string; horizon?: string }

                // 意图解析的原始 JSON 不在对话框显示（parsing indicator 已提供 UX）
                if (tokenData.agent === '意图解析') break

                // 第一个 agent token 到达时移除 parsing/typing indicator
                if (typingIndicatorIdRef.current) {
                    useAnalysisStore.setState(state => ({
                        chatMessages: state.chatMessages.filter(m => m.id !== typingIndicatorIdRef.current)
                    }))
                    typingIndicatorIdRef.current = null
                }

                const agentKey = `${tokenData.agent}-${tokenData.horizon || 'main'}`
                let targetMsgId = agentMessageMapRef.current[agentKey]

                // Fallback: create bubble on first token if agent.status was missed or arrived late
                if (!targetMsgId) {
                    const horizonSuffix = tokenData.horizon ? `(${tokenData.horizon === 'short' ? '短线' : '中线'})` : ''
                    targetMsgId = `chat-agent-msg-${tokenData.agent}-${tokenData.horizon || 'main'}-${Date.now()}`
                    agentMessageMapRef.current[agentKey] = targetMsgId
                    firstTokenMapRef.current[targetMsgId] = true
                    addChatMessage({
                        id: targetMsgId,
                        role: 'assistant',
                        agent: tokenData.agent,
                        content: `**${tokenData.agent}** ${horizonSuffix} 正在思考并撰写报告中...`,
                        timestamp: new Date().toISOString(),
                    })
                    pendingAgentMsgIdsRef.current.add(targetMsgId); forceUpdate(n => n + 1)
                }

                // 记录 section → msgId 映射，用于后续转换成 ReportCard
                if (tokenData.report) {
                    sectionToMsgIdRef.current[tokenData.report] = targetMsgId
                }

                if (firstTokenMapRef.current[targetMsgId]) {
                    const horizonText = tokenData.horizon ? `(${tokenData.horizon === 'short' ? '短线' : '中线'})` : ''
                    setMessageContent(targetMsgId, `### ${tokenData.agent} ${horizonText}\n\n${tokenData.token}`)
                    firstTokenMapRef.current[targetMsgId] = false
                    // 第一个 token 到达，移出 pending 状态
                    pendingAgentMsgIdsRef.current.delete(targetMsgId)
                } else {
                    appendToChatMessage(targetMsgId, tokenData.token)
                }
                break
            }
            case 'agent.snapshot':
                updateAgentSnapshot(data as unknown as AgentSnapshotEvent)
                break
            case 'agent.report':
                addAgentReport(data as unknown as AgentReportEvent)
                break
            case 'agent.report.chunk': {
                const chunkData = data as unknown as ReportChunkEvent
                const { section, is_complete } = chunkData
                addReportChunk(chunkData) // 更新报告面板的打字机效果

                if (is_complete && !streamingReportIds.current.get(section)) {
                    streamingReportIds.current.set(section, true)
                    const existingMsgId = sectionToMsgIdRef.current[section]

                    if (existingMsgId) {
                        // 把流式气泡直接转换成已完成的 ReportCard
                        useAnalysisStore.setState(state => ({
                            chatMessages: state.chatMessages.map(m =>
                                m.id === existingMsgId
                                    ? { ...m, role: 'report' as const, section, complete: true }
                                    : m
                            )
                        }))
                    } else {
                        // 兜底：没找到对应气泡，直接创建 ReportCard
                        const buffer = useAnalysisStore.getState().streamingSections[section]?.buffer || ''
                        addChatMessage({
                            id: `stream:${section}`,
                            role: 'report',
                            section,
                            content: buffer,
                            complete: true,
                            timestamp: new Date().toISOString(),
                        })
                    }
                }
                break
            }
            case 'agent.tool_call':
                // 工具调用信息不再在对话框显示，减少噪音
                break
            case 'agent.writing':
                // 气泡已经表示 agent 正在撰写，不再额外发系统消息
                break
            case 'agent.milestone': {
                const { stage, title, summary } = data as { stage: string; title: string; summary: string }
                if (stage === 'final_decision') {
                    pushAssistant(`**${title}**\n\n${summary}`)
                }
                break
            }
            default:
                break
        }
    }

    const streamChat = async (prompt: string) => {
        const response = await api.chatCompletion(
            [{ role: 'user', content: prompt }],
            true,
            selectedAnalysts,
        )

        if (!response.body) throw new Error('SSE stream unavailable')

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = 'message'

        while (true) {
            const { value, done } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })

            const blocks = buffer.split('\n\n')
            buffer = blocks.pop() || ''

            for (const block of blocks) {
                const lines = block.split('\n')
                let dataLine = ''
                for (const raw of lines) {
                    const line = raw.trim()
                    if (!line) continue
                    if (line.startsWith('event:')) currentEvent = line.slice(6).trim()
                    else if (line.startsWith('data:')) dataLine = line.slice(5).trim()
                }

                if (!dataLine) continue
                if (dataLine === '[DONE]' || currentEvent === 'done') {
                    setIsConnected(false)
                    setIsAnalyzing(false)
                    return
                }
                
                if (currentEvent === 'ping') {
                    continue
                }

                try {
                    const data = JSON.parse(dataLine) as Record<string, unknown>
                    parseAndDispatch({ event: currentEvent, data })
                } catch {
                    console.error('SSE解析失败:', dataLine.slice(0, 120))
                }
            }
        }

        setIsConnected(false)
        setIsAnalyzing(false)
    }

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault()
        const prompt = input.trim()
        if (!prompt || streaming) return

        // Inject custom analysis prompt from settings if set
        const customPrompt = localStorage.getItem('ta-custom-prompt')?.trim() || ''
        const fullPrompt = customPrompt ? `${prompt}\n\n[分析要求] ${customPrompt}` : prompt

        setInput('')
        addChatMessage({
            id: `${Date.now()}-${Math.random()}`,
            role: 'user',
            content: prompt,
            timestamp: new Date().toISOString(),
        })

        reset()
        streamingReportIds.current.clear()
        pendingAgentMsgIdsRef.current = new Set(); completedAgentMsgIdsRef.current = new Set(); forceUpdate(n => n + 1)

        // 立刻插入 typing indicator，让用户知道系统正在响应
        const typingId = `typing-${Date.now()}`
        typingIndicatorIdRef.current = typingId
        addChatMessage({
            id: typingId,
            role: 'assistant',
            content: '__typing__',
            timestamp: new Date().toISOString(),
        })

        setStreaming(true)
        setIsAnalyzing(true)
        setIsConnected(false)

        try {
            await streamChat(fullPrompt)
        } catch (error) {
            // 出错时清理 typing indicator
            if (typingIndicatorIdRef.current) {
                useAnalysisStore.setState(state => ({
                    chatMessages: state.chatMessages.filter(m => m.id !== typingIndicatorIdRef.current)
                }))
                typingIndicatorIdRef.current = null
            }
            const errorMessage = error instanceof Error ? error.message : 'unknown error'
            const shouldRecover = /network|fetch|stream|sse|body/i.test(errorMessage)
            if (shouldRecover) {
                const recovered = await recoverInterruptedJob()
                if (!recovered) {
                    pushAssistant(`请求中断：${errorMessage}\n\n后端任务可能仍在执行，请稍后到历史报告中查看结果。`)
                }
            } else {
                pushAssistant(`请求失败：${errorMessage}`)
            }
            setIsAnalyzing(false)
            setIsConnected(false)
        } finally {
            setStreaming(false)
        }
    }

    const hasAnyReport = chatMessages.some(m => m.role === 'report')

    return (
        <aside className="card h-full min-h-0 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Bot className="w-5 h-5 text-cyan-500" />
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">智能分析</h2>
                </div>
                <div className="flex items-center gap-2">
                    {onShowReport && hasAnyReport && (
                        <button
                            onClick={() => onShowReport()}
                            className="text-xs px-2 py-1 rounded bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 hover:bg-blue-200 dark:hover:bg-blue-500/30 transition-colors flex items-center gap-1"
                        >
                            <FileText className="w-3 h-3" />
                            查看报告
                        </button>
                    )}
                    {streaming && (
                        <span className="badge-blue inline-flex items-center gap-1">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            分析中
                        </span>
                    )}
                </div>
            </div>

            <div className="text-xs text-slate-500 dark:text-slate-400 mb-3 flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                示例：分析贵州茅台 600519.SH 今天走势
            </div>

            {/* 快速提示 */}
            <div className="flex flex-wrap gap-2 mb-3">
                {PRESET_PROMPTS.map((prompt) => (
                    <button
                        key={prompt}
                        onClick={() => setInput(prompt)}
                        className="text-xs px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-blue-400 dark:hover:border-blue-500 hover:text-slate-900 dark:hover:text-slate-200"
                    >
                        {prompt}
                    </button>
                ))}
            </div>

            {/* 分析师配置（可折叠） */}
            <div className="mb-3 border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
                <button
                    onClick={() => setShowConfig(!showConfig)}
                    className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                    <div className="flex items-center gap-2">
                        <Settings2 className="w-4 h-4 text-slate-400" />
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                            分析类型 ({selectedAnalysts.length}/6)
                        </span>
                    </div>
                    {showConfig ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                </button>

                {showConfig && (
                    <div className="p-3 bg-white dark:bg-slate-800/30">
                        <div className="flex flex-wrap gap-2">
                            {ANALYST_OPTIONS.map((option) => (
                                <button
                                    key={option.id}
                                    onClick={() => toggleAnalyst(option.id)}
                                    className={`px-3 py-1.5 text-xs rounded-md border transition-all ${selectedAnalysts.includes(option.id)
                                        ? 'bg-blue-50 dark:bg-blue-500/10 border-blue-500 text-blue-600 dark:text-blue-400'
                                        : 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-500'
                                        }`}
                                >
                                    <span className="font-medium">{option.label}</span>
                                    <span className="block opacity-70">{option.description}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* 聊天内容 */}
            <div ref={messagesContainerRef} className="flex-1 min-h-0 overflow-y-auto space-y-2 pr-1">
                {chatMessages.map((msg) => {
                    // Report card
                    if (msg.role === 'report' && msg.section) {
                        return (
                            <ReportCard
                                key={msg.id}
                                section={msg.section}
                                content={msg.content}
                                streaming={!msg.complete}
                                onOpen={() => onShowReport?.(msg.section)}
                            />
                        )
                    }

                    // Status indicator（提交后立即显示，随 SSE 事件切换阶段）
                    if (msg.content.startsWith('__')) {
                        const c = msg.content
                        let label = ''
                        let icon: 'dots' | 'spin' = 'dots'
                        let colorCls = 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500'

                        if (c === '__typing__') {
                            label = ''
                            icon = 'dots'
                        } else if (c === '__parsing__') {
                            label = '正在识别标的与意图...'
                            icon = 'spin'
                            colorCls = 'bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/30 text-blue-500 dark:text-blue-400'
                        } else if (c.startsWith('__status:collecting:')) {
                            const sym = c.replace('__status:collecting:', '').replace('__', '')
                            label = `已识别 ${sym}，正在采集行情数据...`
                            icon = 'spin'
                            colorCls = 'bg-cyan-50 dark:bg-cyan-500/10 border-cyan-200 dark:border-cyan-500/30 text-cyan-500 dark:text-cyan-400'
                        } else if (c === '__status:analyzing__') {
                            label = '数据就绪，多智能体协作分析启动中...'
                            icon = 'spin'
                            colorCls = 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/30 text-emerald-500 dark:text-emerald-400'
                        }

                        return (
                            <div key={msg.id} className="flex items-center gap-2">
                                <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs transition-colors duration-300 ${colorCls}`}>
                                    {icon === 'spin' ? (
                                        <>
                                            <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                                            <span className="animate-pulse">{label}</span>
                                        </>
                                    ) : (
                                        <>
                                            <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: '0ms' }} />
                                            <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: '150ms' }} />
                                            <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: '300ms' }} />
                                        </>
                                    )}
                                </div>
                            </div>
                        )
                    }

                    // Agent streaming messages → compact card with live preview
                    const agentMeta = msg.agent ? AGENT_META_MAP[msg.agent] : null
                    const isPending = pendingAgentMsgIdsRef.current.has(msg.id)
                    const isCompleted = completedAgentMsgIdsRef.current.has(msg.id)
                    const isExpanded = expandedAgentMsgId === msg.id

                    if (msg.agent && agentMeta && msg.role === 'assistant') {
                        // Extract preview text: strip markdown headers, bold, collapse whitespace
                        const textOnly = msg.content
                            .replace(/^#{1,4}\s+.*$/gm, '')
                            .replace(/\*\*/g, '')
                            .replace(/\n{2,}/g, ' ')
                            .trim()

                        return (
                            <div key={msg.id} className={`rounded-xl border transition-all overflow-hidden ${
                                isCompleted
                                    ? 'bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700/30'
                                    : 'bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700/50'
                            }`}>
                                {/* Compact header — click to expand/collapse */}
                                <button
                                    onClick={() => setExpandedAgentMsgId(prev => prev === msg.id ? null : msg.id)}
                                    className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-slate-100 dark:hover:bg-slate-700/30 transition-colors"
                                >
                                    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-lg ${agentMeta.bgCls} shrink-0`}>
                                        <agentMeta.Icon className={`w-4 h-4 ${agentMeta.iconCls}`} />
                                    </span>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs font-medium text-slate-600 dark:text-slate-300">{agentMeta.label}</p>
                                        {isPending ? (
                                            <p className="text-[11px] text-slate-400 dark:text-slate-500 animate-pulse">正在推理分析中...</p>
                                        ) : (
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate" dir="rtl">
                                                <bdi>{textOnly.slice(-120) || '撰写中...'}</bdi>
                                            </p>
                                        )}
                                    </div>
                                    {isPending ? (
                                        <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" />
                                    ) : isCompleted ? (
                                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                                    ) : (
                                        <span className="text-[10px] text-emerald-500 dark:text-emerald-400 font-medium shrink-0 animate-pulse">撰写中</span>
                                    )}
                                </button>

                                {/* Expanded: show full streaming markdown */}
                                {isExpanded && !isPending && (
                                    <div className="px-3 pb-2 border-t border-slate-200 dark:border-slate-700/50 max-h-60 overflow-y-auto">
                                        <div className="prose dark:prose-invert prose-xs max-w-none mt-2 text-[12px] leading-relaxed">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {msg.content}
                                            </ReactMarkdown>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )
                    }

                    // Normal messages (user / assistant without agent / system)
                    return (
                        <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                            <div
                                className={`max-w-[92%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                                    msg.role === 'user'
                                        ? 'bg-blue-100 dark:bg-blue-500/20 border border-blue-300 dark:border-blue-500/30 text-slate-900 dark:text-slate-100'
                                        : msg.role === 'system'
                                            ? 'bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 italic text-xs'
                                            : 'bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300'
                                }`}
                            >
                                {msg.role === 'user' ? (
                                    msg.content
                                ) : (
                                    <div className="prose dark:prose-invert prose-sm max-w-none">
                                        <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            components={{
                                                table: ({ children }) => (
                                                    <table className="w-full border-collapse border border-slate-300 dark:border-slate-600 my-2 text-xs">{children}</table>
                                                ),
                                                thead: ({ children }) => (
                                                    <thead className="bg-slate-100 dark:bg-slate-700">{children}</thead>
                                                ),
                                                th: ({ children }) => (
                                                    <th className="border border-slate-300 dark:border-slate-600 px-2 py-1 text-left font-semibold text-slate-700 dark:text-slate-300">{children}</th>
                                                ),
                                                td: ({ children }) => (
                                                    <td className="border border-slate-300 dark:border-slate-600 px-2 py-1 text-slate-600 dark:text-slate-400">{children}</td>
                                                ),
                                                tr: ({ children }) => (
                                                    <tr className="even:bg-slate-50 dark:even:bg-slate-800/50">{children}</tr>
                                                ),
                                            }}
                                        >
                                            {msg.content}
                                        </ReactMarkdown>
                                    </div>
                                )}
                            </div>
                        </div>
                    )
                })}
                <div ref={messagesEndRef} />
            </div>

            {/* 输入框 */}
            <form onSubmit={handleSubmit} className="mt-3 shrink-0">
                <div className="flex items-center gap-2">
                    <input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                                e.preventDefault()
                                handleSubmit(e as unknown as FormEvent)
                            }
                        }}
                        placeholder="直接描述你的分析需求..."
                        className="input flex-1"
                        title="Enter 发送，Ctrl+Enter 也可发送"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || streaming}
                        className="btn-primary px-3 py-2 inline-flex items-center gap-1"
                    >
                        <Send className="w-4 h-4" />
                        发送
                    </button>
                </div>
            </form>
        </aside>
    )
}
