export type TaskFeedbackKind = 'analysis' | 'reports' | 'report-detail'
export type TaskFeedbackStatus = 'idle' | 'loading' | 'success' | 'error'

function clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value))
}

export function advanceProgress(current: number, cap = 90): number {
    const safeCap = clamp(cap, 0, 100)
    if (current >= safeCap) return safeCap

    const remaining = safeCap - current
    const step = Math.max(1, Math.round(remaining * 0.22))
    return clamp(current + step, 0, safeCap)
}

export function getAnalysisProgress(params: {
    isConnected: boolean
    hasHorizon: boolean
    completedAgents: number
    totalAgents: number
    hasFinalDecision: boolean
}): number {
    const totalAgents = Math.max(1, params.totalAgents)
    const completedAgents = clamp(params.completedAgents, 0, totalAgents)

    let progress = params.isConnected ? 16 : 8
    if (params.hasHorizon) progress += 12

    progress += Math.round((completedAgents / totalAgents) * 54)

    if (params.hasFinalDecision) {
        progress += 14
    }

    const cap = params.hasFinalDecision ? 96 : 92
    return clamp(progress, 6, cap)
}

export function getTaskStatusLabel(kind: TaskFeedbackKind, status: Exclude<TaskFeedbackStatus, 'idle'>): string {
    const copy: Record<TaskFeedbackKind, Record<Exclude<TaskFeedbackStatus, 'idle'>, string>> = {
        analysis: {
            loading: '多智能体正在协同分析中...',
            success: '智能分析已完成',
            error: '智能分析失败',
        },
        reports: {
            loading: '历史报告加载中...',
            success: '历史报告已加载完成',
            error: '历史报告加载失败',
        },
        'report-detail': {
            loading: '报告详情加载中...',
            success: '报告已打开',
            error: '报告打开失败',
        },
    }

    return copy[kind][status]
}

function parseTimeOrNow(value?: string | null, fallback = Date.now()): number {
    if (!value) return fallback
    const parsed = Date.parse(value)
    return Number.isNaN(parsed) ? fallback : parsed
}

export function getReportRunProgress(params: {
    status: 'pending' | 'running' | 'completed' | 'failed'
    createdAt?: string | null
    nowMs?: number
}): number {
    const nowMs = params.nowMs ?? Date.now()

    if (params.status === 'completed' || params.status === 'failed') return 100

    const createdAtMs = parseTimeOrNow(params.createdAt, nowMs)
    const elapsedMs = Math.max(0, nowMs - createdAtMs)

    if (params.status === 'pending') {
        const progress = 8 + Math.round((Math.min(elapsedMs, 45_000) / 45_000) * 16)
        return clamp(progress, 8, 24)
    }

    const runningProgress = 22 + Math.round((Math.min(elapsedMs, 6 * 60_000) / (6 * 60_000)) * 68)
    return clamp(runningProgress, 22, 90)
}
