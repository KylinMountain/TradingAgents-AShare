import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import Header from './Header'
import { useIsMobile } from '@/hooks/useIsMobile'

interface LayoutProps {
    children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
    const isMobile = useIsMobile()

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
            {!isMobile && <Sidebar />}
            <div className={`${isMobile ? 'ml-0' : 'ml-16'} min-h-screen flex flex-col`}>
                <Header />
                <main className={`flex-1 bg-slate-50 dark:bg-gradient-to-br dark:from-slate-900 dark:via-slate-900/95 dark:to-slate-800 ${isMobile ? 'p-2 pt-3' : 'p-6'}`}>
                    {children}
                </main>
            </div>
        </div>
    )
}
