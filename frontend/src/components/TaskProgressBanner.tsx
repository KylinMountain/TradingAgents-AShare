import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { TaskFeedbackStatus } from '@/utils/progressFeedback'

interface TaskProgressBannerProps {
    status: TaskFeedbackStatus
    progress?: number
    label: string
    detail?: string | null
    className?: string
}

const STATUS_HOLD_MS = 2400

export default function TaskProgressBanner({
    status,
    progress = 0,
    label,
    detail,
    className = '',
}: TaskProgressBannerProps) {
    const [visible, setVisible] = useState(status !== 'idle')

    useEffect(() => {
        if (status === 'idle') {
            setVisible(false)
            return
        }

        setVisible(true)

        if (status === 'success' || status === 'error') {
            const timer = window.setTimeout(() => setVisible(false), STATUS_HOLD_MS)
            return () => window.clearTimeout(timer)
        }

        return undefined
    }, [status, label, detail, progress])

    if (!visible || status === 'idle') return null

    if (status === 'success' || status === 'error') {
        const success = status === 'success'
        const Icon = success ? CheckCircle2 : AlertCircle
        const toneCls = success
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300'
            : 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300'

        return (
            <div className={className}>
                <div className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium shadow-sm ${toneCls}`}>
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{label}</span>
                    {detail ? <span className="text-xs opacity-80">{detail}</span> : null}
                </div>
            </div>
        )
    }

    return (
        <div className={className}>
            <div className="rounded-2xl border border-blue-200 bg-white/90 px-4 py-3 shadow-sm backdrop-blur dark:border-blue-500/20 dark:bg-slate-900/70">
                <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-100">
                            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-blue-500" />
                            <span>{label}</span>
                        </div>
                        {detail ? (
                            <p className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">{detail}</p>
                        ) : null}
                    </div>
                    <span className="shrink-0 text-sm font-semibold tabular-nums text-blue-600 dark:text-blue-300">
                        {Math.round(progress)}%
                    </span>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700/80">
                    <div
                        className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-500 transition-[width] duration-500 ease-out"
                        style={{ width: `${Math.max(6, Math.min(progress, 100))}%` }}
                    />
                </div>
            </div>
        </div>
    )
}
