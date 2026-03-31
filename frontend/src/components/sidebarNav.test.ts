import { describe, expect, it } from 'vitest'

import { navItems } from '@/components/sidebarNav'

describe('sidebarNav', () => {
    it('includes a dedicated tracking board entry in the sidebar', () => {
        const trackingBoardIndex = navItems.findIndex(item => item.path === '/tracking-board')

        expect(trackingBoardIndex).toBeGreaterThan(0)
        expect(navItems[trackingBoardIndex]).toMatchObject({
            path: '/tracking-board',
            label: '跟踪看板',
        })
        expect(navItems[trackingBoardIndex - 1]).toMatchObject({
            path: '/',
            label: '控制台',
        })
    })
})
