import { useEffect, useMemo, useRef, useState } from 'react'
import { Bell, BellOff, ChevronDown, LogOut, Monitor, Moon, Settings, Sun, Github, Heart, Megaphone } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import type { Announcement } from '@/types'

type ThemeMode = 'system' | 'light' | 'dark'

function getInitials(email?: string | null): string {
    if (!email) return 'TA'
    return email.slice(0, 2).toUpperCase()
}

function formatAnnouncementTime(value?: string): string {
    if (!value) return ''
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return value
    return parsed.toLocaleDateString('zh-CN', {
        month: 'numeric',
        day: 'numeric',
    })
}

export default function Header() {
    const navigate = useNavigate()
    const { user, logout } = useAuthStore()
    const [themeMode, setThemeMode] = useState<ThemeMode>('system')
    const [notifPermission, setNotifPermission] = useState<NotificationPermission>('default')
    const [menuOpen, setMenuOpen] = useState(false)
    const [announcementOpen, setAnnouncementOpen] = useState(false)
    const [announcement, setAnnouncement] = useState<Announcement | null>(null)
    const menuRef = useRef<HTMLDivElement | null>(null)
    const announceRef = useRef<HTMLDivElement | null>(null)

    useEffect(() => {
        const saved = (localStorage.getItem('ta-theme') || 'system') as ThemeMode
        const mode: ThemeMode = ['system', 'light', 'dark'].includes(saved) ? saved : 'system'
        setThemeMode(mode)
        applyTheme(mode)
        if ('Notification' in window) setNotifPermission(Notification.permission)
    }, [])

    useEffect(() => {
        if (!user) return
        let cancelled = false
        api.getLatestAnnouncement()
            .then((data) => {
                if (!cancelled) setAnnouncement(data)
            })
            .catch(() => {
                if (!cancelled) setAnnouncement(null)
            })
        return () => {
            cancelled = true
        }
    }, [user])

    useEffect(() => {
        const onClick = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setMenuOpen(false)
            }
            if (announceRef.current && !announceRef.current.contains(event.target as Node)) {
                setAnnouncementOpen(false)
            }
        }
        document.addEventListener('mousedown', onClick)
        return () => document.removeEventListener('mousedown', onClick)
    }, [])

    const applyTheme = (mode: ThemeMode) => {
        const root = document.documentElement
        const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        const shouldBeDark = mode === 'system' ? systemDark : mode === 'dark'
        root.classList.toggle('dark', shouldBeDark)
    }

    const cycleTheme = () => {
        const next: ThemeMode =
            themeMode === 'system' ? 'light' : themeMode === 'light' ? 'dark' : 'system'
        setThemeMode(next)
        localStorage.setItem('ta-theme', next)
        applyTheme(next)
    }

    const toggleNotifications = async () => {
        if (!('Notification' in window)) return
        if (Notification.permission === 'denied') {
            alert('通知权限已被浏览器拒绝，请在浏览器设置中手动开启')
            return
        }
        const perm = await Notification.requestPermission()
        setNotifPermission(perm)
    }

    const themeLabel = themeMode === 'system' ? '跟随系统' : themeMode === 'light' ? '浅色' : '深色'
    const ThemeIcon = themeMode === 'system' ? Monitor : themeMode === 'light' ? Sun : Moon
    const accountTone = useMemo(() => getInitials(user?.email), [user?.email])
    const announcementStorageKey = announcement ? `ta-announcement-read:${announcement.id}` : null
    const hasUnreadAnnouncement = Boolean(
        announcement &&
        announcementStorageKey &&
        localStorage.getItem(announcementStorageKey) !== '1'
    )

    const handleAnnouncementToggle = () => {
        const next = !announcementOpen
        setAnnouncementOpen(next)
        if (next && announcementStorageKey) {
            localStorage.setItem(announcementStorageKey, '1')
        }
    }

    return (
        <header className="h-16 sticky top-0 z-40 border-b border-slate-200/80 dark:border-slate-800 bg-white/88 dark:bg-slate-950/78 backdrop-blur-xl">
            <div className="h-full px-6 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="hidden md:flex items-center gap-4">
                        <div className="flex items-center gap-2.5">
                            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_16px_rgba(16,185,129,0.4)]" />
                            <div className="text-sm font-semibold tracking-[0.04em] text-slate-900 dark:text-slate-100">A 股投研终端</div>
                        </div>
                        <div className="h-4 w-px bg-slate-200 dark:bg-slate-800" />
                        <div className="text-xs tracking-[0.18em] text-slate-400 dark:text-slate-500">工作台在线</div>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {announcement && (
                        <div className="relative" ref={announceRef}>
                            <button
                                onClick={handleAnnouncementToggle}
                                className="group relative flex items-center gap-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 hover:border-slate-300 dark:hover:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-900/90 transition-all"
                                title={announcement.title}
                            >
                                <Megaphone className="w-4 h-4 text-slate-700 dark:text-slate-300 group-hover:text-blue-600 dark:group-hover:text-blue-400" />
                                <span className="hidden sm:inline text-[13px] font-medium text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-white">
                                    {announcement.tag || '公告'}
                                </span>
                                {hasUnreadAnnouncement && (
                                    <span className="absolute right-2 top-1.5 w-2 h-2 rounded-full bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.6)]" />
                                )}
                            </button>

                            {announcementOpen && (
                                <div className="absolute right-0 top-full mt-3 w-[360px] p-4 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-[0_24px_80px_rgba(15,23,42,0.18)] z-50">
                                    <div className="flex items-start justify-between gap-3 mb-3">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300">
                                                    {announcement.tag || '公告'}
                                                </span>
                                                <span className="text-[11px] text-slate-400 dark:text-slate-500">
                                                    {formatAnnouncementTime(announcement.published_at)}
                                                </span>
                                            </div>
                                            <div className="mt-2 text-sm font-bold text-slate-900 dark:text-slate-100">
                                                {announcement.title}
                                            </div>
                                            {announcement.summary && (
                                                <div className="mt-1 text-[12px] leading-relaxed text-slate-500 dark:text-slate-400">
                                                    {announcement.summary}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="space-y-3">
                                        {announcement.items.map((item) => (
                                            <div key={item.title} className="group">
                                                <div className="text-[13px] font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                                                    <div className="w-1.5 h-1.5 rounded-full bg-blue-500 group-hover:scale-125 transition-transform" />
                                                    {item.title}
                                                </div>
                                                <div className="mt-0.5 pl-3 text-[12px] text-slate-500 dark:text-slate-500 leading-relaxed">
                                                    {item.detail}
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    {announcement.cta_label && announcement.cta_path && (
                                        <button
                                            onClick={() => {
                                                setAnnouncementOpen(false)
                                                navigate(announcement.cta_path!)
                                            }}
                                            className="mt-4 w-full py-2 rounded-xl bg-slate-50 dark:bg-slate-900 hover:bg-blue-50 dark:hover:bg-blue-900/20 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600 transition-colors"
                                        >
                                            {announcement.cta_label}
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    )}
                    <Link
                        to="/sponsor"
                        className="group flex items-center gap-2 rounded-2xl border border-pink-200 dark:border-pink-900 bg-white dark:bg-slate-900 px-3 py-1.5 hover:border-pink-300 dark:hover:border-pink-700 hover:bg-pink-50 dark:hover:bg-pink-950/30 transition-all mr-1"
                        title="赞助支持"
                    >
                        <Heart className="w-4 h-4 text-pink-500 dark:text-pink-400 group-hover:text-pink-600 dark:group-hover:text-pink-300" />
                        <span className="text-[13px] font-medium text-pink-600 dark:text-pink-400 group-hover:text-pink-700 dark:group-hover:text-pink-300 hidden sm:inline">赞助</span>
                    </Link>
                    <a
                        href="https://github.com/KylinMountain/TradingAgents-AShare"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group flex items-center gap-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 hover:border-slate-300 dark:hover:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-900/90 transition-all mr-1"
                        title="Star us on GitHub"
                    >
                        <Github className="w-4 h-4 text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-white" />
                        <span className="text-[13px] font-medium text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-white hidden sm:inline">Star</span>
                    </a>
                    {user && (
                        <div className="relative" ref={menuRef}>
                            <button
                                onClick={() => setMenuOpen(v => !v)}
                                className="group flex items-center gap-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-2 py-1.5 hover:border-slate-300 dark:hover:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-900/90 transition-all"
                            >
                                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 via-blue-500 to-indigo-600 text-white flex items-center justify-center text-[11px] font-bold shadow-[0_10px_20px_rgba(37,99,235,0.2)]">
                                    {accountTone}
                                </div>
                                <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
                            </button>

                            {menuOpen && (
                                <div className="absolute right-0 top-[calc(100%+0.75rem)] w-64 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-[0_24px_80px_rgba(15,23,42,0.18)] overflow-hidden">
                                    <div className="px-4 py-3.5 border-b border-slate-100 dark:border-slate-900">
                                        <div className="text-[11px] tracking-[0.18em] text-slate-400 dark:text-slate-500">研究空间</div>
                                        <div className="mt-1.5 text-sm font-medium leading-6 text-slate-950 dark:text-slate-50 break-all">{user.email}</div>
                                    </div>
                                    <div className="p-2">
                                        <button
                                            onClick={cycleTheme}
                                            className="w-full flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
                                        >
                                            <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-slate-900 flex items-center justify-center">
                                                <ThemeIcon className="w-4 h-4" />
                                            </div>
                                            <div className="flex-1 text-left">
                                                <div>主题模式</div>
                                                <div className="text-xs text-slate-400 dark:text-slate-500">{themeLabel}</div>
                                            </div>
                                        </button>
                                        <button
                                            onClick={toggleNotifications}
                                            className="w-full flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
                                        >
                                            <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-slate-900 flex items-center justify-center relative">
                                                {notifPermission === 'denied' ? <BellOff className="w-4 h-4" /> : <Bell className="w-4 h-4" />}
                                                <span className={`absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full ${
                                                    notifPermission === 'granted' ? 'bg-emerald-500' : notifPermission === 'denied' ? 'bg-rose-500' : 'bg-slate-400'
                                                }`} />
                                            </div>
                                            <div className="flex-1 text-left">
                                                <div>通知提醒</div>
                                                <div className="text-xs text-slate-400 dark:text-slate-500">
                                                    {notifPermission === 'granted' ? '已启用' : notifPermission === 'denied' ? '已拒绝' : '未设置'}
                                                </div>
                                            </div>
                                        </button>
                                        <button
                                            onClick={() => {
                                                setMenuOpen(false)
                                                navigate('/reports')
                                            }}
                                            className="w-full flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
                                        >
                                            <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-slate-900 flex items-center justify-center">
                                                <Monitor className="w-4 h-4" />
                                            </div>
                                            我的报告
                                        </button>
                                        <button
                                            onClick={() => {
                                                setMenuOpen(false)
                                                navigate('/settings')
                                            }}
                                            className="w-full flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
                                        >
                                            <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-slate-900 flex items-center justify-center">
                                                <Settings className="w-4 h-4" />
                                            </div>
                                            模型设置
                                        </button>
                                    </div>
                                    <div className="p-2 border-t border-slate-100 dark:border-slate-900">
                                        <button
                                            onClick={() => {
                                                setMenuOpen(false)
                                                logout()
                                            }}
                                            className="w-full flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors"
                                        >
                                            <div className="w-8 h-8 rounded-xl bg-rose-50 dark:bg-rose-500/10 flex items-center justify-center">
                                                <LogOut className="w-4 h-4" />
                                            </div>
                                            退出登录
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </header>
    )
}
