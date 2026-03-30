import { FileText, Download, ChevronDown, ChevronRight, Loader2, MousePointerClick } from 'lucide-react'
import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAnalysisStore } from '@/stores/analysisStore'
import type { ReportDetail } from '@/types'
import { sanitizeReportMarkdown } from '@/utils/reportText'

const REPORT_SECTIONS = [
    { key: 'market_report', title: '市场分析报告', team: '分析团队' },
    { key: 'sentiment_report', title: '舆情分析报告', team: '分析团队' },
    { key: 'news_report', title: '新闻分析报告', team: '分析团队' },
    { key: 'fundamentals_report', title: '基本面分析报告', team: '分析团队' },
    { key: 'macro_report', title: '宏观板块报告', team: '分析团队' },
    { key: 'smart_money_report', title: '主力资金报告', team: '分析团队' },
    { key: 'investment_plan', title: '研究团队决策', team: '研究团队' },
    { key: 'trader_investment_plan', title: '交易团队计划', team: '交易团队' },
    { key: 'final_trade_decision', title: '最终交易决策', team: '组合管理' },
]

const REPORT_DISCLAIMER =
    '> 免责声明：以上内容由模型基于公开数据、历史信息与预设规则自动生成，仅供研究参考，不构成任何投资建议、收益承诺或实际交易指令。'

const MD_COMPONENTS = {
    table: ({ children }: { children?: React.ReactNode }) => (
        <table className="w-full border-collapse border border-slate-300 dark:border-slate-600 my-4">{children}</table>
    ),
    thead: ({ children }: { children?: React.ReactNode }) => (
        <thead className="bg-slate-100 dark:bg-slate-700">{children}</thead>
    ),
    th: ({ children }: { children?: React.ReactNode }) => (
        <th className="border border-slate-300 dark:border-slate-600 px-3 py-2 text-left font-semibold text-slate-700 dark:text-slate-300">{children}</th>
    ),
    td: ({ children }: { children?: React.ReactNode }) => (
        <td className="border border-slate-300 dark:border-slate-600 px-3 py-2 text-slate-600 dark:text-slate-400">{children}</td>
    ),
    tr: ({ children }: { children?: React.ReactNode }) => (
        <tr className="even:bg-slate-50 dark:even:bg-slate-800/50">{children}</tr>
    ),
}

interface ReportViewerProps {
    /** 传入后进入历史报告模式，不读取 store */
    reportData?: ReportDetail
    /** 当前选中章节（实时模式：点哪个智能体就显示哪个） */
    activeSection?: string
}

export default function ReportViewer({ reportData, activeSection }: ReportViewerProps = {}) {
    const { report, streamingSections, isAnalyzing } = useAnalysisStore()
    const [expandedSections, setExpandedSections] = useState<string[]>([])
    const isHistorical = !!reportData

    const getSectionContent = (key: string): string => {
        if (isHistorical) {
            return sanitizeReportMarkdown((reportData?.[key as keyof ReportDetail] as string | undefined) || '')
        }
        const s = streamingSections[key]
        return sanitizeReportMarkdown(s?.displayed || (report?.[key as keyof typeof report] as string | undefined) || '')
    }

    const getSectionState = (key: string) => {
        if (isHistorical) return { isStreaming: false, isComplete: true }
        const s = streamingSections[key]
        return {
            isStreaming: s?.isTyping || false,
            isComplete: s?.isComplete || !!(report?.[key as keyof typeof report]),
        }
    }

    const hasAnyContent = isHistorical
        ? REPORT_SECTIONS.some(s => !!reportData?.[s.key as keyof ReportDetail])
        : Object.keys(streamingSections).length > 0 || (report && Object.values(report).some(v => typeof v === 'string' && v.length > 0))

    // ── Historical mode: auto-expand first 2 sections with content ────────────
    useEffect(() => {
        if (!isHistorical) return
        const withContent = REPORT_SECTIONS
            .filter(s => !!reportData?.[s.key as keyof ReportDetail])
            .map(s => s.key)
        setExpandedSections(withContent.slice(0, 2))
    }, [isHistorical, reportData])

    // Historical mode: accordion toggle
    const toggleSection = (key: string) =>
        setExpandedSections(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key])

    const handleExport = () => {
        const source = isHistorical ? reportData : report
        if (!source) return
        const text = REPORT_SECTIONS
            .filter(s => source[s.key as keyof typeof source])
            .map(s => `## ${s.title}\n\n${source[s.key as keyof typeof source]}`)
            .join('\n\n---\n\n') + `\n\n---\n\n${REPORT_DISCLAIMER}\n`
        const blob = new Blob([text], { type: 'text/markdown' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `analysis-${isHistorical ? reportData?.symbol : report?.symbol || 'report'}.md`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
    }

    // ── Historical mode: full accordion ──────────────────────────────────────
    if (isHistorical) {
        if (!hasAnyContent) {
            return (
                <div className="flex items-center justify-center py-12">
                    <div className="text-center">
                        <FileText className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-4" />
                        <p className="text-slate-500 dark:text-slate-400">暂无分析报告</p>
                    </div>
                </div>
            )
        }
        return (
            <div className="space-y-2">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <FileText className="w-5 h-5 text-blue-500" />
                        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">分析报告</h2>
                    </div>
                    <button onClick={handleExport} className="btn-secondary flex items-center gap-2 text-sm py-1.5 px-3">
                        <Download className="w-4 h-4" />
                        导出
                    </button>
                </div>
                <div className="space-y-3">
                    {REPORT_SECTIONS.map((section) => {
                        const content = getSectionContent(section.key)
                        if (!content) return null
                        const isExpanded = expandedSections.includes(section.key)
                        return (
                            <div key={section.key} className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden bg-white dark:bg-slate-900/40">
                                <button
                                    onClick={() => toggleSection(section.key)}
                                    className="w-full flex items-center justify-between p-4 bg-slate-50/90 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                                >
                                    <div className="flex items-center gap-2">
                                        {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                                        <span className="font-medium text-slate-900 dark:text-slate-100">{section.title}</span>
                                        <span className="text-xs text-slate-500 dark:text-slate-400">{section.team}</span>
                                    </div>
                                    <span className="text-xs text-green-500">✓</span>
                                </button>
                                {isExpanded && (
                                    <div className="p-5 bg-white dark:bg-slate-800/30">
                                        <div className="prose dark:prose-invert prose-sm md:prose-base max-w-none">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>{content}</ReactMarkdown>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )
                    })}
                    <div className="rounded-2xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-xs leading-6 text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{REPORT_DISCLAIMER}</ReactMarkdown>
                    </div>
                </div>
            </div>
        )
    }

    // ── Live mode: single-section viewer ─────────────────────────────────────
    const activeMeta = activeSection ? REPORT_SECTIONS.find(s => s.key === activeSection) : null
    const activeContent = activeSection ? getSectionContent(activeSection) : ''
    const { isStreaming: activeStreaming } = activeSection ? getSectionState(activeSection) : { isStreaming: false }

    return (
        <div className="card flex-1 flex flex-col min-h-0 ring-1 ring-slate-200/70 dark:ring-slate-800 shadow-[0_16px_40px_rgba(15,23,42,0.06)] dark:shadow-none">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-blue-500" />
                    <div>
                        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                            {activeMeta ? activeMeta.title : '分析报告'}
                        </h2>
                        {activeMeta ? (
                            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                                {activeMeta.team} · 点击其他智能体切换报告
                            </p>
                        ) : (
                            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                                点击上方智能体卡片查看完整报告
                            </p>
                        )}
                    </div>
                    {isAnalyzing && (
                        <span className="badge-orange animate-pulse">生成中</span>
                    )}
                </div>
                {hasAnyContent && (
                    <button onClick={handleExport} className="btn-secondary flex items-center gap-2 text-sm py-1.5 px-3">
                        <Download className="w-4 h-4" />
                        导出全部
                    </button>
                )}
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto min-h-0">
                {!activeMeta ? (
                    /* Empty state */
                    <div className="flex flex-col items-center justify-center py-16 gap-3">
                        <MousePointerClick className="w-10 h-10 text-slate-300 dark:text-slate-600" />
                        <p className="text-sm font-medium text-slate-400 dark:text-slate-500">
                            点击上方智能体卡片查看报告
                        </p>
                        {isAnalyzing && !hasAnyContent && (
                            <div className="flex items-center gap-1.5 mt-1 text-xs text-slate-400 dark:text-slate-500">
                                <Loader2 className="w-3 h-3 animate-spin" />
                                等待首个章节输出...
                            </div>
                        )}
                    </div>
                ) : (
                    /* Single section content */
                    <div className="space-y-4">
                        <div className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden bg-white dark:bg-slate-900/40">
                            <div className="p-5 bg-white dark:bg-slate-800/30">
                                {activeContent ? (
                                    <div className="prose dark:prose-invert prose-sm md:prose-base max-w-none">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                                            {activeContent}
                                        </ReactMarkdown>
                                        {activeStreaming && (
                                            <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1" />
                                        )}
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center py-10 text-slate-400 dark:text-slate-500">
                                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                        正在生成报告...
                                    </div>
                                )}
                            </div>
                        </div>

                        {activeContent && (
                            <div className="rounded-2xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-xs leading-6 text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{REPORT_DISCLAIMER}</ReactMarkdown>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}
