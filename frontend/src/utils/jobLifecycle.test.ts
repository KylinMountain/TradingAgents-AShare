import { describe, expect, it } from 'vitest'

import {
    classifyRecoveredJobStatus,
    getJobLifecycleUpdate,
    hasRecoveryPollingReachedLimit,
    RECOVERY_POLL_MAX_ATTEMPTS,
} from '@/utils/jobLifecycle'

describe('getJobLifecycleUpdate', () => {
    it('treats overtime as a non-terminal running state', () => {
        expect(getJobLifecycleUpdate('job.overtime')).toEqual({
            isAnalyzing: true,
            runState: 'running',
            overtimeNotice: '分析耗时较长，后台仍在继续，正在等待最终结果，请勿重复提交。',
        })
    })

    it('uses the backend overtime copy when provided', () => {
        expect(getJobLifecycleUpdate('job.overtime', { msg: '仍在生成最终报告' })?.overtimeNotice)
            .toBe('仍在生成最终报告')
    })

    it('clears an overtime notice only when a terminal event arrives', () => {
        expect(getJobLifecycleUpdate('job.completed')).toMatchObject({
            isAnalyzing: false,
            runState: 'completed',
            overtimeNotice: null,
        })
        expect(getJobLifecycleUpdate('job.failed')).toMatchObject({
            isAnalyzing: false,
            runState: 'failed',
            overtimeNotice: null,
        })
    })

    it('keeps compatibility with unrelated events from older backends', () => {
        expect(getJobLifecycleUpdate('agent.status', { status: 'in_progress' })).toBeNull()
    })
})

describe('hasRecoveryPollingReachedLimit', () => {
    it('stops recovery polling after two hours of three-second retries', () => {
        expect(hasRecoveryPollingReachedLimit(RECOVERY_POLL_MAX_ATTEMPTS - 1)).toBe(false)
        expect(hasRecoveryPollingReachedLimit(RECOVERY_POLL_MAX_ATTEMPTS)).toBe(true)
    })
})

describe('classifyRecoveredJobStatus', () => {
    it('keeps polling an old server after its false 1800-second failure', () => {
        expect(classifyRecoveredJobStatus('failed', '任务超时（超过 1800 秒），已自动终止')).toBe('running')
        expect(classifyRecoveredJobStatus('failed', 'job timeout exceeded 1800 seconds')).toBe('running')
        expect(getJobLifecycleUpdate('job.failed', {
            error: '任务超时（超过 1800 秒），已自动终止',
        })).toMatchObject({
            isAnalyzing: true,
            runState: 'running',
        })
    })

    it('still treats real backend failures as terminal', () => {
        expect(classifyRecoveredJobStatus('failed', 'GLM API authentication failed')).toBe('failed')
        expect(classifyRecoveredJobStatus('completed')).toBe('completed')
        expect(classifyRecoveredJobStatus('running')).toBe('running')
    })
})
