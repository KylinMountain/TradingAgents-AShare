import { FormEvent, useMemo, useState } from 'react'
import { ArrowRight, CheckCircle2, Loader2, LockKeyhole, Mail, Radar, ShieldCheck, Sparkles, TrendingUp } from 'lucide-react'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { useNavigate } from 'react-router-dom'

const SIGNALS = [
    { label: '研究框架', value: '15-Agent' },
    { label: '工作区', value: '私有' },
    { label: '报告流', value: '实时' },
]

const AGENT_GROUPS = [
    {
        title: '分析团队',
        count: '6',
        items: ['市场分析', '舆情分析', '新闻分析', '基本面分析', '宏观分析', '主力资金'],
        description: '围绕行情、情绪、新闻、财务、宏观与资金流建立初始判断。',
    },
    {
        title: '研究团队',
        count: '4',
        items: ['博弈裁判', '多头研究', '空头研究', '研究总监'],
        description: '组织多空论证与博弈推演，收敛成投资计划与核心分歧。',
    },
    {
        title: '交易与风控',
        count: '4',
        items: ['交易员', '激进风控', '中性风控', '稳健风控'],
        description: '生成执行方案，并从不同风险偏好给出约束。',
    },
    {
        title: '组合决策',
        count: '1',
        items: ['组合经理'],
        description: '综合研究与风控结论，输出最终决策。',
    },
]

export default function Login() {
    const navigate = useNavigate()
    const { setAuth } = useAuthStore()
    const [email, setEmail] = useState('')
    const [code, setCode] = useState('')
    const [step, setStep] = useState<'email' | 'code'>('email')
    const [loading, setLoading] = useState(false)
    const [message, setMessage] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)

    const submitLabel = useMemo(() => step === 'email' ? '发送验证码' : '进入研究终端', [step])

    const handleRequestCode = async (e: FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setError(null)
        setMessage(null)
        try {
            const res = await api.requestLoginCode(email)
            setStep('code')
            setMessage(res.dev_code ? `开发环境验证码：${res.dev_code}` : '验证码已发送，请查收邮箱。')
        } catch (err) {
            setError(err instanceof Error ? err.message : '发送验证码失败')
        } finally {
            setLoading(false)
        }
    }

    const handleVerify = async (e: FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setError(null)
        try {
            const res = await api.verifyLoginCode(email, code)
            setAuth(res.access_token, res.user)
            navigate('/analysis', { replace: true })
        } catch (err) {
            setError(err instanceof Error ? err.message : '登录失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_0%_0%,rgba(34,211,238,0.16),transparent_28%),radial-gradient(circle_at_100%_0%,rgba(37,99,235,0.16),transparent_24%),linear-gradient(180deg,#f6f8fb_0%,#edf2f7_100%)] px-5 py-8 dark:bg-[radial-gradient(circle_at_0%_0%,rgba(34,211,238,0.18),transparent_22%),radial-gradient(circle_at_100%_0%,rgba(59,130,246,0.18),transparent_24%),linear-gradient(180deg,#020617_0%,#0b1120_100%)] md:px-10">
            <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl grid-cols-1 gap-10 lg:grid-cols-[1.12fr_0.88fr] lg:gap-0">
                <section className="relative flex flex-col justify-between px-2 py-4 lg:px-8 lg:py-10">
                    <div className="absolute left-0 top-0 h-72 w-72 rounded-full bg-cyan-400/10 blur-3xl dark:bg-cyan-400/10" />
                    <div className="absolute bottom-10 right-16 h-64 w-64 rounded-full bg-blue-500/10 blur-3xl dark:bg-blue-500/10" />

                    <div className="relative">
                        <div className="inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/85 px-3 py-1.5 text-xs tracking-[0.22em] text-slate-500 shadow-sm dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-400">
                            <Radar className="h-3.5 w-3.5 text-cyan-500" />
                            A 股多智能体研究系统
                        </div>

                        <div className="mt-10 max-w-3xl">
                            <h1 className="text-5xl font-semibold tracking-[-0.04em] text-slate-950 dark:text-white md:text-7xl">
                                为投研决策
                                <span className="mt-2 block bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 bg-clip-text text-transparent">
                                    设计的智能工作台
                                </span>
                            </h1>
                            <p className="mt-6 max-w-2xl text-base leading-8 text-slate-600 dark:text-slate-300 md:text-lg">
                                从市场、舆情、新闻、基本面、宏观、主力资金到风控与组合决策，将 15 个 Agent 的协作过程沉淀为可追踪、可复盘、可持续更新的研究链路。
                            </p>
                        </div>

                        <div className="mt-10 grid gap-3 sm:grid-cols-3">
                            {SIGNALS.map((item) => (
                                <div key={item.label} className="rounded-[28px] border border-slate-200/80 bg-white/88 p-5 shadow-[0_14px_40px_rgba(15,23,42,0.06)] backdrop-blur-sm dark:border-slate-800/90 dark:bg-slate-950 dark:shadow-[0_18px_44px_rgba(2,6,23,0.32)]">
                                    <div className="text-[11px] tracking-[0.18em] text-slate-400 dark:text-slate-500">{item.label}</div>
                                    <div className="mt-3 text-2xl font-semibold text-slate-900 dark:text-slate-50">{item.value}</div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="relative mt-10 rounded-[36px] border border-slate-200/80 bg-white/90 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl dark:border-slate-800/90 dark:bg-slate-950 dark:shadow-[0_28px_88px_rgba(2,6,23,0.5)] lg:mt-0">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-[11px] tracking-[0.22em] text-slate-400 dark:text-slate-500">12-AGENT 架构</div>
                                <div className="mt-2 text-xl font-semibold text-slate-950 dark:text-white">协同分工概览</div>
                            </div>
                            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-950 text-white dark:bg-white dark:text-slate-950">
                                <Sparkles className="h-5 w-5" />
                            </div>
                        </div>

                        <div className="mt-6 grid gap-3 md:grid-cols-2">
                            {AGENT_GROUPS.map((group) => (
                                <div key={group.title} className="rounded-[24px] border border-slate-200/80 bg-slate-50/90 p-4 dark:border-slate-800/90 dark:bg-slate-900">
                                    <div className="flex items-center justify-between">
                                        <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">{group.title}</div>
                                        <div className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-xs font-medium text-cyan-600 dark:text-cyan-300">
                                            {group.count} 名
                                        </div>
                                    </div>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                        {group.items.map((item) => (
                                            <span key={item} className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600 shadow-sm dark:bg-slate-800 dark:text-slate-200 dark:ring-1 dark:ring-slate-700/70">
                                                {item}
                                            </span>
                                        ))}
                                    </div>
                                    <div className="mt-3 text-sm leading-6 text-slate-500 dark:text-slate-400">{group.description}</div>
                                </div>
                            ))}
                        </div>

                        <div className="mt-5 flex items-start gap-3 rounded-[24px] bg-slate-950 px-4 py-4 text-slate-100 dark:border dark:border-slate-800/80 dark:bg-slate-900">
                            <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
                            <div className="text-sm leading-6 text-slate-300">
                                登录后可持续保存研究历史、模型配置与分析上下文，用于跟踪同一标的在不同日期下的判断演进。
                            </div>
                        </div>
                    </div>
                </section>

                <section className="flex items-center px-2 py-4 lg:justify-end lg:px-8 lg:py-10">
                    <div className="w-full max-w-md">
                        <div className="rounded-[36px] border border-slate-200/80 bg-white/92 p-7 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl dark:border-slate-800/90 dark:bg-slate-950 dark:shadow-[0_28px_88px_rgba(2,6,23,0.56)]">
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="text-[11px] tracking-[0.22em] text-slate-400 dark:text-slate-500">身份验证</div>
                                    <h2 className="mt-2 text-2xl font-semibold text-slate-950 dark:text-white">进入个人研究空间</h2>
                                </div>
                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 via-blue-500 to-indigo-600 text-white shadow-[0_12px_30px_rgba(37,99,235,0.28)]">
                                    <ShieldCheck className="h-6 w-6" />
                                </div>
                            </div>

                            <div className="mt-6 flex items-center gap-2 rounded-2xl bg-slate-100 p-1 dark:bg-slate-900 dark:ring-1 dark:ring-slate-800">
                                <div className={`flex-1 rounded-xl px-3 py-2 text-center text-sm transition-colors ${step === 'email' ? 'bg-white text-slate-950 shadow-sm dark:bg-slate-800 dark:text-white' : 'text-slate-500 dark:text-slate-400'}`}>
                                    邮箱验证
                                </div>
                                <div className={`flex-1 rounded-xl px-3 py-2 text-center text-sm transition-colors ${step === 'code' ? 'bg-white text-slate-950 shadow-sm dark:bg-slate-800 dark:text-white' : 'text-slate-500 dark:text-slate-400'}`}>
                                    输入验证码
                                </div>
                            </div>

                            <form onSubmit={step === 'email' ? handleRequestCode : handleVerify} className="mt-6 space-y-4">
                                <div>
                                    <label className="mb-2 block text-sm font-medium text-slate-600 dark:text-slate-400">邮箱地址</label>
                                    <div className="relative">
                                        <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                                        <input
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            className="input h-12 w-full rounded-2xl pl-11"
                                            placeholder="you@example.com"
                                            disabled={loading || step === 'code'}
                                            required
                                        />
                                    </div>
                                </div>

                                {step === 'code' && (
                                    <div>
                                        <label className="mb-2 block text-sm font-medium text-slate-600 dark:text-slate-400">验证码</label>
                                        <div className="relative">
                                            <LockKeyhole className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                                            <input
                                                type="text"
                                                value={code}
                                                onChange={(e) => setCode(e.target.value)}
                                                className="input h-12 w-full rounded-2xl pl-11 tracking-[0.35em]"
                                                placeholder="输入 6 位验证码"
                                                maxLength={6}
                                                required
                                            />
                                        </div>
                                    </div>
                                )}

                                {message && (
                                    <div className="flex items-start gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                                        <span>{message}</span>
                                    </div>
                                )}
                                {error && (
                                    <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/12 dark:text-rose-200">
                                        {error}
                                    </div>
                                )}

                                <button type="submit" disabled={loading} className="btn-primary flex h-12 w-full items-center justify-center gap-2 rounded-2xl">
                                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                                    {submitLabel}
                                </button>

                                {step === 'code' && (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setCode('')
                                            setStep('email')
                                            setMessage(null)
                                            setError(null)
                                        }}
                                        className="btn-secondary flex h-12 w-full items-center justify-center rounded-2xl"
                                    >
                                        重新获取验证码
                                    </button>
                                )}
                            </form>

                            <div className="mt-6 rounded-2xl bg-slate-100/90 px-4 py-3 text-xs leading-6 text-slate-500 dark:border dark:border-slate-800/80 dark:bg-slate-900 dark:text-slate-400">
                                当前账户将独占保存报告历史、模型密钥与分析上下文，适合持续跟踪个人研究对象。
                            </div>
                        </div>
                    </div>
                </section>
            </div>

            <footer className="mx-auto mt-8 max-w-7xl text-center text-xs text-slate-400 dark:text-slate-500">
                <p>
                    &copy; {new Date().getFullYear()} KylinMountain &middot; 仅限非商业用途（PolyForm NC 1.0） &middot;{' '}
                    <a href="https://github.com/KylinMountain/TradingAgents-AShare" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-slate-600 dark:hover:text-slate-300">
                        GitHub
                    </a>
                    {' '}&middot;{' '}
                    <a href="https://app.510168.xyz" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-slate-600 dark:hover:text-slate-300">
                        官网
                    </a>
                </p>
            </footer>
        </div>
    )
}
