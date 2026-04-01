import type { QmtImportState } from '@/types'

export function formatQmtSyncTimestamp(value?: string | null): string {
    if (!value) return '尚未同步'
    return value.replace('T', ' ').slice(0, 19)
}

export function buildQmtSyncSummary(state: QmtImportState | null): {
    title: string
    detail: string
    isConfigured: boolean
} {
    const isConfigured = !!state?.qmt_path && !!state?.account_id
    if (!isConfigured) {
        return {
            title: '尚未配置 QMT 同步',
            detail: '请到设置页填写 QMT userdata 路径和资金账号，然后执行一次持仓同步。',
            isConfigured: false,
        }
    }

    return {
        title: `已同步 ${state?.summary.positions || 0} 只 QMT 持仓`,
        detail: `账户 ${state?.account_id} · 最近同步 ${formatQmtSyncTimestamp(state?.last_synced_at)}`,
        isConfigured: true,
    }
}
