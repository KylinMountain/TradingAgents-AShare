export type AnalysisRunState = 'idle' | 'running' | 'completed' | 'failed'

export interface JobLifecycleUpdate {
    isAnalyzing: boolean
    runState: AnalysisRunState
    overtimeNotice: string | null
}

export type RecoveredJobDisposition = 'running' | 'completed' | 'failed'

export const DEFAULT_OVERTIME_NOTICE = '分析耗时较长，后台仍在继续，正在等待最终结果，请勿重复提交。'
export const RECOVERY_POLL_MAX_ATTEMPTS = 2 * 60 * 60 / 3
export const RECOVERY_POLL_TIMEOUT_MESSAGE = '已停止等待任务状态。后端任务可能仍在处理，请稍后到历史报告查看最终结果。'

export function hasRecoveryPollingReachedLimit(
    attempts: number,
    maxAttempts: number = RECOVERY_POLL_MAX_ATTEMPTS,
): boolean {
    return attempts >= maxAttempts
}

export function getJobLifecycleUpdate(
    eventName: string,
    data: Record<string, unknown> = {},
): JobLifecycleUpdate | null {
    switch (eventName) {
        case 'job.running':
            return { isAnalyzing: true, runState: 'running', overtimeNotice: null }
        case 'job.overtime': {
            const suppliedMessage = data.message ?? data.msg
            return {
                isAnalyzing: true,
                runState: 'running',
                overtimeNotice: typeof suppliedMessage === 'string' && suppliedMessage.trim()
                    ? suppliedMessage
                    : DEFAULT_OVERTIME_NOTICE,
            }
        }
        case 'job.completed':
            return { isAnalyzing: false, runState: 'completed', overtimeNotice: null }
        case 'job.failed':
            if (classifyRecoveredJobStatus('failed', typeof data.error === 'string' ? data.error : null) === 'running') {
                return {
                    isAnalyzing: true,
                    runState: 'running',
                    overtimeNotice: DEFAULT_OVERTIME_NOTICE,
                }
            }
            return { isAnalyzing: false, runState: 'failed', overtimeNotice: null }
        default:
            return null
    }
}

export function classifyRecoveredJobStatus(status: string, error?: string | null): RecoveredJobDisposition {
    if (status === 'completed') return 'completed'
    if (status !== 'failed') return 'running'

    // Older servers marked the outer 1800-second watchdog as failed even though
    // the inner analysis continued and could still persist a completed report.
    const legacySoftTimeout = /(?:任务超时[^\n]*(?:1800|秒)|(?:timeout|timed out)[^\n]*1800)/i.test(error || '')
    return legacySoftTimeout ? 'running' : 'failed'
}
