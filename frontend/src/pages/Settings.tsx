import { useState, useEffect, useMemo } from 'react'
import { Save, Key, Database, Loader2, MessageSquare, User, Trash2, Link2, Copy, Plus, CheckCircle2, Mail, Flame, RefreshCw, Info, Webhook } from 'lucide-react'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import type { PortfolioImportState, PortfolioPositionInput, RuntimeWarmupResult, UserToken } from '@/types'

type ProviderPreset = {
    id: string
    label: string
    provider: string
    baseUrl: string
    protocol: string
    editableBaseUrl?: boolean
}

const PROVIDER_PRESETS: ProviderPreset[] = [
    { id: 'openai', label: 'OpenAI', provider: 'openai', baseUrl: 'https://api.openai.com/v1', protocol: 'OpenAI' },
    { id: 'anthropic', label: 'Anthropic', provider: 'anthropic', baseUrl: '', protocol: 'Anthropic' },
    { id: 'google', label: 'Google Gemini', provider: 'google', baseUrl: '', protocol: 'Google' },
    { id: 'dashscope', label: '阿里云百炼（DashScope）', provider: 'openai', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', protocol: 'OpenAI 兼容' },
    { id: 'deepseek', label: 'DeepSeek', provider: 'openai', baseUrl: 'https://api.deepseek.com/v1', protocol: 'OpenAI 兼容' },
    { id: 'moonshot', label: 'Moonshot AI（Kimi）', provider: 'openai', baseUrl: 'https://api.moonshot.cn/v1', protocol: 'OpenAI 兼容' },
    { id: 'zhipu', label: '智谱 AI', provider: 'openai', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', protocol: 'OpenAI 兼容' },
    { id: 'siliconflow', label: '硅基流动', provider: 'openai', baseUrl: 'https://api.siliconflow.cn/v1', protocol: 'OpenAI 兼容' },
    { id: 'custom-openai', label: '自定义 OpenAI 兼容', provider: 'openai', baseUrl: '', protocol: 'OpenAI 兼容', editableBaseUrl: true },
]

function inferPreset(llmProvider: string, backendUrl: string): string {
    const normalizedProvider = (llmProvider || '').toLowerCase()
    const normalizedUrl = (backendUrl || '').replace(/\/$/, '')
    const matched = PROVIDER_PRESETS.find((preset) => {
        if (preset.provider !== normalizedProvider) return false
        if (!preset.baseUrl && preset.id !== 'custom-openai') return true
        return preset.baseUrl.replace(/\/$/, '') === normalizedUrl
    })
    if (matched) return matched.id
    if (normalizedProvider === 'openai') return 'custom-openai'
    return normalizedProvider || 'openai'
}

export default function Settings() {
    const { user } = useAuthStore()
    const [defaultAnalysts, setDefaultAnalysts] = useState(['market', 'social', 'news', 'fundamentals', 'macro', 'smart_money', 'volume_price'])
    const [customPrompt, setCustomPrompt] = useState('')
    const [llmApiKey, setLlmApiKey] = useState('')
    const [hasStoredApiKey, setHasStoredApiKey] = useState(false)
    const [wecomWebhook, setWecomWebhook] = useState('')
    const [hasStoredWebhook, setHasStoredWebhook] = useState(false)
    const [storedWebhookDisplay, setStoredWebhookDisplay] = useState('')

    const [providerPreset, setProviderPreset] = useState('openai')
    const [customBaseUrl, setCustomBaseUrl] = useState('')
    const [deepThinkLlm, setDeepThinkLlm] = useState('')
    const [quickThinkLlm, setQuickThinkLlm] = useState('')
    const [maxDebateRounds, setMaxDebateRounds] = useState(1)
    const [maxRiskRounds, setMaxRiskRounds] = useState(1)
    const [serverFallbackEnabled, setServerFallbackEnabled] = useState(true)
    const [emailReportEnabled, setEmailReportEnabled] = useState(true)
    const [wecomReportEnabled, setWecomReportEnabled] = useState(true)
    const [portfolioImportState, setPortfolioImportState] = useState<PortfolioImportState | null>(null)
    const [portfolioSyncing, setPortfolioSyncing] = useState(false)
    const [portfolioAutoApply, setPortfolioAutoApply] = useState(true)
    const [portfolioPositionsText, setPortfolioPositionsText] = useState('')

    const [configLoading, setConfigLoading] = useState(false)
    const [saving, setSaving] = useState(false)
    const [modelSaving, setModelSaving] = useState(false)
    const [saveAllSaving, setSaveAllSaving] = useState(false)
    const [warmingUp, setWarmingUp] = useState(false)
    const [saved, setSaved] = useState(false)
    const [saveMessage, setSaveMessage] = useState('设置已保存')
    const [configError, setConfigError] = useState<string | null>(null)
    const [warmupResults, setWarmupResults] = useState<RuntimeWarmupResult[]>([])
    const [warmupError, setWarmupError] = useState<string | null>(null)
    const [wecomWarmingUp, setWecomWarmingUp] = useState(false)
    const [wecomWarmupMessage, setWecomWarmupMessage] = useState<string | null>(null)
    const [wecomWarmupError, setWecomWarmupError] = useState<string | null>(null)

    // API Token states
    const [tokens, setTokens] = useState<UserToken[]>([])
    const [tokensLoading, setTokensLoading] = useState(false)
    const [newTokenName, setNewTokenName] = useState('')
    const [isCreatingToken, setIsCreatingToken] = useState(false)
    const [copiedTokenId, setCopiedTokenId] = useState<string | null>(null)
    const [newlyCreatedToken, setNewlyCreatedToken] = useState<string | null>(null)

    const selectedPreset = useMemo(
        () => PROVIDER_PRESETS.find((item) => item.id === providerPreset) || PROVIDER_PRESETS[0],
        [providerPreset],
    )

    const effectiveProvider = selectedPreset.provider
    const effectiveBaseUrl = selectedPreset.editableBaseUrl ? customBaseUrl.trim() : selectedPreset.baseUrl
    const portfolioPositionCount = portfolioImportState?.summary?.positions ?? 0

    useEffect(() => {
        setWarmupResults([])
        setWarmupError(null)
    }, [providerPreset, customBaseUrl, deepThinkLlm, quickThinkLlm, llmApiKey])

    useEffect(() => {
        setWecomWarmupMessage(null)
        setWecomWarmupError(null)
    }, [wecomWebhook])

    useEffect(() => {
        try {
            const stored = localStorage.getItem('tradingagents-settings')
            if (stored) {
                const s = JSON.parse(stored) as Record<string, unknown> & {
                    defaultAnalysts?: string[]
                }
                if ('apiUrl' in s) {
                    delete s.apiUrl
                    localStorage.setItem('tradingagents-settings', JSON.stringify(s))
                }
                if (s.defaultAnalysts) setDefaultAnalysts(s.defaultAnalysts)
                if (typeof s.customPrompt === 'string') setCustomPrompt(s.customPrompt)
            }
        } catch {}
    }, [])

    useEffect(() => {
        setConfigLoading(true)
        setConfigError(null)
        api.getConfig()
            .then(cfg => {
                setProviderPreset(inferPreset(cfg.llm_provider, cfg.backend_url))
                setCustomBaseUrl(cfg.backend_url || '')
                setDeepThinkLlm(cfg.deep_think_llm)
                setQuickThinkLlm(cfg.quick_think_llm)
                setMaxDebateRounds(cfg.max_debate_rounds)
                setMaxRiskRounds(cfg.max_risk_discuss_rounds)
                setHasStoredApiKey(!!cfg.has_api_key)
                setHasStoredWebhook(!!cfg.has_wecom_webhook)
                setStoredWebhookDisplay(cfg.wecom_webhook_display || '')
                setServerFallbackEnabled(!!cfg.server_fallback_enabled)
                setEmailReportEnabled(cfg.email_report_enabled !== false)
                setWecomReportEnabled(cfg.wecom_report_enabled !== false)
            })
            .catch(err => {
                setConfigError(err instanceof Error ? err.message : '无法连接到后端')
            })
            .finally(() => setConfigLoading(false))

        // Fetch tokens
        fetchTokens()
        void fetchPortfolioImportState()
    }, [])

    const fetchTokens = async () => {
        setTokensLoading(true)
        try {
            const data = await api.getTokens()
            setTokens(data)
        } catch (err) {
            console.error('Failed to fetch tokens:', err)
        } finally {
            setTokensLoading(false)
        }
    }

    const fetchPortfolioImportState = async () => {
        try {
            const state = await api.getPortfolioImportState()
            setPortfolioImportState(state)
        } catch (err) {
            console.error('Failed to fetch portfolio import state:', err)
        }
    }

    const handleCreateToken = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!newTokenName.trim()) return
        setIsCreatingToken(true)
        try {
            const created = await api.createToken({ name: newTokenName.trim() })
            setNewTokenName('')
            setNewlyCreatedToken(created.token || null)
            await fetchTokens()
        } catch (err) {
            alert(err instanceof Error ? err.message : '创建 Token 失败')
        } finally {
            setIsCreatingToken(false)
        }
    }

    const handleDeleteToken = async (tokenId: string) => {
        if (!confirm('确定要吊销此 Token 吗？吊销后使用该 Token 的 API 请求将立即失效。')) return
        try {
            await api.deleteToken(tokenId)
            await fetchTokens()
        } catch (err) {
            alert(err instanceof Error ? err.message : '吊销 Token 失败')
        }
    }

    const copyToClipboard = (text: string, id: string) => {
        navigator.clipboard.writeText(text)
        setCopiedTokenId(id)
        setTimeout(() => setCopiedTokenId(null), 2000)
    }

    const persistLocalSettings = () => {
        localStorage.setItem('tradingagents-settings', JSON.stringify({
            defaultAnalysts,
            customPrompt,
        }))
        localStorage.setItem('ta-custom-prompt', customPrompt)
    }

    const buildRuntimeConfigPayload = (options?: { includeEmail?: boolean; includeWecom?: boolean }) => ({
        llm_provider: effectiveProvider,
        backend_url: effectiveBaseUrl || undefined,
        deep_think_llm: deepThinkLlm,
        quick_think_llm: quickThinkLlm,
        max_debate_rounds: maxDebateRounds,
        max_risk_discuss_rounds: maxRiskRounds,
        api_key: llmApiKey || undefined,
        ...(options?.includeWecom ? {
            wecom_webhook_url: wecomWebhook.trim() || undefined,
            wecom_report_enabled: wecomReportEnabled,
        } : {}),
        ...(options?.includeEmail ? { email_report_enabled: emailReportEnabled } : {}),
    })

    const showSavedMessage = (message: string) => {
        setSaveMessage(message)
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
    }

    const parsePortfolioPositions = (text: string): PortfolioPositionInput[] => {
        const lines = text.split('\n').map(l => l.trim()).filter(Boolean)
        const positions: PortfolioPositionInput[] = []
        for (const line of lines) {
            const parts = line.split(/[,\t，\s]+/).filter(Boolean)
            if (!parts[0]) continue
            const symbol = parts[0]
            let nameIdx = -1
            let numStart = 1
            if (parts[1] && !/^[\d.]+$/.test(parts[1])) {
                nameIdx = 1
                numStart = 2
            }
            const nums = parts.slice(numStart).map(v => {
                const n = parseFloat(v)
                return isNaN(n) ? null : n
            })
            positions.push({
                symbol,
                name: nameIdx >= 0 ? parts[nameIdx] : undefined,
                current_position: nums[0] ?? null,
                average_cost: nums[1] ?? null,
                market_value: nums[2] ?? null,
            })
        }
        return positions
    }

    const syncPortfolioImport = async (options?: { successMessage?: string }) => {
        const positions = parsePortfolioPositions(portfolioPositionsText)
        if (positions.length === 0) {
            throw new Error('请输入至少一条持仓记录')
        }
        setPortfolioSyncing(true)
        try {
            const result = await api.syncPortfolioImport({
                positions,
                auto_apply_scheduled: portfolioAutoApply,
            })
            setPortfolioImportState(result)
            showSavedMessage(options?.successMessage || '持仓已保存')
            return result
        } finally {
            setPortfolioSyncing(false)
        }
    }

    const submitConfig = async (options?: { forceWarmup?: boolean; successMessage?: string; includeEmail?: boolean; includeWecom?: boolean }) => {
        persistLocalSettings()
        const { forceWarmup = false, successMessage = '设置已保存', includeEmail = true, includeWecom = false } = options || {}
        const response = await api.updateConfig({
            ...buildRuntimeConfigPayload({ includeEmail, includeWecom }),
            warmup: true,
            force_warmup: forceWarmup,
        })
        setHasStoredApiKey(!!response.has_api_key)
        setHasStoredWebhook(!!response.current.has_wecom_webhook)
        setStoredWebhookDisplay(response.current.wecom_webhook_display || '')
        setWecomReportEnabled(response.current.wecom_report_enabled !== false)
        setLlmApiKey('')
        setWecomWebhook('')
        showSavedMessage(response.warmup?.message || successMessage)
        return response
    }

    const handleSaveModel = async () => {
        setModelSaving(true)
        try {
            await submitConfig({ includeEmail: false, includeWecom: false, successMessage: '模型配置已保存' })
        } catch (err) {
            alert(err instanceof Error ? err.message : '保存模型配置失败')
        } finally {
            setModelSaving(false)
        }
    }

    const handleSaveAll = async () => {
        setSaveAllSaving(true)
        try {
            await submitConfig({ includeEmail: true, includeWecom: true, successMessage: '全部设置已保存' })
            if (portfolioPositionsText.trim()) {
                await syncPortfolioImport({ successMessage: '全部设置已保存' })
            } else {
                showSavedMessage('全部设置已保存')
            }
        } catch (err) {
            alert(err instanceof Error ? err.message : '保存全部设置失败')
        } finally {
            setSaveAllSaving(false)
        }
    }

    const handleWarmup = async () => {
        setWarmingUp(true)
        setWarmupError(null)
        setWarmupResults([])
        try {
            const response = await api.warmupConfig({
                ...buildRuntimeConfigPayload(),
                prompt: '你好',
            })
            setWarmupResults(response.results || [])
        } catch (err) {
            setWarmupError(err instanceof Error ? err.message : 'Warmup 触发失败')
        } finally {
            setWarmingUp(false)
        }
    }
    const handleClearApiKey = async () => {
        if (!hasStoredApiKey) return
        setSaving(true)
        try {
            const response = await api.updateConfig({ clear_api_key: true })
            setHasStoredApiKey(!!response.has_api_key)
            setLlmApiKey('')
            setSaved(true)
            setTimeout(() => setSaved(false), 2000)
        } catch (err) {
            alert(err instanceof Error ? err.message : '清除密钥失败')
        } finally {
            setSaving(false)
        }
    }

    const handleClearWebhook = async () => {
        if (!hasStoredWebhook) return
        setSaving(true)
        try {
            const response = await api.updateConfig({ clear_wecom_webhook: true })
            setHasStoredWebhook(!!response.current.has_wecom_webhook)
            setStoredWebhookDisplay(response.current.wecom_webhook_display || '')
            setWecomWebhook('')
            setWecomWarmupMessage(null)
            setWecomWarmupError(null)
            showSavedMessage('企业微信机器人已清除')
        } catch (err) {
            alert(err instanceof Error ? err.message : '清除企业微信机器人失败')
        } finally {
            setSaving(false)
        }
    }

    const handleWecomWarmup = async () => {
        setWecomWarmingUp(true)
        setWecomWarmupMessage(null)
        setWecomWarmupError(null)
        try {
            const response = await api.warmupWecom({
                wecom_webhook_url: wecomWebhook.trim() || undefined,
            })
            setWecomWarmupMessage(
                response.webhook_display
                    ? `${response.message}，目标：${response.webhook_display}`
                    : response.message
            )
        } catch (err) {
            setWecomWarmupError(err instanceof Error ? err.message : 'Webhook 测试发送失败')
        } finally {
            setWecomWarmingUp(false)
        }
    }

    const handleSavePortfolio = async () => {
        try {
            await syncPortfolioImport({ successMessage: '持仓已保存' })
        } catch (err) {
            alert(err instanceof Error ? err.message : '持仓保存失败')
        }
    }

    const clearPortfolioImport = async () => {
        if (!confirm('确定清空已导入的持仓上下文吗？')) return
        try {
            await api.clearPortfolioImport()
            await fetchPortfolioImportState()
            setPortfolioPositionsText('')
        } catch (err) {
            alert(err instanceof Error ? err.message : '清空持仓失败')
        }
    }

    const toggleAnalyst = (analyst: string) => {
        setDefaultAnalysts(prev =>
            prev.includes(analyst) ? prev.filter(a => a !== analyst) : [...prev, analyst]
        )
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">系统设置</h1>
                <p className="text-slate-500 dark:text-slate-400 mt-1">配置当前账户的分析参数、模型与持仓追踪</p>
            </div>

            <div className="card space-y-3">
                <div className="flex items-center gap-2">
                    <User className="w-5 h-5 text-cyan-500" />
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">账户空间</h2>
                </div>
                <div className="text-sm text-slate-600 dark:text-slate-300">
                    <div>当前登录：{user?.email || '-'}</div>
                    <div className="mt-1 text-slate-500 dark:text-slate-400">报告历史、分析任务和模型配置仅当前账户可见。</div>
                </div>
            </div>

            <div className=”card space-y-4”>
                <div className=”flex items-center gap-2”>
                    <Database className=”w-5 h-5 text-emerald-500” />
                    <h2 className=”text-lg font-semibold text-slate-900 dark:text-slate-100”>持仓追踪</h2>
                    <div className=”group relative”>
                        <button
                            type=”button”
                            aria-label=”持仓追踪说明”
                            className=”flex h-5 w-5 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 transition-colors hover:border-sky-300 hover:text-sky-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500 dark:hover:border-sky-500/40 dark:hover:text-sky-300”
                        >
                            <Info className=”h-3 w-3” />
                        </button>
                        <div className=”pointer-events-none absolute left-0 top-7 z-20 w-[360px] rounded-2xl border border-slate-200 bg-white p-4 text-left text-xs leading-6 text-slate-600 opacity-0 shadow-2xl transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200”>
                            <div className=”font-medium text-slate-900 dark:text-slate-100”>如何导入持仓</div>
                            <div className=”mt-2”>
                                每行输入一只股票，格式：<code className=”bg-slate-100 dark:bg-slate-800 px-1 rounded”>代码 名称 持仓 成本 市值</code>
                            </div>
                            <div className=”mt-2”>
                                支持用逗号、Tab 或空格分隔。股票代码支持 600519.SH 或纯 6 位数字。
                            </div>
                            <div className=”mt-2”>
                                导入后跟踪看板和定时分析会自动使用持仓上下文。
                            </div>
                        </div>
                    </div>
                    <div className=”ml-auto flex items-center gap-3”>
                        {portfolioSyncing && <Loader2 className=”w-4 h-4 animate-spin text-slate-400” />}
                        <button
                            type=”button”
                            onClick={handleSavePortfolio}
                            disabled={portfolioSyncing || saveAllSaving}
                            className=”btn-secondary inline-flex items-center gap-2”
                        >
                            {portfolioSyncing ? <Loader2 className=”w-4 h-4 animate-spin” /> : <Save className=”w-4 h-4” />}
                            保存
                        </button>
                    </div>
                </div>
                <p className=”text-sm text-slate-500 dark:text-slate-400”>
                    在这里导入持仓信息。保存后跟踪看板和定时分析会自动使用最新持仓上下文。
                </p>

                <div>
                    <label className=”block text-sm font-medium text-slate-600 dark:text-slate-300 mb-2”>持仓列表（每行一只）</label>
                    <textarea
                        value={portfolioPositionsText}
                        onChange={e => setPortfolioPositionsText(e.target.value)}
                        rows={6}
                        className=”input w-full font-mono text-xs”
                        placeholder={“600519.SH 贵州茅台 100 1800.5 180050\n000858 五粮液 200 150.3 30060\n300750 宁德时代 50 210 10500”}
                    />
                    <p className=”mt-1 text-xs text-slate-400 dark:text-slate-500”>
                        格式：代码 [名称] [持仓数] [成本价] [市值]，用逗号/Tab/空格分隔
                    </p>
                </div>

                <label className=”flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300”>
                    <input type=”checkbox” checked={portfolioAutoApply} onChange={e => setPortfolioAutoApply(e.target.checked)} />
                    自动加入定时任务
                </label>

                <div className=”flex flex-wrap gap-3”>
                    <button type=”button” onClick={() => { void handleSavePortfolio() }} disabled={portfolioSyncing || saveAllSaving} className=”btn-primary inline-flex items-center gap-2”>
                        {portfolioSyncing ? <Loader2 className=”w-4 h-4 animate-spin” /> : <RefreshCw className=”w-4 h-4” />}
                        保存持仓
                    </button>
                    <button type=”button” onClick={clearPortfolioImport} className=”inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/60”>
                        <Trash2 className=”w-4 h-4” />
                        清空持仓
                    </button>
                </div>

                {portfolioImportState && portfolioPositionCount > 0 && (
                    <div className=”rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-900/40 p-4 space-y-2 text-sm”>
                        <div className=”flex flex-wrap gap-3 text-slate-600 dark:text-slate-300”>
                            <span>持仓 {portfolioPositionCount} 只</span>
                            <span>{portfolioImportState.last_synced_at ? `最近同步 ${portfolioImportState.last_synced_at.slice(0, 19).replace('T', ' ')}` : '尚未同步'}</span>
                        </div>
                        {!!portfolioImportState.scheduled_sync && (
                            <div className=”flex flex-wrap gap-3 text-xs text-indigo-600 dark:text-indigo-300”>
                                <span>新增定时任务 {portfolioImportState.scheduled_sync.created.length} 只</span>
                                <span>已存在 {portfolioImportState.scheduled_sync.existing.length} 只</span>
                                {portfolioImportState.scheduled_sync.skipped_limit.length > 0 && (
                                    <span>超出上限未加入 {portfolioImportState.scheduled_sync.skipped_limit.length} 只</span>
                                )}
                            </div>
                        )}
                        <div className=”max-h-64 overflow-y-auto pr-1 space-y-2”>
                            {portfolioImportState.positions.map(item => (
                                <div
                                    key={item.symbol}
                                    className=”flex flex-wrap gap-3 rounded-xl border border-slate-200/80 dark:border-slate-700/80 bg-white/80 dark:bg-slate-950/30 px-3 py-2 text-xs text-slate-500 dark:text-slate-400”
                                >
                                    <span className=”font-medium text-slate-700 dark:text-slate-200”>{item.name}</span>
                                    <span>{item.symbol}</span>
                                    <span>持仓 {item.current_position ?? '-'}</span>
                                    <span>成本 {item.average_cost ?? '-'}</span>
                                    <span>市值 {item.market_value ?? '-'}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            <div className="card space-y-4">
                <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-purple-500" />
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">模型接入</h2>
                    <div className="ml-auto flex items-center gap-3">
                        {configLoading && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
                        <button
                            type="button"
                            onClick={handleSaveModel}
                            disabled={configLoading || modelSaving || saveAllSaving}
                            className="btn-secondary inline-flex items-center gap-2"
                        >
                            {modelSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            保存
                        </button>
                    </div>
                </div>

                {configError && (
                    <p className="text-sm text-amber-500">⚠ {configError}（显示本地默认值）</p>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                            模型厂商
                        </label>
                        <select
                            value={providerPreset}
                            onChange={e => setProviderPreset(e.target.value)}
                            className="input w-full"
                            disabled={configLoading}
                        >
                            {PROVIDER_PRESETS.map((preset) => (
                                <option key={preset.id} value={preset.id}>{preset.label}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                            接入协议
                        </label>
                        <div className="input w-full flex items-center gap-2 bg-slate-50 dark:bg-slate-900/70 text-slate-600 dark:text-slate-300">
                            <Link2 className="w-4 h-4 text-slate-400" />
                            <span>{selectedPreset.protocol}</span>
                        </div>
                    </div>

                    {(selectedPreset.baseUrl || selectedPreset.editableBaseUrl) && (
                        <div className="md:col-span-2">
                            <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                                Base URL
                            </label>
                            <input
                                type="text"
                                value={selectedPreset.editableBaseUrl ? customBaseUrl : selectedPreset.baseUrl}
                                onChange={e => setCustomBaseUrl(e.target.value)}
                                className="input w-full"
                                disabled={configLoading || !selectedPreset.editableBaseUrl}
                                placeholder="https://your-openai-compatible-endpoint/v1"
                            />
                            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                {selectedPreset.editableBaseUrl
                                    ? '自定义 OpenAI 兼容服务需要自行填写 Base URL。'
                                    : '该厂商默认通过预设的 OpenAI 兼容地址接入，通常只需填写模型名和 API Key。'}
                            </p>
                        </div>
                    )}

                    <div>
                        <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                            常规模型
                            <span className="ml-1 text-xs text-slate-400 font-normal">用于意图识别、JSON 提取等轻量任务</span>
                        </label>
                        <input
                            type="text"
                            value={quickThinkLlm}
                            onChange={e => setQuickThinkLlm(e.target.value)}
                            className="input w-full"
                            placeholder="例如：gpt-4.1-mini / deepseek-chat / moonshot-v1-8k"
                            disabled={configLoading}
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                            推理模型
                            <span className="ml-1 text-xs text-slate-400 font-normal">用于深度分析、辩论等复杂任务</span>
                        </label>
                        <input
                            type="text"
                            value={deepThinkLlm}
                            onChange={e => setDeepThinkLlm(e.target.value)}
                            className="input w-full"
                            placeholder="例如：gpt-4.1 / deepseek-reasoner / kimi-k2-0905-preview"
                            disabled={configLoading}
                        />
                    </div>

                    <div className="md:col-span-2">
                        <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                            用户模型 Key
                        </label>
                        <div className="relative">
                            <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <input
                                type="password"
                                value={llmApiKey}
                                onChange={e => setLlmApiKey(e.target.value)}
                                className="input w-full pl-10"
                                placeholder={hasStoredApiKey ? '已保存，留空则保持不变' : '输入你的模型 API Key'}
                                disabled={configLoading}
                            />
                        </div>
                        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                            <div className="text-xs text-slate-500 dark:text-slate-400">
                                {serverFallbackEnabled
                                    ? '当前后端已开启公共模型回退：未填写个人 Key 时，可能仍会使用服务端默认模型配置。'
                                    : '当前后端已关闭公共模型回退：未填写个人 Key 时，将无法发起需要模型的分析任务。'}
                            </div>
                            {hasStoredApiKey && (
                                <button
                                    type="button"
                                    onClick={handleClearApiKey}
                                    disabled={saving || modelSaving || saveAllSaving}
                                    className="inline-flex items-center gap-1 text-xs text-rose-500 hover:text-rose-600 disabled:opacity-50"
                                >
                                    <Trash2 className="w-3.5 h-3.5" />
                                    清除密钥
                                </button>
                            )}
                        </div>
                        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                            保存模型配置后，系统会在后台自动 warmup 当前模型；也可以直接在这里点击 warmup，默认发送“你好”并查看模型原始回复。
                        </p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                            辩论轮数上限
                        </label>
                        <input
                            type="number"
                            min={1}
                            max={5}
                            value={maxDebateRounds}
                            onChange={e => setMaxDebateRounds(Number(e.target.value))}
                            className="input w-full"
                            disabled={configLoading}
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                            风险讨论轮数上限
                        </label>
                        <input
                            type="number"
                            min={1}
                            max={5}
                            value={maxRiskRounds}
                            onChange={e => setMaxRiskRounds(Number(e.target.value))}
                            className="input w-full"
                            disabled={configLoading}
                        />
                    </div>

                    <div className="md:col-span-2 rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-slate-50/80 dark:bg-slate-900/40 p-4 space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <div className="text-sm font-medium text-slate-900 dark:text-slate-100">Warmup 测试</div>
                                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                    使用当前表单配置向模型发送“你好”，不会自动保存设置。
                                </p>
                            </div>
                            <button onClick={handleWarmup} disabled={saving || modelSaving || saveAllSaving || warmingUp || configLoading} className="btn-secondary inline-flex items-center gap-2">
                                {warmingUp ? <Loader2 className="w-4 h-4 animate-spin" /> : <Flame className="w-4 h-4" />}
                                {warmingUp ? '测试中...' : '立即 Warmup'}
                            </button>
                        </div>

                        {warmupError && (
                            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-600 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300">
                                {warmupError}
                            </div>
                        )}

                        {warmupResults.length > 0 && (
                            <div className="space-y-3">
                                {warmupResults.map((item, index) => (
                                    <div
                                        key={`${item.model}-${index}`}
                                        className="rounded-xl border border-slate-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-950/40 px-4 py-3"
                                    >
                                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                                            <span className="font-medium text-slate-700 dark:text-slate-200">{item.targets.join(' / ')}</span>
                                            <span>{item.model}</span>
                                        </div>
                                        {item.content && (
                                            <pre className="mt-2 whitespace-pre-wrap break-words font-sans text-sm text-slate-700 dark:text-slate-200">
                                                {item.content}
                                            </pre>
                                        )}
                                        {item.error && (
                                            <p className="mt-2 text-sm text-rose-500 dark:text-rose-300">{item.error}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="card space-y-4">
                <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-green-500" />
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">默认分析配置</h2>
                </div>

                <div>
                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                        默认启用分析师
                    </label>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {[
                            { key: 'market', label: '市场分析' },
                            { key: 'social', label: '舆情分析' },
                            { key: 'news', label: '新闻分析' },
                            { key: 'fundamentals', label: '基本面' },
                            { key: 'macro', label: '宏观板块' },
                            { key: 'smart_money', label: '主力资金' },
                            { key: 'volume_price', label: '量价分析' },
                        ].map((analyst) => {
                            const active = defaultAnalysts.includes(analyst.key)
                            return (
                                <button
                                    key={analyst.key}
                                    type="button"
                                    onClick={() => toggleAnalyst(analyst.key)}
                                    className={`rounded-xl border px-3 py-3 text-sm transition-colors ${
                                        active
                                            ? 'bg-blue-50 dark:bg-blue-500/10 border-blue-500 text-blue-600 dark:text-blue-400'
                                            : 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-400'
                                    }`}
                                >
                                    {analyst.label}
                                </button>
                            )
                        })}
                    </div>
                </div>
            </div>

            <div className="card space-y-4">
                <div className="flex items-center gap-2">
                    <Key className="w-5 h-5 text-amber-500" />
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">API 访问令牌</h2>
                    {tokensLoading && <Loader2 className="w-4 h-4 animate-spin text-slate-400 ml-auto" />}
                </div>

                <div className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                    使用 API Token 在三方应用（如 Open Claw）中调用投研分析接口。请妥善保管您的 Token。
                </div>

                {/* Newly created token — show once */}
                {newlyCreatedToken && (
                    <div className="p-3 rounded-2xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800">
                        <div className="text-sm font-medium text-emerald-800 dark:text-emerald-200 mb-1">Token 创建成功 — 请立即复制，关闭后无法再次查看</div>
                        <div className="flex items-center gap-2">
                            <code className="text-xs text-emerald-700 dark:text-emerald-300 bg-white dark:bg-slate-950 px-1.5 py-0.5 rounded border font-mono tracking-tight break-all">
                                {newlyCreatedToken}
                            </code>
                            <button
                                onClick={() => copyToClipboard(newlyCreatedToken, '__new__')}
                                className="p-1 hover:bg-emerald-100 dark:hover:bg-emerald-800 rounded transition-colors text-emerald-600"
                                title="复制 Token"
                            >
                                {copiedTokenId === '__new__' ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                            </button>
                        </div>
                        <button onClick={() => setNewlyCreatedToken(null)} className="mt-2 text-xs text-emerald-600 hover:underline">我已复制，关闭提示</button>
                    </div>
                )}

                {/* Token List */}
                <div className="space-y-3">
                    {tokens.map((token) => (
                        <div key={token.id} className="flex flex-col sm:flex-row sm:items-center gap-3 p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border border-slate-100 dark:border-slate-800 transition-all group">
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">{token.name}</div>
                                <div className="flex items-center gap-2 mt-1">
                                    <code className="text-xs text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-950 px-1.5 py-0.5 rounded border border-slate-100 dark:border-slate-800 font-mono tracking-tight">
                                        ta-sk-{'•'.repeat(16)}{token.token_hint || '****'}
                                    </code>
                                </div>
                                <div className="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
                                    创建于：{new Date(token.created_at).toLocaleDateString()}
                                    {token.last_used_at && ` • 最后使用：${new Date(token.last_used_at).toLocaleString()}`}
                                </div>
                            </div>
                            <button
                                onClick={() => handleDeleteToken(token.id)}
                                className="self-end sm:self-center p-2 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/10 rounded-xl transition-colors"
                                title="吊销 Token"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}

                    {tokens.length === 0 && !tokensLoading && (
                        <div className="text-center py-6 border-2 border-dashed border-slate-100 dark:border-slate-800 rounded-3xl text-slate-400 text-sm font-medium">
                            暂无活跃的 API Token
                        </div>
                    )}
                </div>

                {/* Create Token Form */}
                    <form onSubmit={handleCreateToken} className="flex items-center gap-2 pt-2">
                        <input
                            type="text"
                            value={newTokenName}
                            onChange={e => setNewTokenName(e.target.value)}
                            placeholder="给新 Token 起个名字，如：Open Claw"
                            className="input flex-1 h-10 text-sm"
                            disabled={isCreatingToken || tokens.length >= 10}
                        />
                    <button
                        type="submit"
                        disabled={isCreatingToken || !newTokenName.trim() || tokens.length >= 10}
                        className="btn-primary h-10 px-4 flex items-center gap-2 whitespace-nowrap text-sm"
                    >
                        {isCreatingToken ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                        生成 Token
                    </button>
                </form>
                {tokens.length >= 10 && (
                    <p className="text-[10px] text-amber-500">已达到 Token 创建上限（10个）</p>
                )}
            </div>

            <div className="card space-y-3">
                <div className="flex items-center gap-2">
                    <Mail className="w-5 h-5 text-blue-500" />
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">邮件报告推送</h2>
                </div>
                <div className="flex items-center justify-between">
                    <div>
                        <div className="text-sm text-slate-600 dark:text-slate-300">定时分析完成时自动发送报告到邮箱</div>
                        <div className="text-xs text-slate-400 dark:text-slate-500 mt-1">发送至 {user?.email || '-'}</div>
                    </div>
                    <button
                        type="button"
                        onClick={() => setEmailReportEnabled(!emailReportEnabled)}
                        disabled={configLoading}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                            emailReportEnabled ? 'bg-blue-500' : 'bg-slate-300 dark:bg-slate-600'
                        }`}
                    >
                        <span
                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                emailReportEnabled ? 'translate-x-6' : 'translate-x-1'
                            }`}
                        />
                    </button>
                </div>
                <div className="border-t border-slate-100 pt-3 dark:border-slate-800">
                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-2">
                        企业微信机器人 Webhook 地址
                    </label>
                    <div className="relative">
                        <Webhook className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                            type="text"
                            value={wecomWebhook}
                            onChange={e => setWecomWebhook(e.target.value)}
                            className="input w-full pl-10"
                            placeholder={
                                hasStoredWebhook
                                    ? '已保存，留空则保持不变'
                                    : '可选：粘贴完整 webhook 地址，例如 https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...'
                            }
                            disabled={configLoading}
                        />
                    </div>
                    <div className="mt-3 space-y-3">
                        {storedWebhookDisplay && (
                            <div className="rounded-xl border border-slate-200/80 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-700/80 dark:bg-slate-900/40 dark:text-slate-300">
                                当前已保存：<span className="font-mono break-all">{storedWebhookDisplay}</span>
                            </div>
                        )}

                        <div className="flex items-center justify-between rounded-xl border border-slate-200/80 bg-slate-50/80 px-3 py-3 dark:border-slate-700/80 dark:bg-slate-900/40">
                            <div>
                                <div className="text-sm text-slate-600 dark:text-slate-300">是否发送到 Webhook</div>
                                <div className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                                    定时分析完成后，按这个开关决定是否向企业微信机器人推送摘要。
                                </div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setWecomReportEnabled(!wecomReportEnabled)}
                                disabled={configLoading}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                    wecomReportEnabled ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'
                                }`}
                            >
                                <span
                                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                        wecomReportEnabled ? 'translate-x-6' : 'translate-x-1'
                                    }`}
                                />
                            </button>
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="text-xs text-slate-500 dark:text-slate-400">
                                支持直接填写完整地址，例如 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...`。测试发送优先使用当前输入，留空时会使用已保存的地址。
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                                <button
                                    type="button"
                                    onClick={handleWecomWarmup}
                                    disabled={configLoading || saving || modelSaving || saveAllSaving || wecomWarmingUp || (!wecomWebhook.trim() && !hasStoredWebhook)}
                                    className="btn-secondary inline-flex items-center gap-2"
                                >
                                    {wecomWarmingUp ? <Loader2 className="w-4 h-4 animate-spin" /> : <Flame className="w-4 h-4" />}
                                    {wecomWarmingUp ? '发送中...' : 'Webhook Warmup'}
                                </button>
                                {hasStoredWebhook && (
                                    <button
                                        type="button"
                                        onClick={handleClearWebhook}
                                        disabled={saving || modelSaving || saveAllSaving}
                                        className="inline-flex items-center gap-1 text-xs text-rose-500 hover:text-rose-600 disabled:opacity-50"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                        清除机器人
                                    </button>
                                )}
                            </div>
                        </div>

                        {wecomWarmupMessage && (
                            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300">
                                {wecomWarmupMessage}
                            </div>
                        )}

                        {wecomWarmupError && (
                            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-600 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300">
                                {wecomWarmupError}
                            </div>
                        )}

                        <div className="text-xs text-slate-500 dark:text-slate-400">
                            当前保存设置时会一起保存这个 webhook 和发送开关；为了安全，页面只展示脱敏后的已保存地址。
                        </div>
                    </div>
                </div>
            </div>

            <div className="card space-y-4">
                <div className="flex items-center gap-2">
                    <MessageSquare className="w-5 h-5 text-cyan-500" />
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">自定义分析提示</h2>
                </div>
                <div>
                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                        附加提示词
                    </label>
                    <textarea
                        value={customPrompt}
                        onChange={e => setCustomPrompt(e.target.value)}
                        className="input w-full min-h-[120px] resize-y"
                        placeholder="例如：更关注估值安全边际、政策催化与机构资金行为。"
                    />
                </div>
            </div>

            <div className="flex items-center gap-4">
                <button onClick={handleSaveAll} disabled={saveAllSaving || modelSaving || portfolioSyncing} className="btn-primary inline-flex items-center gap-2">
                    {saveAllSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    保存全部
                </button>
                {saved && <span className="text-sm text-green-600 dark:text-green-400">✓ {saveMessage}</span>}
            </div>
        </div>
    )
}
