import { useState, useRef, useEffect } from 'react'
import { Bot, Loader2, Play, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '@/services/api'
import { useAnalysisStore } from '@/stores/analysisStore'
import type { AnalysisReport, AgentReportEvent, AgentSnapshotEvent, AgentStatusEvent, ReportChunkEvent } from '@/types'
import AgentCollaboration from './AgentCollaboration'

interface AnalysisConsoleProps {
    symbol: string
    onShowReport?: (section?: string) => void
    onOpenDebate?: (debate: 'research' | 'risk') => void
    selectedSection?: string
}

interface StreamEvent {
    event: string
    data: Record<string, unknown>
}

export default function AnalysisConsole({ symbol, onShowReport, onOpenDebate, selectedSection }: AnalysisConsoleProps) {
    const [prompt, setPrompt] = useState('')
    const [streaming, setStreaming] = useState(false)
    const lastAnalyzedSymbol = useRef('')
    const [analyzedDisplayName, setAnalyzedDisplayName] = useState('')

    const {
        isAnalyzing,
        analysisRunState,
        currentSymbol,
        setCurrentJobId,
        setCurrentSymbol,
        setIsAnalyzing,
        setIsConnected,
        setAnalysisRunState,
        setCurrentHorizon,
        updateAgentStatus,
        updateAgentSnapshot,
        addAgentReport,
        addReportChunk,
        setReportAndStructuredData,
        markAgentMessagesComplete,
        reset,
        agents,
    } = useAnalysisStore()

    const [workflowExpanded, setWorkflowExpanded] = useState(true)
    const isActive = isAnalyzing || analysisRunState === 'running' || analysisRunState === 'completed'

    // 分析完成或缓存恢复后，若缺中文名则补查（仅触发一次）
    useEffect(() => {
        if (analysisRunState !== 'completed' || analyzedDisplayName || !currentSymbol) return
        let cancelled = false
        const lookup = async () => {
            const code = currentSymbol.split('.')[0]
            if (!code) return
            try {
                const res = await api.searchStocks(code)
                if (cancelled) return
                const match = res.results.find(r => r.symbol === currentSymbol)
                if (match) setAnalyzedDisplayName(match.name)
            } catch {}
        }
        lookup()
        return () => { cancelled = true }
    }, [analysisRunState, currentSymbol, analyzedDisplayName])

    const parseAndDispatch = (event: StreamEvent) => {
        const { event: eventName, data } = event
        switch (eventName) {
            case 'job.ready':
                setIsConnected(true)
                break
            case 'job.created': {
                const jobId = String(data.job_id || '')
                const sym = String(data.symbol || '')
                if (jobId) setCurrentJobId(jobId)
                if (sym) { setCurrentSymbol(sym); lookupName(sym) }
                break
            }
            case 'job.running':
                setIsAnalyzing(true)
                setAnalysisRunState('running')
                break
            case 'agent.horizon_start': {
                const h = String(data.horizon || '')
                setCurrentHorizon(h || null)
                break
            }
            case 'agent.horizon_done':
                break
            case 'job.completed': {
                setCurrentHorizon(null)
                setIsAnalyzing(false)
                setAnalysisRunState('completed')
                markAgentMessagesComplete()
                setReportAndStructuredData(
                    (data.result || null) as AnalysisReport | null,
                    {
                        riskItems: data.risk_items as never,
                        keyMetrics: data.key_metrics as never,
                        confidence: data.confidence as number | null,
                        targetPrice: data.target_price as number | null,
                        stopLoss: data.stop_loss_price as number | null,
                    },
                )
                break
            }
            case 'job.failed':
                setCurrentHorizon(null)
                setIsAnalyzing(false)
                setAnalysisRunState('failed', String(data.error || 'unknown error'))
                break
            case 'agent.status':
                updateAgentStatus(data as unknown as AgentStatusEvent)
                break
            case 'agent.token':
                // Agent token 事件由 store 的 addReportChunk / agent.report.chunk 处理
                break
            case 'agent.snapshot':
                updateAgentSnapshot(data as unknown as AgentSnapshotEvent)
                break
            case 'agent.report':
                addAgentReport(data as unknown as AgentReportEvent)
                break
            case 'agent.report.chunk':
                addReportChunk(data as unknown as ReportChunkEvent)
                break
            case 'agent.tool_call':
            case 'agent.writing':
            case 'agent.debate.token':
                break
            default:
                break
        }
    }

    const streamChat = async (fullPrompt: string) => {
        const selectedAnalysts = (() => {
            try {
                const stored = localStorage.getItem('tradingagents-settings')
                if (!stored) return ['market', 'social', 'news', 'fundamentals', 'macro', 'smart_money', 'volume_price']
                const parsed = JSON.parse(stored) as { defaultAnalysts?: string[] }
                if (Array.isArray(parsed.defaultAnalysts) && parsed.defaultAnalysts.length > 0) {
                    return parsed.defaultAnalysts
                }
            } catch {}
            return ['market', 'social', 'news', 'fundamentals', 'macro', 'smart_money', 'volume_price']
        })()

        const response = await api.chatCompletion(
            [{ role: 'user', content: fullPrompt }],
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

                if (currentEvent === 'ping') continue

                try {
                    const data = JSON.parse(dataLine) as Record<string, unknown>
                    parseAndDispatch({ event: currentEvent, data })
                } catch {
                    // 静默跳过解析失败的行
                }
            }
        }

        setIsConnected(false)
        setIsAnalyzing(false)
    }

    const lookupName = async (sym: string) => {
        const code = sym.split('.')[0]
        if (!code) return
        try {
            const res = await api.searchStocks(code)
            const match = res.results.find(r => r.symbol === sym)
            if (match) setAnalyzedDisplayName(match.name)
        } catch {}
    }

    const handleStartAnalysis = async () => {
        const finalPrompt = prompt.trim() || `分析 ${symbol} 今日走势`
        const customPrompt = localStorage.getItem('ta-custom-prompt')?.trim() || ''
        const fullPrompt = customPrompt ? `${finalPrompt}\n\n[分析要求] ${customPrompt}` : finalPrompt

        lastAnalyzedSymbol.current = symbol
        setStreaming(true)
        reset()
        setIsAnalyzing(true)
        setIsConnected(false)
        setAnalysisRunState('running')
        lookupName(symbol)

        try {
            await streamChat(fullPrompt)
        } catch {
            setAnalysisRunState('failed', '分析请求失败，请重试')
        } finally {
            setStreaming(false)
        }
    }

    const defaultPrompt = `分析 ${symbol} 今日走势`

    const doneCount = agents.filter(a => a.status === 'completed').length
    const totalCount = agents.filter(a => a.status !== 'skipped').length || agents.length || 15
    const progressPct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0
    const activeAgent = agents.find(a => a.status === 'in_progress')

    const META_LABEL: Record<string, string> = {
        'Market Analyst': '技术面', 'Social Analyst': '舆情', 'News Analyst': '新闻',
        'Fundamentals Analyst': '基本面', 'Macro Analyst': '宏观', 'Smart Money Analyst': '主力资金',
        'Volume Price Analyst': '量价', 'Bull Researcher': '多头', 'Bear Researcher': '空头',
        'Research Manager': '研究总监', 'Trader': '交易员', 'Aggressive Analyst': '激进',
        'Neutral Analyst': '中性', 'Conservative Analyst': '稳健', 'Portfolio Manager': '组合经理',
    }

    const activeLabel = activeAgent ? (META_LABEL[activeAgent.name] || activeAgent.name) : null
    const isCached = analysisRunState === 'completed' && agents.length > 0 && agents.every(a => !a.startedAt)

    return (
        <section className="card space-y-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Bot className="w-5 h-5 text-purple-500" />
                    <h2 className="font-semibold text-slate-900 dark:text-slate-100">智能分析</h2>
                </div>
                <div className="flex items-center gap-2">
                    {analysisRunState === 'running' && (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-100 px-3 py-1 text-xs font-medium text-purple-600 dark:bg-purple-500/15 dark:text-purple-300">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            分析中
                        </span>
                    )}
                    {analysisRunState === 'completed' && (
                        <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300">
                            已完成
                        </span>
                    )}
                    {analysisRunState === 'failed' && (
                        <span className="rounded-full bg-rose-100 px-3 py-1 text-xs font-medium text-rose-600 dark:bg-rose-500/15 dark:text-rose-300">
                            失败
                        </span>
                    )}
                </div>
            </div>

            {/* 输入框始终可见 */}
            <div className="flex flex-col sm:flex-row gap-3">
                <input
                    type="text"
                    value={prompt}
                    onChange={e => setPrompt(e.target.value)}
                    placeholder={defaultPrompt}
                    onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleStartAnalysis() } }}
                    className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:placeholder:text-slate-500"
                />
                <button
                    type="button"
                    onClick={handleStartAnalysis}
                    disabled={streaming || analysisRunState === 'running'}
                    className="inline-flex items-center gap-2 rounded-xl bg-purple-500 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-purple-600 disabled:cursor-not-allowed disabled:opacity-40 shrink-0"
                >
                    <Play className="w-4 h-4" />
                    {isActive && symbol === lastAnalyzedSymbol.current ? '重新分析' : '开始分析'}
                </button>
            </div>

            {!isActive && (
                <p className="text-xs text-slate-400 dark:text-slate-500">
                    输入分析指令后点击按钮，系统将启动多Agent协作分析。直接回车也可触发。
                </p>
            )}

            {/* 分析中或已完成：进度条 + 可折叠流程图 */}
            {isActive && (
            <>
            <button
                type="button"
                onClick={() => setWorkflowExpanded(v => !v)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-left"
            >
                <div className="relative w-8 h-8 shrink-0">
                    <svg className="w-8 h-8 -rotate-90" viewBox="0 0 36 36">
                        <circle cx="18" cy="18" r="14" fill="none" stroke="currentColor"
                            className="text-slate-200 dark:text-slate-700" strokeWidth="3" />
                        <circle cx="18" cy="18" r="14" fill="none" stroke="currentColor"
                            className={analysisRunState === 'completed' ? 'text-emerald-500' : 'text-blue-500'}
                            strokeWidth="3" strokeLinecap="round"
                            strokeDasharray={`${progressPct * 0.88} 88`} />
                    </svg>
                    {analysisRunState === 'running' ? (
                        <Loader2 className="absolute inset-0 m-auto w-3 h-3 animate-spin text-blue-500" />
                    ) : (
                        <span className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-slate-500 dark:text-slate-400">
                            {progressPct}
                        </span>
                    )}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        {(analyzedDisplayName) && (
                            <span className="text-sm font-bold text-slate-800 dark:text-slate-100 truncate max-w-[180px]">
                                {analyzedDisplayName}
                            </span>
                        )}
                        <span className="text-xs text-slate-400 font-mono">{currentSymbol}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-600 dark:text-slate-300">
                            {doneCount}/{totalCount}
                        </span>
                        <span className="text-xs text-slate-400">
                            agents 已完成
                        </span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                        <div className="flex-1 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden max-w-[120px]">
                            <div
                                className={`h-full rounded-full transition-all duration-500 ${analysisRunState === 'completed' ? 'bg-emerald-500' : 'bg-blue-500'}`}
                                style={{ width: `${progressPct}%` }}
                            />
                        </div>
                        {activeLabel && analysisRunState === 'running' && (
                            <span className="text-xs text-blue-500 dark:text-blue-400 font-medium truncate">
                                {activeLabel} 分析中...
                            </span>
                        )}
                        {!activeLabel && doneCount >= totalCount && analysisRunState === 'running' && (
                            <span className="text-xs text-amber-500 font-medium">正在生成最终报告...</span>
                        )}
                        {analysisRunState === 'completed' && (
                            <span className="text-xs text-emerald-500 font-medium">
                                全部完成{isCached ? ' · 缓存' : ''}
                            </span>
                        )}
                    </div>
                </div>

                <span className="text-xs text-slate-400 flex items-center gap-1 shrink-0">
                    {workflowExpanded ? (
                        <>收起 <ChevronUp className="w-3 h-3" /></>
                    ) : (
                        <>展开 <ChevronDown className="w-3 h-3" /></>
                    )}
                </span>
            </button>

            {workflowExpanded && (
                <AgentCollaboration onSelectSection={onShowReport || (() => {})} onOpenDebate={onOpenDebate || (() => {})} selectedSection={selectedSection} />
            )}
            </>
            )}
        </section>
    )

}
