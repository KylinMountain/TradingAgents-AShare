import { describe, expect, it } from 'vitest'

import { advanceProgress, getAnalysisProgress, getReportRunProgress, getTaskStatusLabel } from '@/utils/progressFeedback'

describe('advanceProgress', () => {
    it('moves quickly at the beginning and slows down near the cap', () => {
        expect(advanceProgress(12)).toBeGreaterThan(12)
        expect(advanceProgress(82)).toBeGreaterThanOrEqual(82)
        expect(advanceProgress(82)).toBeLessThanOrEqual(90)
    })

    it('never exceeds the configured cap', () => {
        expect(advanceProgress(91)).toBe(90)
        expect(advanceProgress(88, 88)).toBe(88)
    })
})

describe('getAnalysisProgress', () => {
    it('reflects handshake and agent progress before the final report lands', () => {
        expect(getAnalysisProgress({
            isConnected: true,
            hasHorizon: true,
            completedAgents: 7,
            totalAgents: 14,
            hasFinalDecision: false,
        })).toBe(55)
    })

    it('reserves the last stretch for the final decision and caps incomplete runs below 100', () => {
        expect(getAnalysisProgress({
            isConnected: true,
            hasHorizon: true,
            completedAgents: 14,
            totalAgents: 14,
            hasFinalDecision: false,
        })).toBeLessThan(100)

        expect(getAnalysisProgress({
            isConnected: true,
            hasHorizon: true,
            completedAgents: 14,
            totalAgents: 14,
            hasFinalDecision: true,
        })).toBe(96)
    })
})

describe('getTaskStatusLabel', () => {
    it('returns page-specific copy for loading and completion states', () => {
        expect(getTaskStatusLabel('analysis', 'loading')).toContain('智能体')
        expect(getTaskStatusLabel('reports', 'success')).toBe('历史报告已加载完成')
        expect(getTaskStatusLabel('report-detail', 'error')).toBe('报告打开失败')
    })
})

describe('getReportRunProgress', () => {
    it('shows queued reports at a low early progress', () => {
        const now = Date.parse('2026-04-01T10:10:00+08:00')
        expect(getReportRunProgress({
            status: 'pending',
            createdAt: '2026-04-01T10:09:30+08:00',
            nowMs: now,
        })).toBeGreaterThanOrEqual(8)
    })

    it('pushes running reports forward while keeping headroom before completion', () => {
        const now = Date.parse('2026-04-01T10:15:00+08:00')
        const progress = getReportRunProgress({
            status: 'running',
            createdAt: '2026-04-01T10:10:00+08:00',
            nowMs: now,
        })

        expect(progress).toBeGreaterThan(40)
        expect(progress).toBeLessThan(100)
    })

    it('returns terminal values for completed and failed reports', () => {
        expect(getReportRunProgress({ status: 'completed' })).toBe(100)
        expect(getReportRunProgress({ status: 'failed' })).toBe(100)
    })
})
