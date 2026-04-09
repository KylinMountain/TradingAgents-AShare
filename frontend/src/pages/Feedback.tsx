import { useState, useEffect } from 'react'
import { MessageSquarePlus, Send, Loader2, ChevronLeft, Clock, CheckCircle2, MessageCircle } from 'lucide-react'
import { api } from '@/services/api'
import type { FeedbackItem } from '@/types'

export default function Feedback() {
    const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [loading, setLoading] = useState(true)
    const [showForm, setShowForm] = useState(false)
    const [selectedFeedback, setSelectedFeedback] = useState<FeedbackItem | null>(null)
    const [subject, setSubject] = useState('')
    const [content, setContent] = useState('')
    const [submitting, setSubmitting] = useState(false)
    const pageSize = 10

    const loadFeedbacks = async (p = page) => {
        setLoading(true)
        try {
            const res = await api.listFeedbacks(p, pageSize)
            setFeedbacks(res.feedbacks)
            setTotal(res.total)
        } catch (e) {
            console.error('Failed to load feedbacks', e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { loadFeedbacks(page) }, [page])

    const [error, setError] = useState('')

    const handleSubmit = async () => {
        if (!subject.trim() || !content.trim()) return
        setSubmitting(true)
        setError('')
        try {
            await api.createFeedback(subject.trim(), content.trim())
            setSubject('')
            setContent('')
            setShowForm(false)
            setPage(1)
            await loadFeedbacks(1)
        } catch (e) {
            setError(e instanceof Error ? e.message : '提交失败，请稍后重试')
        } finally {
            setSubmitting(false)
        }
    }

    const openDetail = async (fb: FeedbackItem) => {
        setSelectedFeedback(fb)
        if (fb.admin_reply && !fb.is_read) {
            try {
                await api.markFeedbackRead(fb.id)
                setFeedbacks(prev => prev.map(f => f.id === fb.id ? { ...f, is_read: true } : f))
            } catch { /* ignore */ }
        }
    }

    const totalPages = Math.ceil(total / pageSize)

    const formatTime = (iso?: string) => {
        if (!iso) return ''
        const d = new Date(iso)
        return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    }

    // Detail view
    if (selectedFeedback) {
        const fb = selectedFeedback
        return (
            <div className="space-y-6">
                <button
                    onClick={() => setSelectedFeedback(null)}
                    className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
                >
                    <ChevronLeft className="w-4 h-4" /> 返回列表
                </button>

                <div className="card">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">{fb.subject}</h2>
                    <p className="text-xs text-slate-400 dark:text-slate-500 mb-4">{formatTime(fb.created_at)}</p>
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-900/40 p-4 mb-5">
                        <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{fb.content}</p>
                    </div>

                    {fb.admin_reply ? (
                        <div className="rounded-xl bg-blue-50 dark:bg-blue-950/30 p-4" style={{ borderLeft: '3px solid #3b82f6' }}>
                            <div className="flex items-center gap-1.5 mb-2">
                                <CheckCircle2 className="w-4 h-4 text-blue-500" />
                                <span className="text-xs font-medium text-blue-600 dark:text-blue-400">管理员回复</span>
                                <span className="text-xs text-slate-400 dark:text-slate-500 ml-auto">{formatTime(fb.replied_at ?? undefined)}</span>
                            </div>
                            <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{fb.admin_reply}</p>
                        </div>
                    ) : (
                        <div className="flex items-center gap-2 text-slate-400 dark:text-slate-500 text-sm py-3">
                            <Clock className="w-4 h-4" />
                            <span>等待回复中...</span>
                        </div>
                    )}
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">反馈留言</h1>
                    <p className="mt-1 text-slate-500 dark:text-slate-400">提交建议或问题，我们会尽快回复</p>
                </div>
                <button
                    onClick={() => setShowForm(!showForm)}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
                >
                    <MessageSquarePlus className="w-4 h-4" />
                    新建留言
                </button>
            </div>

            {/* New feedback form */}
            {showForm && (
                <div className="card">
                    <input
                        type="text"
                        placeholder="主题"
                        value={subject}
                        onChange={e => setSubject(e.target.value)}
                        maxLength={200}
                        className="input w-full mb-3"
                    />
                    <textarea
                        placeholder="请详细描述您的建议或遇到的问题..."
                        value={content}
                        onChange={e => setContent(e.target.value)}
                        maxLength={5000}
                        rows={5}
                        className="input w-full resize-none mb-3"
                    />
                    {error && (
                        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300 mb-3">
                            {error}
                        </div>
                    )}
                    <div className="flex justify-end gap-2">
                        <button
                            onClick={() => { setShowForm(false); setSubject(''); setContent('') }}
                            className="btn-secondary"
                        >
                            取消
                        </button>
                        <button
                            onClick={handleSubmit}
                            disabled={submitting || !subject.trim() || !content.trim()}
                            className="btn-primary flex items-center gap-2"
                        >
                            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            提交
                        </button>
                    </div>
                </div>
            )}

            {/* Feedback list */}
            <div className="card">
                {loading ? (
                    <div className="flex items-center justify-center py-16 text-slate-400 dark:text-slate-500">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" /> 加载中...
                    </div>
                ) : feedbacks.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 text-slate-400 dark:text-slate-500">
                        <MessageCircle className="w-10 h-10 mb-3 opacity-40" />
                        <p className="text-sm">暂无留言，点击"新建留言"开始反馈</p>
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100 dark:divide-slate-700/60">
                        {feedbacks.map(fb => (
                            <button
                                key={fb.id}
                                onClick={() => openDetail(fb)}
                                className="w-full text-left px-1 py-4 first:pt-0 last:pb-0 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors group"
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{fb.subject}</h3>
                                            {fb.admin_reply && !fb.is_read && (
                                                <span className="flex-shrink-0 px-1.5 py-0.5 rounded-full bg-blue-500 text-[10px] text-white font-medium">新回复</span>
                                            )}
                                        </div>
                                        <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-1">{fb.content}</p>
                                    </div>
                                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                                        <span className="text-[11px] text-slate-400 dark:text-slate-500">{formatTime(fb.created_at)}</span>
                                        {fb.admin_reply ? (
                                            <span className="flex items-center gap-1 text-[11px] text-green-600 dark:text-green-400">
                                                <CheckCircle2 className="w-3 h-3" /> 已回复
                                            </span>
                                        ) : (
                                            <span className="flex items-center gap-1 text-[11px] text-slate-400 dark:text-slate-500">
                                                <Clock className="w-3 h-3" /> 待回复
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                )}

                {/* Pagination */}
                {totalPages > 1 && (
                    <div className="flex items-center justify-center gap-2 mt-4 pt-4 border-t border-slate-100 dark:border-slate-700/60">
                        <button
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            disabled={page <= 1}
                            className="px-3 py-1.5 rounded-lg text-xs text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700/50 disabled:opacity-30 transition-colors"
                        >
                            上一页
                        </button>
                        <span className="text-xs text-slate-400 dark:text-slate-500 tabular-nums">{page} / {totalPages}</span>
                        <button
                            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                            className="px-3 py-1.5 rounded-lg text-xs text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700/50 disabled:opacity-30 transition-colors"
                        >
                            下一页
                        </button>
                    </div>
                )}
            </div>
        </div>
    )
}
