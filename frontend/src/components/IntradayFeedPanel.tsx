import { AlertTriangle, Radar, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '@/services/api'
import type { IntradaySignal } from '@/types'

const REFRESH_INTERVAL_SECONDS = 25

type CaseTone = 'emerald' | 'rose' | 'amber'

const CASE_TONE: Record<IntradaySignal['anomaly_case'], CaseTone> = {
    A: 'rose',    // 涨 + 大资金流入：量价确认(红涨)
    B: 'amber',   // 涨 + 资金流出：量价背离，警惕出货
    C: 'rose',    // 不涨但资金流入：暗中吸筹
    D: 'emerald', // 跌 + 大资金流出：真下杀(绿跌)
    E: 'amber',   // 跌但资金流入：逆势吸筹，信号混合
}

const CASE_LABEL: Record<IntradaySignal['anomaly_case'], string> = {
    A: '量价确认',
    B: '量价背离',
    C: '暗中吸筹',
    D: '真下杀',
    E: '逆势吸筹',
}

const TONE_CLASSES: Record<CaseTone, string> = {
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/20',
    rose: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/20',
    amber: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/20',
}

function formatTime(iso: string): string {
    try {
        return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } catch {
        return iso
    }
}

function todayStr(): string {
    const d = new Date()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${d.getFullYear()}-${mm}-${dd}`
}

function SignalCard({ signal }: { signal: IntradaySignal }) {
    const tone = CASE_TONE[signal.anomaly_case] ?? 'amber'
    const isUp = signal.change_pct >= 0
    // 非交易日的 feed 会展示上一交易日的信号,必须标出日期避免误读为今日
    const isToday = signal.trade_date === todayStr()

    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">{signal.board_name}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${TONE_CLASSES[tone]}`}>
                        {CASE_LABEL[signal.anomaly_case] ?? signal.anomaly_case}
                    </span>
                </div>
                <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
                    {!isToday && <span className="mr-1 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] dark:bg-slate-800">{signal.trade_date}</span>}
                    {formatTime(signal.created_at)}
                </span>
            </div>

            <div className="mt-2 flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                <span className={isUp ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'}>
                    {isUp ? '+' : ''}{signal.change_pct.toFixed(2)}%
                </span>
                <span>{signal.net_inflow >= 0 ? '净流入' : '净流出'} {Math.abs(signal.net_inflow).toFixed(2)} 亿</span>
                {signal.fund_source && <span>资金来源:{signal.fund_source}</span>}
                {signal.judgement && <span className="font-medium text-slate-700 dark:text-slate-300">判断:{signal.judgement}</span>}
            </div>

            <p className="mt-2 whitespace-pre-line text-sm text-slate-700 dark:text-slate-300">
                {signal.cause_summary ?? '（归因生成失败,仅展示原始异动数据)'}
            </p>
        </div>
    )
}

export default function IntradayFeedPanel() {
    const [signals, setSignals] = useState<IntradaySignal[]>([])
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let cancelled = false
        // Guards against out-of-order responses: if refresh #1 is slow and
        // resolves after refresh #2 (already applied to state), #1's stale
        // result must not overwrite #2's fresher one.
        let latestRequestId = 0

        async function load(isRefresh: boolean) {
            const requestId = ++latestRequestId
            if (isRefresh) setRefreshing(true)
            else setLoading(true)

            try {
                const response = await api.getIntradayFeed()
                if (cancelled || requestId !== latestRequestId) return
                setSignals(response.items)
                setError(null)
            } catch (err) {
                if (cancelled || requestId !== latestRequestId) return
                setError(err instanceof Error ? err.message : '盘中异动加载失败')
            } finally {
                if (!cancelled && requestId === latestRequestId) {
                    setLoading(false)
                    setRefreshing(false)
                }
            }
        }

        void load(false)
        const intervalId = window.setInterval(() => {
            void load(true)
        }, REFRESH_INTERVAL_SECONDS * 1000)

        return () => {
            cancelled = true
            window.clearInterval(intervalId)
        }
    }, [])

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Radar className="h-5 w-5 text-slate-400" />
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">盘中异动</h2>
                </div>
                {refreshing && <RefreshCw className="h-4 w-4 animate-spin text-slate-400" />}
            </div>

            {error && (
                <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {error}
                </div>
            )}

            {loading ? (
                <div className="flex items-center justify-center py-16 text-slate-400">
                    <RefreshCw className="h-5 w-5 animate-spin" />
                </div>
            ) : signals.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 py-16 text-center text-sm text-slate-400 dark:border-slate-800">
                    今日暂无盘中异动
                </div>
            ) : (
                <div className="space-y-3">
                    {signals.map(signal => (
                        <SignalCard key={signal.id} signal={signal} />
                    ))}
                </div>
            )}
        </div>
    )
}
