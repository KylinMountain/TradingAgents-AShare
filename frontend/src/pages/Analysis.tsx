import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loader2, Search } from 'lucide-react'
import DapanDianJin from '@/components/DapanDianJin'
import AnalysisConsole from '@/components/AnalysisConsole'
import DebateDrawer from '@/components/DebateDrawer'
import ReportViewer from '@/components/ReportViewer'
import KlinePanel from '@/components/KlinePanel'
import RadarPanel from '@/components/RadarPanel'
import PositionPanel from '@/components/PositionPanel'
import VolumeWashPanel from '@/components/VolumeWashPanel'
// import FundFlowPanel from '@/components/FundFlowPanel'
// import BollingerDeviationPanel from '@/components/BollingerDeviationPanel'
import DecisionCard from '@/components/DecisionCard'
import RiskRadar from '@/components/RiskRadar'
import KeyMetrics from '@/components/KeyMetrics'
import StrategyDecisionCard from '@/components/StrategyDecisionCard'
import BiasAnalysisPanel from '@/components/BiasAnalysisPanel'
import { api, getBaseUrl } from '@/services/api'
import { useAnalysisStore } from '@/stores/analysisStore'
import { useSyncedCharts } from '@/hooks/useSyncedCharts'
import type { StockSearchResult, YangYinHistoryPoint, GoldFingerPoint, RedGreenBgPoint } from '@/types'

function mapDecision(decision?: string): 'buy' | 'sell' | 'hold' | 'add' | 'reduce' | 'watch' | undefined {
    if (!decision) return undefined
    const d = decision.toUpperCase()
    if (d.includes('SELL') || d.includes('卖出')) return 'sell'
    if (d.includes('REDUCE') || d.includes('减持')) return 'reduce'
    if (d.includes('WATCH') || d.includes('观望')) return 'watch'
    if (d.includes('HOLD') || d.includes('持有')) return 'hold'
    if (d.includes('ADD') || d.includes('增持')) return 'add'
    if (d.includes('BUY') || d.includes('买入')) return 'buy'
    return undefined
}

function extractConfidence(text?: string): number | undefined {
    if (!text) return undefined
    const m = text.match(/置信度[:：]\s*(\d+)%/i) ?? text.match(/confidence[:：]\s*(\d+)%/i)
    if (m) {
        const v = parseInt(m[1])
        return v >= 0 && v <= 100 ? v : undefined
    }
    return undefined
}

function extractPrice(text: string | undefined, type: 'target' | 'stop'): number | undefined {
    if (!text) return undefined
    const patterns = type === 'target'
        ? [/目标[^：:\n]{0,30}[:：]\s*[¥$]?\s*([\d.]+)/, /target[^：:\n]{0,30}[:：]\s*[¥$]?\s*([\d.]+)/i, /downside\s+target[^：:\n]{0,15}[:：]\s*[¥$]?\s*([\d.]+)/i, /upside\s+target[^：:\n]{0,15}[:：]\s*[¥$]?\s*([\d.]+)/i, /price\s+target[^：:\n]{0,15}[:：]\s*[¥$]?\s*([\d.]+)/i, /price\s+objective[^：:\n]{0,15}[:：]\s*[¥$]?\s*([\d.]+)/i, /support\s+level[^：:\n]{0,10}[:：]\s*[¥$]?\s*([\d.]+)/i, /resistance\s+level[^：:\n]{0,10}[:：]\s*[¥$]?\s*([\d.]+)/i, /下[行看跌][^：:\n]{0,30}[:：]\s*[¥$]?\s*([\d.]+)/, /看[空跌][^：:\n]{0,30}[:：]\s*[¥$]?\s*([\d.]+)/, /阻力位[^：:\n]{0,20}[:：]\s*[¥$]?\s*([\d.]+)/]
        : [/止损[^：:\n]{0,30}[:：]\s*[¥$]?\s*([\d.]+)/, /stop[-\s_]?loss[^：:\n]{0,30}[:：]\s*[¥$]?\s*([\d.]+)/i]
    for (const p of patterns) {
        const m = text.match(p)
        if (m) return parseFloat(m[1])
    }
    return undefined
}

function extractEntryRange(text: string | undefined): string | undefined {
    if (!text) return undefined
    const m = text.match(/\*{0,4}(?:入场|建仓|买入|卖出)区间\*{0,4}\s*[：:]\s*[¥$]?\s*([\d.]+)\s*(?:元)?\s*[–\-—至~]\s*[¥$]?\s*([\d.]+)\s*(?:元)?/)
        ?? text.match(/\*{0,4}(?:入场|建仓|买入|卖出)区间\*{0,4}[：:\s]*[¥$]?\s*([\d.]+)\s*(?:元)?\s*[–\-—至~]\s*[¥$]?\s*([\d.]+)\s*(?:元)?/)
    if (m) return `${m[1]} - ${m[2]}`
    return undefined
}

export default function Analysis() {
    const { registerKlineChart, registerSubChart, syncNow } = useSyncedCharts()
    const [searchParams] = useSearchParams()
    const querySymbol = (searchParams.get('symbol') || '').trim().toUpperCase()
    const [activeSymbol, setActiveSymbol] = useState(() => querySymbol || useAnalysisStore.getState().currentSymbol || '000001.SH')
    const [activeSection, setActiveSection] = useState<string | undefined>()
    const [debateDrawer, setDebateDrawer] = useState<'research' | 'risk' | null>(null)
    const reportRef = useRef<HTMLDivElement | null>(null)

    // 标的搜索
    const [symbolSearch, setSymbolSearch] = useState('')
    const [symbolResults, setSymbolResults] = useState<StockSearchResult[]>([])
    const [symbolSearching, setSymbolSearching] = useState(false)
    const [showSymbolDropdown, setShowSymbolDropdown] = useState(false)
    const [yangYinHistory, setYangYinHistory] = useState<YangYinHistoryPoint[]>([])
    const [goldFingerHistory, setGoldFingerHistory] = useState<GoldFingerPoint[]>([])
    const [redGreenBgHistory, setRedGreenBgHistory] = useState<RedGreenBgPoint[]>([])
    const [symbolError, setSymbolError] = useState('')
    const [decisionDisplayName, setDecisionDisplayName] = useState('')
    const symbolTimerRef = useRef<ReturnType<typeof setTimeout>>()
    const symbolContainerRef = useRef<HTMLDivElement>(null)

    // 防抖搜索
    useEffect(() => {
        if (symbolTimerRef.current) clearTimeout(symbolTimerRef.current)
        const q = symbolSearch.trim()
        if (!q) { setSymbolResults([]); setShowSymbolDropdown(false); setSymbolSearching(false); return }
        setSymbolSearching(true)
        symbolTimerRef.current = setTimeout(async () => {
            try {
                const res = await api.searchStocks(q)
                setSymbolResults(res.results)
                setShowSymbolDropdown(true)
            } catch { setShowSymbolDropdown(false) }
            setSymbolSearching(false)
        }, 300)
    }, [symbolSearch])

    useEffect(() => {
        let retried = false
        const refresh = () => {
            let needRebuild = false
            const fetches = [
                api.getYangYinHistory(30).then(data => {
                    if (!data || data.length < 2) needRebuild = true
                    setYangYinHistory(prev => {
                        if (!prev || prev.length === 0) return data
                        const prevLast = prev[prev.length - 1]
                        const newLast = data[data.length - 1]
                        if (prevLast?.trade_date !== newLast?.trade_date || prevLast?.yang_pct !== newLast?.yang_pct) {
                            return data
                        }
                        return prev
                    })
                }).catch(() => {}),
                api.getGoldFingerHistory(30).then(data => {
                    if (!data || data.length < 2) needRebuild = true
                    setGoldFingerHistory(prev => {
                        if (!prev || prev.length === 0) return data
                        const prevLast = prev[prev.length - 1]
                        const newLast = data[data.length - 1]
                        if (prevLast?.trade_date !== newLast?.trade_date || prevLast?.signal !== newLast?.signal) {
                            return data
                        }
                        return prev
                    })
                }).catch(() => {}),
                api.getRedGreenBgHistory(30).then(data => {
                    if (!data || data.length < 2) needRebuild = true
                    setRedGreenBgHistory(prev => {
                        if (!prev || prev.length === 0) return data
                        const prevLast = prev[prev.length - 1]
                        const newLast = data[data.length - 1]
                        if (prevLast?.trade_date !== newLast?.trade_date || prevLast?.background !== newLast?.background) {
                            return data
                        }
                        return prev
                    })
                }).catch(() => {}),
            ]
            Promise.all(fetches).then(() => {
                if (needRebuild && !retried) {
                    retried = true
                    api.ensureYangYinData().then(() => {
                        setTimeout(refresh, 3000)
                    }).catch(() => {})
                }
            })
        }
        refresh()
        const es = new EventSource(`${getBaseUrl()}/v1/dapan-dianjin/events`)
        es.addEventListener('scan_completed', () => refresh())
        return () => es.close()
    }, [])

    // 点击外部关闭下拉
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (symbolContainerRef.current && !symbolContainerRef.current.contains(e.target as Node)) {
                setShowSymbolDropdown(false)
            }
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [])
    const {
        report,
        currentSymbol,
        jobConfidence,
        jobTargetPrice,
        jobStopLoss,
        riskItems,
        keyMetrics,
    } = useAnalysisStore()

    const decisionSymbol = report?.symbol || activeSymbol

    useEffect(() => {
        let cancelled = false
        const lookup = async () => {
            const code = decisionSymbol.split('.')[0]
            if (!code) return
            try {
                const res = await api.searchStocks(code)
                if (cancelled) return
                const match = res.results.find(r => r.symbol === decisionSymbol)
                if (match) setDecisionDisplayName(match.name)
            } catch {}
        }
        lookup()
        return () => { cancelled = true }
    }, [decisionSymbol])

    const handleShowReport = (section?: string) => {
        setActiveSection(section)
        reportRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }

    useEffect(() => {
        if (querySymbol) setActiveSymbol(querySymbol)
    }, [querySymbol])

    useEffect(() => {
        if (currentSymbol) {
            setActiveSymbol(currentSymbol)
        }
    }, [currentSymbol])

    const finalDecision = report?.final_trade_decision
    const confidence = jobConfidence ?? extractConfidence(finalDecision)
    const targetPrice = jobTargetPrice ?? extractPrice(finalDecision, 'target')
    const stopLoss = jobStopLoss ?? extractPrice(finalDecision, 'stop')
    const entryRange = extractEntryRange(report?.trader_investment_plan) ?? extractEntryRange(report?.investment_plan)

    return (
        <div className="space-y-4 max-w-[1400px] mx-auto max-sm:space-y-2 max-sm:px-1">
            {/* 大盘点金 -- always shown */}
            <DapanDianJin history={yangYinHistory} goldFingerHistory={goldFingerHistory} redGreenBgHistory={redGreenBgHistory} />

            {/* 标的搜索栏 */}
            <div ref={symbolContainerRef} className="relative">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                        type="text"
                        value={symbolSearch}
                        onChange={e => { setSymbolSearch(e.target.value); setSymbolError('') }}
                        onFocus={() => symbolResults.length > 0 && setShowSymbolDropdown(true)}
                        onKeyDown={e => {
                            if (e.key === 'Enter' && symbolSearch.trim()) {
                                const q = symbolSearch.trim().toUpperCase()
                                const matched = symbolResults.find(r =>
                                    r.symbol.replace(/\.(SH|SZ|BJ)$/i, '') === q.replace(/\.(SH|SZ|BJ)$/i, '') ||
                                    r.name === q
                                )
                                if (matched) {
                                    setActiveSymbol(matched.symbol)
                                    setSymbolSearch('')
                                    setShowSymbolDropdown(false)
                                } else {
                                    setSymbolError('未找到匹配的股票，请检查代码或名称')
                                }
                            }
                        }}
                        placeholder="搜索股票代码或名称，切换K线视图"
                        className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-10 text-sm text-slate-700 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:placeholder:text-slate-500"
                    />
                    {symbolSearching && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-slate-400" />}
                </div>
                {symbolError && (
                    <p className="mt-1 text-xs text-red-500">{symbolError}</p>
                )}
                {showSymbolDropdown && symbolResults.length > 0 && (
                    <div className="absolute z-50 left-0 right-0 mt-1 rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800 max-h-60 overflow-y-auto">
                        {symbolResults.map(r => (
                            <button
                                key={r.symbol}
                                type="button"
                                onClick={() => {
                                    setActiveSymbol(r.symbol)
                                    setSymbolSearch('')
                                    setShowSymbolDropdown(false)
                                }}
                                className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                            >
                                <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{r.name}</span>
                                <span className="text-xs text-slate-400">{r.symbol}</span>
                            </button>
                        ))}
                    </div>
                )}
            </div>

            <div className="h-[360px] max-sm:h-[300px]">
                <KlinePanel
                    symbol={activeSymbol}
                    onSymbolChange={(symbol) => {
                        setActiveSymbol(symbol)
                    }}
                    onChartReady={registerKlineChart}
                    onSyncNow={syncNow}
                />
            </div>

            <RadarPanel symbol={activeSymbol} onChartReady={(c) => registerSubChart('radar', c)} onSyncNow={syncNow} />

            <VolumeWashPanel symbol={activeSymbol} onChartReady={(c) => registerSubChart('volumeWash', c)} onSyncNow={syncNow} />

            {/* <FundFlowPanel symbol={activeSymbol} onChartReady={(c) => registerSubChart('fundFlow', c)} onSyncNow={syncNow} /> */}

            <PositionPanel symbol={activeSymbol} onChartReady={(c) => registerSubChart('position', c)} onSyncNow={syncNow} />

            {/* <BollingerDeviationPanel symbol={activeSymbol} onChartReady={(c) => registerSubChart('bollingerDeviation', c)} onSyncNow={syncNow} /> */}

            <AnalysisConsole
                symbol={activeSymbol}
                onShowReport={handleShowReport}
                onOpenDebate={setDebateDrawer}
                selectedSection={activeSection}
            />

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                <DecisionCard
                    symbol={decisionSymbol}
                    name={decisionDisplayName || undefined}
                    report={report || undefined}
                    decision={mapDecision(report?.decision)}
                    direction={report?.direction}
                    confidence={confidence}
                    targetPrice={targetPrice}
                    stopLoss={stopLoss}
                    entryRange={entryRange}
                    reasoning={finalDecision?.slice(0, 300)}
                />
                <RiskRadar items={riskItems} />
                <KeyMetrics items={keyMetrics} />
            </div>

            <div ref={reportRef}>
                <ReportViewer activeSection={activeSection} />
            </div>

            <StrategyDecisionCard
                symbol={activeSymbol}
                name={decisionDisplayName || undefined}
            />

            <BiasAnalysisPanel
                symbol={activeSymbol}
                name={decisionDisplayName || undefined}
            />

            <DebateDrawer debate={debateDrawer} onClose={() => setDebateDrawer(null)} />
        </div>
    )
}
