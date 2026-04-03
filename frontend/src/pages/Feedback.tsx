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
            <div className="max-w-3xl mx-auto">
                <button
                    onClick={() => setSelectedFeedback(null)}
                    className="flex items-center gap-1 text-slate-500 hover:text-slate-300 mb-4 text-sm transition-colors"
                >
                    <ChevronLeft className="w-4 h-4" /> 返回列表
                </button>

                <div className="bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200 dark:border-slate-700/60 p-6">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">{fb.subject}</h2>
                    <p className="text-xs text-slate-400 mb-4">{formatTime(fb.created_at)}</p>
                    <div className="bg-slate-50 dark:bg-slate-900/40 rounded-xl p-4 mb-4">
                        <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{fb.content}</p>
                    </div>

                    {fb.admin_reply ? (
                        <div className="border-l-3 border-blue-500 bg-blue-50 dark:bg-blue-950/30 rounded-xl p-4" style={{ borderLeft: '3px solid #3b82f6' }}>
                            <div className="flex items-center gap-1.5 mb-2">
                                <CheckCircle2 className="w-4 h-4 text-blue-500" />
                                <span className="text-xs font-medium text-blue-600 dark:text-blue-400">管理员回复</span>
                                <span className="text-xs text-slate-400 ml-auto">{formatTime(fb.replied_at)}</span>
                            </div>
                            <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{fb.admin_reply}</p>
                        </div>
                    ) : (
                        <div className="flex items-center gap-2 text-slate-400 text-sm py-3">
                            <Clock className="w-4 h-4" />
                            <span>等待回复中...</span>
                        </div>
                    )}
                </div>
            </div>
        )
    }

    return (
        <div className="max-w-3xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">反馈留言</h1>
                    <p className="text-sm text-slate-500 mt-1">提交建议或问题，我们会尽快回复并通过邮件通知您</p>
                </div>
                <button
                    onClick={() => setShowForm(!showForm)}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 text-white text-sm font-medium hover:shadow-lg hover:shadow-blue-500/25 transition-all"
                >
                    <MessageSquarePlus className="w-4 h-4" />
                    新建留言
                </button>
            </div>

            {/* New feedback form */}
            {showForm && (
                <div className="bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200 dark:border-slate-700/60 p-5 mb-6">
                    <input
                        type="text"
                        placeholder="主题"
                        value={subject}
                        onChange={e => setSubject(e.target.value)}
                        maxLength={200}
                        className="w-full px-4 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40 mb-3"
                    />
                    <textarea
                        placeholder="请详细描述您的建议或遇到的问题..."
                        value={content}
                        onChange={e => setContent(e.target.value)}
                        maxLength={5000}
                        rows={5}
                        className="w-full px-4 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40 resize-none mb-3"
                    />
                    {error && <p className="text-xs text-red-500 mb-2">{error}</p>}
                    <div className="flex justify-end gap-2">
                        <button
                            onClick={() => { setShowForm(false); setSubject(''); setContent('') }}
                            className="px-4 py-2 rounded-xl text-sm text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors"
                        >
                            取消
                        </button>
                        <button
                            onClick={handleSubmit}
                            disabled={submitting || !subject.trim() || !content.trim()}
                            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-blue-500 text-white text-sm font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            提交
                        </button>
                    </div>
                </div>
            )}

            {/* Feedback list */}
            {loading ? (
                <div className="flex items-center justify-center py-20 text-slate-400">
                    <Loader2 className="w-5 h-5 animate-spin mr-2" /> 加载中...
                </div>
            ) : feedbacks.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-400">
                    <MessageCircle className="w-10 h-10 mb-3 opacity-40" />
                    <p className="text-sm">暂无留言，点击"新建留言"开始反馈</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {feedbacks.map(fb => (
                        <button
                            key={fb.id}
                            onClick={() => openDetail(fb)}
                            className="w-full text-left bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200 dark:border-slate-700/60 p-4 hover:border-blue-500/40 hover:shadow-md transition-all group"
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{fb.subject}</h3>
                                        {fb.admin_reply && !fb.is_read && (
                                            <span className="flex-shrink-0 px-1.5 py-0.5 rounded-full bg-blue-500 text-[10px] text-white font-medium">新回复</span>
                                        )}
                                    </div>
                                    <p className="text-xs text-slate-500 line-clamp-1">{fb.content}</p>
                                </div>
                                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                                    <span className="text-[11px] text-slate-400">{formatTime(fb.created_at)}</span>
                                    {fb.admin_reply ? (
                                        <span className="flex items-center gap-1 text-[11px] text-green-500">
                                            <CheckCircle2 className="w-3 h-3" /> 已回复
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1 text-[11px] text-slate-400">
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
                <div className="flex items-center justify-center gap-2 mt-6">
                    <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page <= 1}
                        className="px-3 py-1.5 rounded-lg text-xs text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-30 transition-colors"
                    >
                        上一页
                    </button>
                    <span className="text-xs text-slate-400">{page} / {totalPages}</span>
                    <button
                        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                        disabled={page >= totalPages}
                        className="px-3 py-1.5 rounded-lg text-xs text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-30 transition-colors"
                    >
                        下一页
                    </button>
                </div>
            )}
        </div>
    )
}
