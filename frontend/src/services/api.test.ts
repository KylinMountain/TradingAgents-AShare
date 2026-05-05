import { afterEach, describe, expect, it, vi } from 'vitest'

import { getBaseUrl } from '@/services/api'

describe('getBaseUrl', () => {
    afterEach(() => {
        vi.unstubAllEnvs()
    })

    it('uses same-origin relative paths when VITE_API_URL is not configured', () => {
        vi.stubEnv('VITE_API_URL', '')

        expect(getBaseUrl()).toBe('')
    })

    it('uses an explicit API URL without a trailing slash when configured', () => {
        vi.stubEnv('VITE_API_URL', ' https://api.example.test/ ')

        expect(getBaseUrl()).toBe('https://api.example.test')
    })
})
