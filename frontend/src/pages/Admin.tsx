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

export default function Admin() {
    const user = useAuthStore(s => s.user)
    const navigate = useNavigate()
    const [users, setUsers] = useState<AdminUser[]>([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    useEffect(() => {
        if (!user) return
        loadUsers()
    }, [user])

    const loadUsers = async () => {
        setLoading(true)
        setError('')
        try {
            const resp = await api.get('/v1/admin/users?limit=200')
            setUsers(resp.data.users)
            setTotal(resp.data.total)
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
                    <span className="text-sm text-slate-500">共 {total} 个用户</span>
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
            </div>
        </div>
    )
}
