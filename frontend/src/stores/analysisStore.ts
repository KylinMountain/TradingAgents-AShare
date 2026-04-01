import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type {
    Agent,
    JobStatus,
    AnalysisReport,
    LogEntry,
    AgentStatusEvent,
    AgentMessageEvent,
    AgentToolCallEvent,
    AgentReportEvent,
    AgentSnapshotEvent,
    ReportChunkEvent,
    AgentMilestoneEvent,
    AgentTokenEvent,
    StreamingSectionState,
    MilestoneMessage,
    RiskItem,
    KeyMetric,
    DebateMessage,
} from '@/types'

export interface ChatMessage {
    id: string
    role: 'user' | 'assistant' | 'system' | 'report'
    content: string
    timestamp: string
    agent?: string      // The name of the agent who sent the message
    section?: string    // only for role='report'
    complete?: boolean  // only for role='report'
}

const createInitialChatMessages = (): ChatMessage[] => [
    {
        id: 'init',
        role: 'assistant',
        content: '我是你的 A 股多智能体投研助手。直接告诉我你想分析的标的和日期。',
        timestamp: new Date().toISOString(),
    },
]

interface AnalysisState {
    // Current Job
    currentJobId: string | null
    currentSymbol: string
    jobStatus: JobStatus | null

    // Agents
    agents: Agent[]

    // Report
    report: AnalysisReport | null

    // Structured data from job.completed SSE event (LLM-extracted)
    riskItems: RiskItem[]
    keyMetrics: KeyMetric[]
    jobConfidence: number | null
    jobTargetPrice: number | null
    jobStopLoss: number | null

    // Streaming Report State (for typewriter effect)
    streamingSections: Record<string, StreamingSectionState>

    // Milestones for chat display
    milestones: MilestoneMessage[]

    // Debate messages (transient, for battle view)
    debateMessages: Record<string, DebateMessage[]>
    debateScrollTick: number

    // Chat messages (persisted across route changes)
    chatMessages: ChatMessage[]

    // Logs (kept for system messages only)
    logs: LogEntry[]

    // Loading States
    isAnalyzing: boolean
    isConnected: boolean
    analysisRunState: 'idle' | 'running' | 'completed' | 'failed'
    analysisRunError: string | null

    // Current analysis horizon (for badge display)
    currentHorizon: string | null

    // Actions
    setCurrentJobId: (jobId: string | null) => void
    setCurrentSymbol: (symbol: string) => void
    setJobStatus: (status: JobStatus | null) => void
    updateAgentStatus: (event: AgentStatusEvent) => void
    updateAgentSnapshot: (event: AgentSnapshotEvent) => void
    addAgentMessage: (event: AgentMessageEvent) => void
    addAgentToolCall: (event: AgentToolCallEvent) => void
    addAgentReport: (event: AgentReportEvent) => void
    addReportChunk: (event: ReportChunkEvent) => void
    addAgentToken: (event: AgentTokenEvent) => void
    addMilestone: (event: AgentMilestoneEvent) => void
    addLog: (log: LogEntry) => void
    setReport: (report: AnalysisReport | null) => void
    setStructuredData: (data: {
        riskItems?: RiskItem[]
        keyMetrics?: KeyMetric[]
        confidence?: number | null
        targetPrice?: number | null
        stopLoss?: number | null
    }) => void
    setIsAnalyzing: (isAnalyzing: boolean) => void
    setIsConnected: (isConnected: boolean) => void
    setAnalysisRunState: (state: 'idle' | 'running' | 'completed' | 'failed', error?: string | null) => void
    setCurrentHorizon: (horizon: string | null) => void
    addChatMessage: (message: ChatMessage) => void
    appendToChatMessage: (id: string, chunk: string) => void
    setMessageContent: (id: string, content: string) => void
    markAgentMessagesComplete: (msgIds?: string[]) => void
    addDebateMessage: (msg: DebateMessage) => void
    appendDebateToken: (debate: string, agent: string, round: number, token: string, horizon?: string) => void
    clearChatMessages: () => void
    clearSession: () => void
    reset: () => void
}

const initialAgents: Agent[] = [
    // Analyst Team
    { id: 'market', name: 'Market Analyst', team: 'Analyst Team', status: 'pending' },
    { id: 'social', name: 'Social Analyst', team: 'Analyst Team', status: 'pending' },
    { id: 'news', name: 'News Analyst', team: 'Analyst Team', status: 'pending' },
    { id: 'fundamentals', name: 'Fundamentals Analyst', team: 'Analyst Team', status: 'pending' },
    { id: 'macro', name: 'Macro Analyst', team: 'Analyst Team', status: 'pending' },
    { id: 'smart_money', name: 'Smart Money Analyst', team: 'Analyst Team', status: 'pending' },

    // Research Team
    { id: 'bull', name: 'Bull Researcher', team: 'Research Team', status: 'pending' },
    { id: 'bear', name: 'Bear Researcher', team: 'Research Team', status: 'pending' },
    { id: 'research_manager', name: 'Research Manager', team: 'Research Team', status: 'pending' },

    // Trading Team
    { id: 'trader', name: 'Trader', team: 'Trading Team', status: 'pending' },

    // Risk Management
    { id: 'aggressive', name: 'Aggressive Analyst', team: 'Risk Management', status: 'pending' },
    { id: 'conservative', name: 'Conservative Analyst', team: 'Risk Management', status: 'pending' },
    { id: 'neutral', name: 'Neutral Analyst', team: 'Risk Management', status: 'pending' },

    // Portfolio Management
    { id: 'portfolio_manager', name: 'Portfolio Manager', team: 'Portfolio Management', status: 'pending' },
]

// Debounced localStorage storage to avoid blocking the main thread on every token
function createDebouncedStorage(delay = 800) {
    let pending: [string, string] | null = null
    let timer: ReturnType<typeof setTimeout> | null = null
    return {
        getItem: (name: string) => localStorage.getItem(name),
        setItem: (name: string, value: string) => {
            pending = [name, value]
            if (timer) clearTimeout(timer)
            timer = setTimeout(() => {
                if (pending) { localStorage.setItem(pending[0], pending[1]); pending = null }
                timer = null
            }, delay)
        },
        removeItem: (name: string) => {
            pending = null
            if (timer) { clearTimeout(timer); timer = null }
            localStorage.removeItem(name)
        },
    }
}
const debouncedStorage = createDebouncedStorage()

export const useAnalysisStore = create<AnalysisState>()(persist((set) => ({
    currentJobId: null,
    currentSymbol: '000001.SH',
    jobStatus: null,
    agents: initialAgents,
    report: null,
    riskItems: [],
    keyMetrics: [],
    jobConfidence: null,
    jobTargetPrice: null,
    jobStopLoss: null,
    streamingSections: {},
    milestones: [],
    debateMessages: {},
        debateScrollTick: 0,
    chatMessages: createInitialChatMessages(),
    logs: [],
    isAnalyzing: false,
    isConnected: false,
    analysisRunState: 'idle',
    analysisRunError: null,
    currentHorizon: null,

    setCurrentJobId: (jobId) => set({ currentJobId: jobId }),

    setCurrentSymbol: (symbol) => set({ currentSymbol: symbol }),

    setJobStatus: (status) => set({ jobStatus: status }),

    updateAgentStatus: (event) => set((state) => ({
        agents: state.agents.map(agent => {
            if (agent.name !== event.agent) return agent
            const updates: Partial<Agent> = { status: event.status }
            if (event.status === 'in_progress' && !agent.startedAt) updates.startedAt = Date.now()
            if ((event.status === 'completed' || event.status === 'skipped') && !agent.finishedAt) updates.finishedAt = Date.now()
            return { ...agent, ...updates }
        })
    })),

    updateAgentSnapshot: (event) => set((state) => {
        const agentMap = new Map(event.agents.map(a => [a.agent, a.status]))
        return {
            agents: state.agents.map(agent => ({
                ...agent,
                status: agentMap.get(agent.name) || agent.status
            }))
        }
    }),

    // 不再将消息和工具调用添加到日志（已移至后端）
    addAgentMessage: () => {
        // 消息已移至后端日志，前端不再显示
    },

    addAgentToolCall: () => {
        // 工具调用已移至后端日志，前端不再显示
    },

    addAgentReport: (event) => set((state) => ({
        report: {
            ...state.report,
            [event.section]: event.content
        } as AnalysisReport
    })),

    // 处理报告分片（支持打字机效果）
    addReportChunk: (event) => set((state) => {
        const { section, chunk, is_complete } = event
        const current = state.streamingSections[section] || {
            buffer: '',
            displayed: '',
            isTyping: false,
            isComplete: false
        }

        if (is_complete) {
            // 完成时，确保显示完整内容
            return {
                streamingSections: {
                    ...state.streamingSections,
                    [section]: {
                        ...current,
                        buffer: current.buffer,
                        displayed: current.buffer,
                        isTyping: false,
                        isComplete: true
                    }
                }
            }
        }

        // 追加到缓冲区
        const newBuffer = current.buffer + chunk
        return {
            streamingSections: {
                ...state.streamingSections,
                [section]: {
                    ...current,
                    buffer: newBuffer,
                    displayed: newBuffer, // 直接显示完整缓冲区（打字机效果由组件控制）
                    isTyping: true,
                    isComplete: false
                }
            }
        }
    }),

    addAgentToken: (event) => set((state) => {
        const { report: section, token } = event
        if (!section) return state

        const current = state.streamingSections[section] || {
            buffer: '',
            displayed: '',
            isTyping: false,
            isComplete: false
        }

        const newBuffer = current.buffer + token
        return {
            streamingSections: {
                ...state.streamingSections,
                [section]: {
                    ...current,
                    buffer: newBuffer,
                    displayed: newBuffer,
                    isTyping: true,
                    isComplete: false
                }
            }
        }
    }),

    // 添加里程碑消息（用于对话框显示）
    addMilestone: (event) => set((state) => {
        const milestone: MilestoneMessage = {
            id: `${Date.now()}-${Math.random()}`,
            stage: event.stage,
            title: event.title,
            summary: event.summary,
            timestamp: event.timestamp
        }
        return {
            milestones: [...state.milestones, milestone]
        }
    }),

    // 添加聊天记录（持久化）
    addChatMessage: (message) => set((state) => ({
        chatMessages: [...state.chatMessages, message]
    })),

    // 追加内容到已有消息（用于流式报告 chunk 更新）
    appendToChatMessage: (id, chunk) => set((state) => ({
        chatMessages: state.chatMessages.map(m =>
            m.id === id ? { ...m, content: m.content + chunk } : m
        )
    })),

    setMessageContent: (id, content) => set((state) => ({
        chatMessages: state.chatMessages.map(m =>
            m.id === id ? { ...m, content } : m
        )
    })),

    // 批量标记 agent 消息为已完成；不传 msgIds 则标记所有 agent assistant 消息
    markAgentMessagesComplete: (msgIds?: string[]) => set((state) => ({
        chatMessages: state.chatMessages.map(m => {
            if (m.role !== 'assistant' || !m.agent || m.complete) return m
            if (msgIds && !msgIds.includes(m.id)) return m
            return { ...m, complete: true }
        })
    })),

    // upsert: 同 agent+round 则替换（流式结束时用完整内容覆盖）
    addDebateMessage: (msg) => set((state) => {
        const key = msg.debate
        const existing = state.debateMessages[key] || []
        const idx = existing.findIndex(m => m.agent === msg.agent && m.round === msg.round)
        const updated = idx >= 0
            ? existing.map((m, i) => i === idx ? msg : m)
            : [...existing, msg]
        return {
            debateMessages: { ...state.debateMessages, [key]: updated }
        }
    }),

    // 流式 token 追加：找到已有消息则追加 content，否则创建新消息
    appendDebateToken: (debate, agent, round, token, horizon) => set((state) => {
        const key = debate
        const tick = state.debateScrollTick + 1
        const existing = state.debateMessages[key] || []
        const idx = existing.findIndex(m => m.agent === agent && m.round === round)
        if (idx >= 0) {
            const updated = existing.map((m, i) =>
                i === idx ? { ...m, content: m.content + token } : m
            )
            return { debateMessages: { ...state.debateMessages, [key]: updated }, debateScrollTick: tick }
        }
        const isVerdict = round === -1
        return {
            debateMessages: {
                ...state.debateMessages,
                [key]: [...existing, { debate: debate as 'research' | 'risk', agent, round, content: token, isVerdict, horizon }],
            },
            debateScrollTick: tick,
        }
    }),

    // 清空聊天记录
    clearChatMessages: () => set({
        chatMessages: createInitialChatMessages()
    }),

    clearSession: () => set({
        currentJobId: null,
        currentSymbol: '000001.SH',
        jobStatus: null,
        agents: initialAgents.map(a => ({ ...a, status: 'pending' })),
        report: null,
        riskItems: [],
        keyMetrics: [],
        jobConfidence: null,
        jobTargetPrice: null,
        jobStopLoss: null,
        streamingSections: {},
        debateMessages: {},
        debateScrollTick: 0,
        milestones: [],
        chatMessages: createInitialChatMessages(),
        logs: [],
        isAnalyzing: false,
        isConnected: false,
        analysisRunState: 'idle',
        analysisRunError: null,
        currentHorizon: null,
    }),

    addLog: (log) => set((state) => ({
        logs: [log, ...state.logs].slice(0, 100)
    })),

    setReport: (report) => set((state) => ({
        report,
        currentSymbol: report?.symbol || state.currentSymbol,
    })),

    setStructuredData: (data) => set({
        riskItems: data.riskItems ?? [],
        keyMetrics: data.keyMetrics ?? [],
        jobConfidence: data.confidence ?? null,
        jobTargetPrice: data.targetPrice ?? null,
        jobStopLoss: data.stopLoss ?? null,
    }),

    setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),

    setIsConnected: (isConnected) => set({ isConnected }),

    setAnalysisRunState: (analysisRunState, error = null) => set({
        analysisRunState,
        analysisRunError: analysisRunState === 'failed' ? error : null,
    }),

    setCurrentHorizon: (horizon) => set({ currentHorizon: horizon }),

    reset: () => set((state) => ({
        currentJobId: null,
        currentSymbol: state.currentSymbol,
        jobStatus: null,
        agents: initialAgents.map(a => ({ ...a, status: 'pending' })),
        report: null,
        riskItems: [],
        keyMetrics: [],
        jobConfidence: null,
        jobTargetPrice: null,
        jobStopLoss: null,
        streamingSections: {},
        debateMessages: {},
        debateScrollTick: 0,
        milestones: [],
        // 注意：reset时不清空chatMessages，保持对话历史
        logs: [],
        isAnalyzing: false,
        isConnected: false,
        analysisRunState: 'idle',
        analysisRunError: null,
        currentHorizon: null,
    }))
}), {
    name: 'tradingagents-analysis',
    version: 1,
    storage: createJSONStorage(() => debouncedStorage),
    partialize: (state) => ({
        currentSymbol: state.currentSymbol,
        report: state.report,
        riskItems: state.riskItems,
        keyMetrics: state.keyMetrics,
        jobConfidence: state.jobConfidence,
        jobTargetPrice: state.jobTargetPrice,
        jobStopLoss: state.jobStopLoss,
        // Filter out transient status indicator messages (e.g. __typing__, __parsing__)
        // so they don't persist across page refreshes
        chatMessages: state.chatMessages.filter(m => !m.content.startsWith('__')),
    }),
    merge: (persistedState, currentState) => {
        const persisted = (persistedState ?? {}) as Partial<AnalysisState>
        return {
            ...currentState,
            ...persisted,
            currentJobId: null,
            jobStatus: null,
            agents: initialAgents.map(a => ({ ...a, status: 'pending' })),
            streamingSections: {},
            debateMessages: {},
        debateScrollTick: 0,
            milestones: [],
            logs: [],
            isAnalyzing: false,
            isConnected: false,
            analysisRunState: 'idle',
            analysisRunError: null,
            chatMessages: persisted.chatMessages?.length ? persisted.chatMessages : currentState.chatMessages,
        }
    },
}))
