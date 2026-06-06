import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'

interface AdminUser {
    id: string
    email: string
    is_active: boolean
    is_admin: boolean
    is_banned: boolean
    ban_reason?: string
    created_at?: string
    last_login_at?: string
    last_login_ip?: string
}

interface QueryLog {
    id: string
    user_id: string
    email?: string
    query_text?: string
    symbol?: string
    created_at?: string
}

export default function Admin() {
    const user = useAuthStore(s => s.user)
    const navigate = useNavigate()
    const [users, setUsers] = useState<AdminUser[]>([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [showAddModal, setShowAddModal] = useState(false)
    const [newEmail, setNewEmail] = useState('')
    const [newIsAdmin, setNewIsAdmin] = useState(false)
    const [adding, setAdding] = useState(false)
    const [logs, setLogs] = useState<QueryLog[]>([])
    const [logsTotal, setLogsTotal] = useState(0)
    const [logsLoading, setLogsLoading] = useState(true)

    useEffect(() => {
        if (!user) return
        loadUsers()
        loadLogs()
    }, [user])

    const loadUsers = async () => {
        setLoading(true)
        setError('')
        try {
            const resp = await api.get<{ users: AdminUser[]; total: number }>('/v1/admin/users?limit=200')
            setUsers(resp.users)
            setTotal(resp.total)
        } catch (e: any) {
            if (e?.response?.status === 403) {
                setError('你没有管理员权限')
            } else {
                setError('加载失败')
            }
        } finally {
            setLoading(false)
        }
    }

    const loadLogs = async () => {
        setLogsLoading(true)
        try {
            const resp = await api.get<{ logs: QueryLog[]; total: number }>('/v1/admin/query-logs?limit=100')
            setLogs(resp.logs)
            setLogsTotal(resp.total)
        } catch {
            // ignore
        } finally {
            setLogsLoading(false)
        }
    }

    const handleBan = async (userId: string) => {
        const reason = prompt('请输入封禁原因（可选）:')
        try {
            await api.post(`/v1/admin/users/${userId}/ban`, { reason: reason || undefined })
            loadUsers()
        } catch {
            alert('操作失败')
        }
    }

    const handleUnban = async (userId: string) => {
        try {
            await api.post(`/v1/admin/users/${userId}/unban`)
            loadUsers()
        } catch {
            alert('操作失败')
        }
    }

    const handleDelete = async (userId: string, email: string) => {
        if (!confirm(`确定要删除用户 ${email} 吗？此操作不可恢复！`)) return
        try {
            await api.delete(`/v1/admin/users/${userId}`)
            loadUsers()
        } catch {
            alert('操作失败')
        }
    }

    const handleSetAdmin = async (userId: string) => {
        try {
            await api.post(`/v1/admin/users/${userId}/set-admin`)
            loadUsers()
        } catch {
            alert('操作失败')
        }
    }

    const handleRevokeAdmin = async (userId: string) => {
        try {
            await api.post(`/v1/admin/users/${userId}/revoke-admin`)
            loadUsers()
        } catch {
            alert('操作失败')
        }
    }

    const handleAddUser = async () => {
        if (!newEmail.trim()) return
        setAdding(true)
        try {
            await api.post('/v1/admin/users', { email: newEmail.trim(), is_admin: newIsAdmin })
            setShowAddModal(false)
            setNewEmail('')
            setNewIsAdmin(false)
            loadUsers()
        } catch (e: any) {
            alert(e?.message || '添加失败')
        } finally {
            setAdding(false)
        }
    }

    if (error) {
        return (
            <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
                <div className="text-center">
                    <p className="text-red-500 text-lg mb-4">{error}</p>
                    <button onClick={() => navigate('/')} className="text-blue-500 hover:underline">返回首页</button>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 p-6">
            <div className="max-w-6xl mx-auto">
                <div className="flex items-center justify-between mb-6">
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">用户管理</h1>
                    <div className="flex items-center gap-3">
                        <span className="text-sm text-slate-500">共 {total} 个用户</span>
                        <button onClick={() => setShowAddModal(true)} className="px-3 py-1.5 text-sm rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors">添加授权邮箱</button>
                    </div>
                </div>

                {loading ? (
                    <div className="text-center py-20 text-slate-400">加载中...</div>
                ) : (
                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                                    <th className="text-left px-4 py-3 text-slate-500 font-medium">邮箱</th>
                                    <th className="text-left px-4 py-3 text-slate-500 font-medium">角色</th>
                                    <th className="text-left px-4 py-3 text-slate-500 font-medium">状态</th>
                                    <th className="text-left px-4 py-3 text-slate-500 font-medium">注册时间</th>
                                    <th className="text-left px-4 py-3 text-slate-500 font-medium">最后登录</th>
                                    <th className="text-right px-4 py-3 text-slate-500 font-medium">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map(u => (
                                    <tr key={u.id} className="border-b border-slate-100 dark:border-slate-800 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/30">
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-2">
                                                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 text-white flex items-center justify-center text-xs font-bold">
                                                    {u.email[0].toUpperCase()}
                                                </div>
                                                <span className="text-slate-900 dark:text-white font-medium">{u.email}</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3">
                                            {u.is_admin ? (
                                                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">管理员</span>
                                            ) : (
                                                <span className="text-slate-400">普通用户</span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3">
                                            {u.is_banned ? (
                                                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" title={u.ban_reason || ''}>已封禁</span>
                                            ) : (
                                                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">正常</span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3 text-slate-500">
                                            {u.created_at ? new Date(u.created_at).toLocaleDateString('zh-CN') : '-'}
                                        </td>
                                        <td className="px-4 py-3 text-slate-500">
                                            {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString('zh-CN') : '未登录'}
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                {u.id === user?.id ? (
                                                    <span className="text-xs text-slate-400">当前用户</span>
                                                ) : (
                                                    <>
                                                        {u.is_banned ? (
                                                            <button onClick={() => handleUnban(u.id)} className="px-2 py-1 text-xs rounded-lg bg-green-50 text-green-600 hover:bg-green-100 dark:bg-green-900/20 dark:text-green-400">解封</button>
                                                        ) : (
                                                            <button onClick={() => handleBan(u.id)} className="px-2 py-1 text-xs rounded-lg bg-orange-50 text-orange-600 hover:bg-orange-100 dark:bg-orange-900/20 dark:text-orange-400">封禁</button>
                                                        )}
                                                        {u.is_admin ? (
                                                            <button onClick={() => handleRevokeAdmin(u.id)} className="px-2 py-1 text-xs rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400">撤销管理员</button>
                                                        ) : (
                                                            <button onClick={() => handleSetAdmin(u.id)} className="px-2 py-1 text-xs rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400">设为管理员</button>
                                                        )}
                                                        <button onClick={() => handleDelete(u.id, u.email)} className="px-2 py-1 text-xs rounded-lg bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400">删除</button>
                                                    </>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {showAddModal && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowAddModal(false)}>
                        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 w-full max-w-md shadow-xl" onClick={e => e.stopPropagation()}>
                            <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-4">添加授权邮箱</h2>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm text-slate-500 mb-1">邮箱</label>
                                    <input type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)}
                                        placeholder="user@example.com"
                                        className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                                <div className="flex items-center gap-2">
                                    <input type="checkbox" id="add-is-admin" checked={newIsAdmin} onChange={e => setNewIsAdmin(e.target.checked)}
                                        className="rounded border-slate-300" />
                                    <label htmlFor="add-is-admin" className="text-sm text-slate-600 dark:text-slate-400">设为管理员</label>
                                </div>
                            </div>
                            <div className="flex justify-end gap-2 mt-6">
                                <button onClick={() => setShowAddModal(false)} className="px-4 py-2 text-sm rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700">取消</button>
                                <button onClick={handleAddUser} disabled={adding || !newEmail.trim()}
                                    className="px-4 py-2 text-sm rounded-lg bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50 transition-colors">{adding ? '添加中...' : '确认添加'}</button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Query Logs Section */}
                <div className="mt-8">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-bold text-slate-900 dark:text-white">查询日志</h2>
                        <span className="text-sm text-slate-500">共 {logsTotal} 条记录</span>
                    </div>
                    {logsLoading ? (
                        <div className="text-center py-10 text-slate-400">加载中...</div>
                    ) : logs.length === 0 ? (
                        <div className="text-center py-10 text-slate-400">暂无查询记录</div>
                    ) : (
                        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                                        <th className="text-left px-4 py-3 text-slate-500 font-medium">时间</th>
                                        <th className="text-left px-4 py-3 text-slate-500 font-medium">用户</th>
                                        <th className="text-left px-4 py-3 text-slate-500 font-medium">查询内容</th>
                                        <th className="text-left px-4 py-3 text-slate-500 font-medium">股票代码</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {logs.map(log => (
                                        <tr key={log.id} className="border-b border-slate-100 dark:border-slate-800 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/30">
                                            <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                                                {log.created_at ? new Date(log.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
                                            </td>
                                            <td className="px-4 py-3 text-slate-900 dark:text-white">{log.email || '-'}</td>
                                            <td className="px-4 py-3 text-slate-600 dark:text-slate-400 max-w-xs truncate">{log.query_text || '-'}</td>
                                            <td className="px-4 py-3">
                                                {log.symbol ? (
                                                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">{log.symbol}</span>
                                                ) : '-'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
