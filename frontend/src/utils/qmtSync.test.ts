import { describe, expect, it } from 'vitest'

import type { QmtImportState } from '@/types'
import { buildQmtSyncSummary, formatQmtSyncTimestamp } from '@/utils/qmtSync'

describe('formatQmtSyncTimestamp', () => {
    it('formats ISO timestamp to compact local-like text', () => {
        expect(formatQmtSyncTimestamp('2026-03-31T09:08:07+08:00')).toBe('2026-03-31 09:08:07')
    })

    it('returns fallback for empty values', () => {
        expect(formatQmtSyncTimestamp(undefined)).toBe('尚未同步')
    })
})

describe('buildQmtSyncSummary', () => {
    it('guides user to settings when QMT is not configured', () => {
        expect(buildQmtSyncSummary(null)).toEqual({
            title: '尚未配置 QMT 同步',
            detail: '请到设置页填写 QMT userdata 路径和资金账号，然后执行一次持仓同步。',
            isConfigured: false,
        })
    })

    it('describes synced holdings when configuration exists', () => {
        const state: QmtImportState = {
            broker: 'qmt_xtquant',
            qmt_path: 'D:/QMT/userdata_mini',
            account_id: 'demo-account',
            account_type: 'STOCK',
            auto_apply_scheduled: true,
            last_synced_at: '2026-03-31T09:08:07+08:00',
            last_error: null,
            summary: { positions: 3 },
            scheduled_sync: { created: ['600519.SH'], existing: ['300750.SZ'], skipped_limit: [] },
            positions: [],
        }

        expect(buildQmtSyncSummary(state)).toEqual({
            title: '已同步 3 只 QMT 持仓',
            detail: '账户 demo-account · 最近同步 2026-03-31 09:08:07',
            isConfigured: true,
        })
    })
})
