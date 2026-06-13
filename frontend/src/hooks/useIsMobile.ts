import { useEffect, useState } from 'react'

export function useIsMobile(breakpoint = 768) {
    const [isMobile, setIsMobile] = useState(() => {
        if (typeof window === 'undefined') return false
        return window.innerWidth < breakpoint
    })

    useEffect(() => {
        const onResize = () => setIsMobile(window.innerWidth < breakpoint)
        window.addEventListener('resize', onResize)
        return () => window.removeEventListener('resize', onResize)
    }, [breakpoint])

    return isMobile
}
