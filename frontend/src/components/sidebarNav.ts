import type { LucideIcon } from 'lucide-react'
import {
    Activity,
    Briefcase,
    FileText,
    LayoutDashboard,
    Settings,
    Wallet,
} from 'lucide-react'

export interface SidebarNavItem {
    path: string
    icon: LucideIcon
    label: string
}

export const navItems: SidebarNavItem[] = [
    { path: '/', icon: LayoutDashboard, label: '控制台' },
    { path: '/analysis', icon: Activity, label: '智能分析' },
    { path: '/reports', icon: FileText, label: '历史报告' },
    { path: '/portfolio', icon: Briefcase, label: '自选 & 定时' },
    { path: '/tracking-board', icon: Wallet, label: '跟踪看板' },
    { path: '/settings', icon: Settings, label: '设置' },
]
