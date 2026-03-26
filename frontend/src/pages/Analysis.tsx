import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AgentCollaboration from '@/components/AgentCollaboration'
import DebateDrawer from '@/components/DebateDrawer'
import ReportViewer from '@/components/ReportViewer'
import ChatCopilotPanel from '@/components/ChatCopilotPanel'
import KlinePanel from '@/components/KlinePanel'
import DecisionCard from '@/components/DecisionCard'
import RiskRadar from '@/components/RiskRadar'
import KeyMetrics from '@/components/KeyMetrics'
import { useAnalysisStore } from '@/stores/analysisStore'

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
        ? [/目标价[:：]\s*[¥$]?\s*([\d.]+)/, /目标价格[:：]\s*[¥$]?\s*([\d.]+)/, /target[:：]\s*[¥$]?\s*([\d.]+)/i]
        : [/止损价[:：]\s*[¥$]?\s*([\d.]+)/, /止损价格[:：]\s*[¥$]?\s*([\d.]+)/, /stop[-\s_]?loss[:：]\s*[¥$]?\s*([\d.]+)/i]
    for (const p of patterns) {
        const m = text.match(p)
        if (m) return parseFloat(m[1])
    }
    return undefined
}

export default function Analysis() {
    const [searchParams] = useSearchParams()
    const querySymbol = (searchParams.get('symbol') || '').trim().toUpperCase()
    const [activeSymbol, setActiveSymbol] = useState(() => querySymbol || useAnalysisStore.getState().currentSymbol || '000001.SH')
    const [activeSection, setActiveSection] = useState<string | undefined>()
    const [debateDrawer, setDebateDrawer] = useState<'research' | 'risk' | null>(null)
    const reportRef = useRef<HTMLDivElement | null>(null)
    const {
        report,
        currentSymbol,
        setCurrentSymbol,
        jobConfidence,
        jobTargetPrice,
        jobStopLoss,
        riskItems,
        keyMetrics,
    } = useAnalysisStore()

    const handleShowReport = (section?: string) => {
        setActiveSection(section)
        reportRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }

    const initialChatInput = querySymbol ? `分析 ${querySymbol} 今日走势` : undefined

    useEffect(() => {
        if (querySymbol) setActiveSymbol(querySymbol)
    }, [querySymbol])

    useEffect(() => {
        if (currentSymbol) {
            setActiveSymbol(currentSymbol)
        }
    }, [currentSymbol])

    const finalDecision = report?.final_trade_decision
    // Prefer LLM-extracted structured values, fall back to regex parsing
    const confidence = jobConfidence ?? extractConfidence(finalDecision)
    const targetPrice = jobTargetPrice ?? extractPrice(finalDecision, 'target')
    const stopLoss = jobStopLoss ?? extractPrice(finalDecision, 'stop')

    return (
        <div className="grid grid-cols-[340px_minmax(0,1fr)] gap-4 min-h-[calc(100vh-5rem)]">
            <aside className="h-[calc(100vh-5rem)] sticky top-0 flex flex-col gap-4">
                <div className="min-h-0 flex-1">
                    <ChatCopilotPanel
                        onSymbolDetected={(symbol) => {
                            setActiveSymbol(symbol)
                            setCurrentSymbol(symbol)
                        }}
                        onShowReport={handleShowReport}
                        initialInput={initialChatInput}
                    />
                </div>
            </aside>

            <div className="min-w-0 space-y-4">
                <div className="h-[360px]">
                    <KlinePanel
                        symbol={activeSymbol}
                        onSymbolChange={(symbol) => {
                            setActiveSymbol(symbol)
                        }}
                    />
                </div>

                <AgentCollaboration onSelectSection={handleShowReport} onOpenDebate={setDebateDrawer} selectedSection={activeSection} />

                <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                    <DecisionCard
                        symbol={activeSymbol}
                        report={report || undefined}
                        decision={mapDecision(report?.decision)}
                        direction={report?.direction}
                        confidence={confidence}
                        targetPrice={targetPrice}
                        stopLoss={stopLoss}
                        reasoning={finalDecision?.slice(0, 300)}
                    />
                    <RiskRadar items={riskItems} />
                    <KeyMetrics items={keyMetrics} />
                </div>

                <div ref={reportRef}>
                    <ReportViewer activeSection={activeSection} />
                </div>
            </div>

            <DebateDrawer debate={debateDrawer} onClose={() => setDebateDrawer(null)} />
        </div>
    )
}
