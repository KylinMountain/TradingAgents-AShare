import type { PortfolioImportState } from '@/types'

export function formatSyncTimestamp(value?: string | null): string {
    if (!value) return '尚未同步'
    return value.replace('T', ' ').slice(0, 19)
}

export function buildPortfolioSyncSummary(state: PortfolioImportState | null): {
    title: string
    detail: string
    hasPositions: boolean
} {
    const hasPositions = (state?.summary?.positions ?? 0) > 0
    if (!hasPositions) {
        return {
            title: '尚未导入持仓',
            detail: '请到设置页导入持仓信息，支持手动输入。',
            hasPositions: false,
        }
    }

    return {
        title: `已导入 ${state?.summary.positions || 0} 只持仓`,
        detail: `最近同步 ${formatSyncTimestamp(state?.last_synced_at)}`,
        hasPositions: true,
    }
}
