import { useState } from 'react'
import { Sparkles, X, ArrowRight } from 'lucide-react'
import { RELAY_PROMO } from '@/config/promo'

const DISMISS_KEY = 'promo-relay-dismissed'

/** 首页可关闭的中转站推广横幅。文案/链接来自 @/config/promo，关闭状态记在 localStorage。 */
export default function PromoBanner() {
    const [dismissed, setDismissed] = useState(() => {
        try {
            return localStorage.getItem(DISMISS_KEY) === '1'
        } catch {
            return false
        }
    })

    if (!RELAY_PROMO.enabled || dismissed) return null

    const close = () => {
        try {
            localStorage.setItem(DISMISS_KEY, '1')
        } catch {
            /* localStorage 不可用时忽略 */
        }
        setDismissed(true)
    }

    return (
        <div className="relative flex items-center gap-3 rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200">
            <Sparkles className="w-4 h-4 shrink-0 text-indigo-500" />
            <p className="flex-1 leading-relaxed">
                用 Codex / Claude Code 有困难？推荐 {RELAY_PROMO.rate} 倍率的{' '}
                <a href={RELAY_PROMO.url} target="_blank" rel="noopener noreferrer" className="font-semibold hover:underline">
                    {RELAY_PROMO.name}
                </a>
                {' '}—— 一个 Key 通调 GPT / Claude / Grok，畅用 Codex / Claude Code，也能直接用于本站分析。
                <a
                    href={RELAY_PROMO.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 inline-flex items-center gap-0.5 font-semibold hover:underline"
                >
                    点此注册 <ArrowRight className="w-3 h-3" />
                </a>
            </p>
            <span className="shrink-0 self-start text-[10px] text-indigo-400 dark:text-indigo-500">推广</span>
            <button
                type="button"
                onClick={close}
                className="shrink-0 self-start rounded p-1 text-indigo-400 transition-colors hover:bg-indigo-100 hover:text-indigo-600 dark:hover:bg-indigo-900/40"
                aria-label="关闭推广"
            >
                <X className="w-4 h-4" />
            </button>
        </div>
    )
}
