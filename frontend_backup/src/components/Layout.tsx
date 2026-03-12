import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import Header from './Header'

interface LayoutProps {
    children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
            <Sidebar />
            <div className="ml-16 min-h-screen flex flex-col">
                <Header />
                <main className="flex-1 p-6 bg-slate-50 dark:bg-gradient-to-br dark:from-slate-900 dark:via-slate-900/95 dark:to-slate-800">
                    {children}
                </main>
            </div>
        </div>
    )
}
