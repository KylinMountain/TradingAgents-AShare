import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
    LayoutDashboard,
    Activity,
    FileText,
    Settings,
    TrendingUp,
    Briefcase
} from 'lucide-react'

const navItems = [
    { path: '/', icon: LayoutDashboard, label: '控制台' },
    { path: '/analysis', icon: Activity, label: '智能分析' },
    { path: '/reports', icon: FileText, label: '历史报告' },
    { path: '/portfolio', icon: Briefcase, label: '自选股' },
    { path: '/settings', icon: Settings, label: '设置' },
]

export default function Sidebar() {
    const [isExpanded, setIsExpanded] = useState(false)

    return (
        <aside
            className={`fixed left-0 top-0 h-full bg-slate-900/95 backdrop-blur-md border-r border-slate-700 flex flex-col z-50 transition-all duration-300 ${isExpanded ? 'w-48' : 'w-16'
                }`}
            onMouseEnter={() => setIsExpanded(true)}
            onMouseLeave={() => setIsExpanded(false)}
        >
            {/* Logo */}
            <div className="h-16 flex items-center justify-center border-b border-slate-700 px-2">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/30 flex-shrink-0">
                        <TrendingUp className="w-5 h-5 text-white" />
                    </div>
                    {isExpanded && (
                        <span className="font-bold text-base bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent whitespace-nowrap">
                            TradingAgents
                        </span>
                    )}
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-4 px-2 space-y-2">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                            `flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 ${isActive
                                ? 'bg-gradient-to-r from-blue-500/20 to-purple-500/20 text-blue-400 border border-blue-500/30'
                                : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                            }`
                        }
                    >
                        <item.icon className="w-5 h-5 flex-shrink-0" />
                        {isExpanded && (
                            <span className="font-medium text-sm whitespace-nowrap">{item.label}</span>
                        )}
                    </NavLink>
                ))}
            </nav>

            {/* Footer */}
            <div className="p-3 border-t border-slate-700">
                {isExpanded ? (
                    <div className="text-xs text-slate-500 text-center">
                        <p className="text-slate-400 text-sm font-medium">TradingAgents</p>
                        <p className="mt-0.5">多智能体投研系统 v0.1.0</p>
                    </div>
                ) : (
                    <div className="text-[10px] text-slate-500 text-center">v0.1</div>
                )}
            </div>
        </aside>
    )
}
