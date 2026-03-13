import { FormEvent, useState, useRef, useEffect } from 'react'
import { Bot, Loader2, Send, Sparkles, Settings2, ChevronDown, ChevronUp, FileText, ChevronRight } from 'lucide-react'
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
    AgentWritingEvent,
    AgentToolCallDisplayEvent,
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
    investment_plan: '研究团队投资计划',
    trader_investment_plan: '交易员计划',
    final_trade_decision: '最终交易决策',
}

const SECTION_ICONS: Record<string, string> = {
    market_report: '📈',
    sentiment_report: '💬',
    news_report: '📰',
    fundamentals_report: '📊',
    investment_plan: '🧠',
    trader_investment_plan: '💼',
    final_trade_decision: '⚖️',
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
    const icon = SECTION_ICONS[section] || '📄'
    const preview = content.replace(/^#+\s*/gm, '').replace(/\*\*/g, '').slice(0, 80)

    if (streaming) {
        return (
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-blue-500/10 border border-blue-500/20 text-sm">
                <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" />
                <span className="text-blue-300 font-medium">{icon} {title}</span>
                <span className="text-slate-500 text-xs ml-auto">撰写中...</span>
            </div>
        )
    }

    return (
        <button
            onClick={onOpen}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/50 hover:border-blue-400 dark:hover:border-blue-500/40 hover:bg-blue-50 dark:hover:bg-slate-800 transition-all text-left group"
        >
            <span className="text-base shrink-0">{icon}</span>
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
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const messagesContainerRef = useRef<HTMLDivElement>(null)

    const {
        chatMessages,
        setCurrentJobId,
        setCurrentSymbol,
        setIsAnalyzing,
        setIsConnected,
        updateAgentStatus,
        updateAgentSnapshot,
        addAgentReport,
        addReportChunk,
        addChatMessage,
        appendToChatMessage,
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
                break
            case 'job.created': {
                const jobId = String(data.job_id || '')
                const symbol = String(data.symbol || '')
                const tradeDate = String(data.trade_date || '')
                if (jobId) setCurrentJobId(jobId)
                if (symbol) {
                    setCurrentSymbol(symbol)
                    onSymbolDetected(symbol)
                }
                pushSystem(`已启动分析：${symbol} @ ${tradeDate}`)
                streamingReportIds.current.clear()
                break
            }
            case 'job.running':
                setIsAnalyzing(true)
                break
            case 'job.completed':
                setIsAnalyzing(false)
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
                setIsAnalyzing(false)
                pushAssistant(`分析失败：${String(data.error || 'unknown error')}`)
                break
            case 'agent.status':
                updateAgentStatus(data as unknown as AgentStatusEvent)
                break
            case 'agent.snapshot':
                updateAgentSnapshot(data as unknown as AgentSnapshotEvent)
                break
            case 'agent.report':
                addAgentReport(data as unknown as AgentReportEvent)
                break
            case 'agent.report.chunk': {
                const chunkData = data as unknown as ReportChunkEvent
                const { section, chunk, is_complete } = chunkData
                const msgId = `stream:${section}`
                addReportChunk(chunkData)

                if (!streamingReportIds.current.has(section)) {
                    // First chunk → create new report message in the flow
                    streamingReportIds.current.set(section, false)
                    addChatMessage({
                        id: msgId,
                        role: 'report',
                        section,
                        content: chunk,
                        complete: false,
                        timestamp: new Date().toISOString(),
                    })
                } else if (!is_complete) {
                    // Subsequent chunks → append
                    appendToChatMessage(msgId, chunk)
                }

                if (is_complete) {
                    streamingReportIds.current.set(section, true)
                    // Mark the message as complete in the store
                    // We update by replacing the message content isn't needed —
                    // we track completion via a local completed set
                    useAnalysisStore.setState(state => ({
                        chatMessages: state.chatMessages.map(m =>
                            m.id === msgId ? { ...m, complete: true } : m
                        )
                    }))
                }
                break
            }
            case 'agent.tool_call': {
                const toolData = data as unknown as AgentToolCallDisplayEvent
                const description = toolData.description || toolData.tool
                pushSystem(`${toolData.agent}：${description}`)
                break
            }
            case 'agent.writing': {
                const writingData = data as unknown as AgentWritingEvent
                pushSystem(`${writingData.agent}：正在撰写 ${writingData.report_name}...`)
                break
            }
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
        setStreaming(true)
        setIsAnalyzing(true)
        setIsConnected(false)

        try {
            await streamChat(fullPrompt)
        } catch (error) {
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

                    // Normal messages
                    return (
                        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
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
