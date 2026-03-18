import React, { useMemo } from 'react'
import { useAnalysisStore } from '@/stores/analysisStore'
import { Swords, TrendingUp, TrendingDown, Target, Zap, ShieldAlert } from 'lucide-react'

export default function GameTheoryDebateArena() {
    const { report } = useAnalysisStore()
    
    // Extract GT Debate State from the report metadata if available, 
    // or parse from game_theory_report. 
    // In our backend implementation, GameTheoryDebateState is part of AgentState.
    // We assume the API has been updated to include it in the response.
    const gtState = (report as any)?.game_theory_debate_state
    const signals = (report as any)?.game_theory_signals

    if (!gtState || !gtState.history) {
        return null
    }

    const historyLines = gtState.history.split('\n').filter(Boolean)

    return (
        <div className="mt-8 border-2 border-rose-500/20 rounded-2xl bg-rose-50/10 dark:bg-rose-950/5 overflow-hidden">
            {/* Arena Header */}
            <div className="bg-rose-500 text-white px-6 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Swords className="w-6 h-6 animate-pulse" />
                    <h4 className="font-black tracking-tighter uppercase text-lg">筹码博弈演武场 (Game Theory Arena)</h4>
                </div>
                <div className="flex items-center gap-4 text-xs font-bold uppercase tracking-widest opacity-80">
                    <span>Round {gtState.count}</span>
                    <span className="w-1 h-1 bg-white rounded-full" />
                    <span>{gtState.round_goal}</span>
                </div>
            </div>

            <div className="p-6">
                {/* Board / Context */}
                <div className="mb-8 grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-white dark:bg-slate-800 p-4 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                        <div className="flex items-center gap-2 mb-2 text-rose-600 dark:text-rose-400">
                            <Target className="w-4 h-4" />
                            <span className="text-[10px] font-black uppercase tracking-widest">当前局面</span>
                        </div>
                        <p className="text-sm font-bold text-slate-900 dark:text-slate-100">{signals?.board || '博弈博弈中...'}</p>
                    </div>
                    <div className="bg-white dark:bg-slate-800 p-4 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                        <div className="flex items-center gap-2 mb-2 text-blue-600 dark:text-blue-400">
                            <Zap className="w-4 h-4" />
                            <span className="text-[10px] font-black uppercase tracking-widest">博弈重心</span>
                        </div>
                        <p className="text-sm font-bold text-slate-900 dark:text-slate-100">{gtState.round_summary || '寻找预期差...'}</p>
                    </div>
                    <div className="bg-white dark:bg-slate-800 p-4 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                        <div className="flex items-center gap-2 mb-2 text-amber-600 dark:text-amber-400">
                            <ShieldAlert className="w-4 h-4" />
                            <span className="text-[10px] font-black uppercase tracking-widest">反共识信号</span>
                        </div>
                        <p className="text-sm font-black text-amber-600 dark:text-amber-400 uppercase tracking-tighter">
                            {signals?.counter_consensus_signal || '计算中...'}
                        </p>
                    </div>
                </div>

                {/* Debate Flow */}
                <div className="space-y-6 relative">
                    <div className="absolute left-1/2 top-0 bottom-0 w-[2px] bg-slate-100 dark:bg-slate-800 hidden md:block" />
                    
                    {historyLines.map((line: string, idx: number) => {
                        const isSmartMoney = line.startsWith('Smart Money')
                        const [speaker, ...contentParts] = line.split(': ')
                        const content = contentParts.join(': ')

                        return (
                            <div key={idx} className={`flex w-full ${isSmartMoney ? 'justify-start' : 'justify-end'}`}>
                                <div className={`relative max-w-[85%] md:max-w-[45%] p-4 rounded-2xl shadow-sm border ${
                                    isSmartMoney 
                                    ? 'bg-amber-50 border-amber-200 dark:bg-amber-900/10 dark:border-amber-500/30' 
                                    : 'bg-orange-50 border-orange-200 dark:bg-orange-900/10 dark:border-orange-500/30 text-right'
                                }`}>
                                    <div className={`flex items-center gap-2 mb-2 ${isSmartMoney ? 'flex-row' : 'flex-row-reverse'}`}>
                                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black ${
                                            isSmartMoney ? 'bg-amber-500 text-white' : 'bg-orange-500 text-white'
                                        }`}>
                                            {isSmartMoney ? '主' : '散'}
                                        </div>
                                        <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">
                                            {isSmartMoney ? '主力机构' : '散户群体'}
                                        </span>
                                    </div>
                                    <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300 italic font-medium">
                                        "{content}"
                                    </p>
                                    
                                    {/* Indicator arrows */}
                                    <div className={`absolute top-1/2 -translate-y-1/2 w-4 h-4 ${
                                        isSmartMoney ? '-right-2' : '-left-2'
                                    } hidden md:block`}>
                                        {isSmartMoney ? <TrendingUp className="text-amber-500/40" /> : <TrendingDown className="text-orange-500/40" />}
                                    </div>
                                </div>
                            </div>
                        )
                    })}
                </div>

                {/* Claims Grid */}
                {gtState.claims && gtState.claims.length > 0 && (
                    <div className="mt-10 pt-8 border-t border-slate-100 dark:border-slate-800">
                        <h5 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 mb-6 text-center">博弈关键 Claim 追踪</h5>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {gtState.claims.map((claim: any, idx: number) => (
                                <div key={idx} className="group p-3 rounded-xl border border-slate-100 dark:border-slate-800 hover:border-rose-500/30 transition-all duration-300">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-[9px] font-black px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded text-slate-500">
                                            {claim.claim_id}
                                        </span>
                                        <span className={`text-[9px] font-bold uppercase ${
                                            claim.status === 'resolved' ? 'text-emerald-500' : 'text-rose-500'
                                        }`}>
                                            {claim.status}
                                        </span>
                                    </div>
                                    <p className="text-[12px] font-bold text-slate-800 dark:text-slate-200 line-clamp-2 leading-snug">
                                        {claim.claim}
                                    </p>
                                    <div className="mt-2 flex flex-wrap gap-1">
                                        {claim.evidence?.slice(0, 2).map((ev: string, ei: number) => (
                                            <span key={ei} className="text-[8px] bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded italic">
                                                #{ev}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
