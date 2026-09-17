import { describe, expect, it } from 'vitest'

import { reconcilePersistedChatMessages } from '@/utils/chatRecovery'

describe('reconcilePersistedChatMessages', () => {
    it('removes an orphaned agent placeholder after page hydration', () => {
        expect(reconcilePersistedChatMessages([
            {
                id: 'aggressive-placeholder',
                role: 'assistant',
                agent: 'Aggressive Analyst',
                content: '**Aggressive Analyst** (短线) 正在思考并撰写报告中...',
                timestamp: '2026-07-13T06:04:00Z',
            },
        ])).toEqual([])
    })

    it('keeps partial agent content but marks it complete so it cannot show as writing', () => {
        expect(reconcilePersistedChatMessages([
            {
                id: 'aggressive-partial',
                role: 'assistant',
                agent: 'Aggressive Analyst',
                content: '### Aggressive Analyst\n\n已经生成的部分分析内容',
                timestamp: '2026-07-13T06:04:00Z',
            },
        ])).toEqual([
            {
                id: 'aggressive-partial',
                role: 'assistant',
                agent: 'Aggressive Analyst',
                content: '### Aggressive Analyst\n\n已经生成的部分分析内容',
                timestamp: '2026-07-13T06:04:00Z',
                complete: true,
            },
        ])
    })

    it('leaves user, report and completed agent messages unchanged', () => {
        const messages = [
            { id: 'user', role: 'user', content: '分析一下', timestamp: 'now' },
            { id: 'report', role: 'report', content: '完整报告', timestamp: 'now', complete: true },
            {
                id: 'agent',
                role: 'assistant',
                agent: 'Trader',
                content: '交易计划',
                timestamp: 'now',
                complete: true,
            },
        ]
        expect(reconcilePersistedChatMessages(messages)).toEqual(messages)
    })
})
