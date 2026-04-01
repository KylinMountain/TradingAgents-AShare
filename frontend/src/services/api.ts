import type { AnalysisRequest, AnalysisResponse, Announcement, AuthUser, AuthVerifyResponse, JobStatus, AnalysisReport, KlineResponse, LatestAnnouncementResponse, PortfolioOverviewResponse, Report, ReportBatchDeleteResponse, ReportDetail, ReportListResponse, RuntimeConfig, RuntimeConfigUpdate, RuntimeConfigUpdateResponse, RuntimeWarmupRequest, RuntimeWarmupResponse, WatchlistItem, WatchlistBatchResponse, ScheduledAnalysis, ScheduledBatchTriggerResponse, StockSearchResult, QmtImportState, TrackingBoardResponse, UserToken, UserTokenCreateRequest, WecomWarmupRequest, WecomWarmupResponse } from '@/types'

export function getBaseUrl(): string {
    const envUrl = (import.meta.env.VITE_API_URL as string) || ''
    if (envUrl) return envUrl.replace(/\/$/, '')
    if (typeof window !== 'undefined' && window.location?.origin) {
        return window.location.origin.replace(/\/$/, '')
    }
    return 'http://localhost:8000'
}

// Kept for backward compatibility
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function getAuthToken(): string | null {
    try {
        return localStorage.getItem('ta-access-token')
    } catch {
        return null
    }
}

class ApiService {
    private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
        const url = `${getBaseUrl()}${endpoint}`
        const token = getAuthToken()
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
                ...options?.headers,
            },
        })

        if (!response.ok) {
            const contentType = response.headers.get('content-type') || ''
            if (contentType.includes('application/json')) {
                const data = await response.json().catch(() => null)
                const detail = data?.detail || data?.message
                throw new Error(detail || `HTTP error! status: ${response.status}`)
            }
            const error = await response.text()
            throw new Error(error || `HTTP error! status: ${response.status}`)
        }

        if (response.status === 204 || response.status === 205) {
            return undefined as T
        }

        const contentType = response.headers.get('content-type') || ''
        if (!contentType.includes('application/json')) {
            const text = await response.text()
            return (text ? (text as T) : undefined) as T
        }

        const raw = await response.text()
        if (!raw) {
            return undefined as T
        }

        return JSON.parse(raw) as T
    }

    async startAnalysis(request: AnalysisRequest): Promise<AnalysisResponse> {
        return this.request<AnalysisResponse>('/v1/analyze', {
            method: 'POST',
            body: JSON.stringify(request),
        })
    }

    async getJobStatus(jobId: string): Promise<JobStatus> {
        return this.request<JobStatus>(`/v1/jobs/${jobId}`)
    }

    async getJobResult(jobId: string): Promise<{ job_id: string; status: string; decision: string; result: AnalysisReport }> {
        return this.request(`/v1/jobs/${jobId}/result`)
    }

    async getKline(symbol: string, startDate?: string, endDate?: string): Promise<KlineResponse> {
        const params = new URLSearchParams({ symbol })
        if (startDate) params.append('start_date', startDate)
        if (endDate) params.append('end_date', endDate)
        return this.request<KlineResponse>(`/v1/market/kline?${params}`)
    }

    async chatCompletion(
        messages: Array<{ role: string; content: string }>,
        stream = true,
        selectedAnalysts?: string[],
    ) {
        const response = await fetch(`${getBaseUrl()}/v1/chat/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
            },
            body: JSON.stringify({
                messages,
                stream,
                selected_analysts: selectedAnalysts,
            }),
        })

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }

        return response
    }

    // Report API Methods
    async getReports(symbol?: string, skip = 0, limit = 100): Promise<ReportListResponse> {
        const params = new URLSearchParams()
        if (symbol) params.append('symbol', symbol)
        params.append('skip', skip.toString())
        params.append('limit', limit.toString())
        return this.request<ReportListResponse>(`/v1/reports?${params}`)
    }

    async getLatestReportsBySymbols(symbols: string[]): Promise<{ reports: Report[] }> {
        return this.request<{ reports: Report[] }>('/v1/reports/latest-by-symbols', {
            method: 'POST',
            body: JSON.stringify({ symbols }),
        })
    }

    async getReport(reportId: string): Promise<ReportDetail> {
        return this.request<ReportDetail>(`/v1/reports/${reportId}`)
    }

    async getLatestAnnouncement(): Promise<Announcement | null> {
        const data = await this.request<LatestAnnouncementResponse>('/v1/announcements/latest')
        return data.announcement
    }

    async deleteReport(reportId: string): Promise<{ message: string }> {
        return this.request<{ message: string }>(`/v1/reports/${reportId}`, {
            method: 'DELETE',
        })
    }

    async deleteReportsBatch(reportIds: string[]): Promise<ReportBatchDeleteResponse> {
        return this.request<ReportBatchDeleteResponse>('/v1/reports/batch/delete', {
            method: 'POST',
            body: JSON.stringify({ report_ids: reportIds }),
        })
    }

    async createReport(report: {
        symbol: string
        trade_date: string
        decision?: string
        result_data?: AnalysisReport
    }): Promise<Report> {
        return this.request<Report>('/v1/reports', {
            method: 'POST',
            body: JSON.stringify(report),
        })
    }

    // Watchlist
    async getWatchlist(): Promise<{ items: WatchlistItem[] }> {
        return this.request<{ items: WatchlistItem[] }>('/v1/watchlist')
    }
    async addToWatchlist(input: string): Promise<WatchlistBatchResponse> {
        return this.request<WatchlistBatchResponse>('/v1/watchlist', {
            method: 'POST',
            body: JSON.stringify({ text: input }),
        })
    }
    async removeFromWatchlist(id: string): Promise<void> {
        await this.request('/v1/watchlist/' + id, { method: 'DELETE' })
    }

    // Scheduled Analysis
    async getScheduled(): Promise<{ items: ScheduledAnalysis[] }> {
        return this.request<{ items: ScheduledAnalysis[] }>('/v1/scheduled')
    }
    async getPortfolioOverview(): Promise<PortfolioOverviewResponse> {
        return this.request<PortfolioOverviewResponse>('/v1/portfolio/overview')
    }
    async createScheduled(symbol: string, horizon?: string, trigger_time?: string): Promise<ScheduledAnalysis> {
        return this.request<ScheduledAnalysis>('/v1/scheduled', {
            method: 'POST',
            body: JSON.stringify({ symbol, horizon, trigger_time }),
        })
    }
    async updateScheduled(id: string, data: { is_active?: boolean; horizon?: string; trigger_time?: string }): Promise<ScheduledAnalysis> {
        return this.request<ScheduledAnalysis>('/v1/scheduled/' + id, {
            method: 'PATCH',
            body: JSON.stringify(data),
        })
    }
    async updateScheduledBatch(
        item_ids: string[],
        data: { is_active?: boolean; horizon?: string; trigger_time?: string }
    ): Promise<{ items: ScheduledAnalysis[] }> {
        return this.request<{ items: ScheduledAnalysis[] }>('/v1/scheduled/batch', {
            method: 'PATCH',
            body: JSON.stringify({ item_ids, ...data }),
        })
    }
    async deleteScheduled(id: string): Promise<void> {
        await this.request('/v1/scheduled/' + id, { method: 'DELETE' })
    }
    async deleteScheduledBatch(item_ids: string[]): Promise<{ deleted_ids: string[]; missing_ids: string[] }> {
        return this.request<{ deleted_ids: string[]; missing_ids: string[] }>('/v1/scheduled/batch/delete', {
            method: 'POST',
            body: JSON.stringify({ item_ids }),
        })
    }
    async triggerScheduledTest(id: string): Promise<AnalysisResponse> {
        return this.request<AnalysisResponse>(`/v1/scheduled/${id}/trigger`, {
            method: 'POST',
        })
    }
    async triggerScheduledBatch(item_ids: string[]): Promise<ScheduledBatchTriggerResponse> {
        return this.request<ScheduledBatchTriggerResponse>('/v1/scheduled/batch/trigger', {
            method: 'POST',
            body: JSON.stringify({ item_ids }),
        })
    }

    async getQmtImportState(): Promise<QmtImportState> {
        return this.request<QmtImportState>('/v1/portfolio/imports/qmt')
    }

    async syncQmtImport(data: {
        qmt_path: string
        account_id: string
        account_type?: string
        auto_apply_scheduled: boolean
    }): Promise<QmtImportState> {
        return this.request<QmtImportState>('/v1/portfolio/imports/qmt', {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async clearQmtImport(): Promise<void> {
        await this.request('/v1/portfolio/imports/qmt', { method: 'DELETE' })
    }

    async getDashboardTrackingBoard(): Promise<TrackingBoardResponse> {
        return this.request<TrackingBoardResponse>('/v1/dashboard/tracking-board')
    }

    // Stock Search
    async searchStocks(q: string): Promise<{ results: StockSearchResult[] }> {
        return this.request<{ results: StockSearchResult[] }>(`/v1/market/stock-search?q=${encodeURIComponent(q)}`)
    }

    async getConfig(): Promise<RuntimeConfig> {
        return this.request<RuntimeConfig>('/v1/config')
    }

    async updateConfig(updates: RuntimeConfigUpdate): Promise<RuntimeConfigUpdateResponse> {
        return this.request<RuntimeConfigUpdateResponse>('/v1/config', {
            method: 'PATCH',
            body: JSON.stringify(updates),
        })
    }

    async warmupConfig(request: RuntimeWarmupRequest): Promise<RuntimeWarmupResponse> {
        return this.request<RuntimeWarmupResponse>('/v1/config/warmup', {
            method: 'POST',
            body: JSON.stringify(request),
        })
    }

    async warmupWecom(request: WecomWarmupRequest): Promise<WecomWarmupResponse> {
        return this.request<WecomWarmupResponse>('/v1/config/wecom/warmup', {
            method: 'POST',
            body: JSON.stringify(request),
        })
    }

    async requestLoginCode(email: string): Promise<{ message: string; dev_code?: string }> {
        return this.request('/v1/auth/request-code', {
            method: 'POST',
            body: JSON.stringify({ email }),
        })
    }

    async verifyLoginCode(email: string, code: string): Promise<AuthVerifyResponse> {
        return this.request('/v1/auth/verify-code', {
            method: 'POST',
            body: JSON.stringify({ email, code }),
        })
    }

    async getMe(): Promise<AuthUser> {
        return this.request('/v1/auth/me')
    }

    // Token Management
    async getTokens(): Promise<UserToken[]> {
        return this.request<UserToken[]>('/v1/tokens')
    }

    async createToken(request: UserTokenCreateRequest): Promise<UserToken> {
        return this.request<UserToken>('/v1/tokens', {
            method: 'POST',
            body: JSON.stringify(request),
        })
    }

    async deleteToken(tokenId: string): Promise<{ message: string }> {
        return this.request<{ message: string }>(`/v1/tokens/${tokenId}`, {
            method: 'DELETE',
        })
    }
}

export const api = new ApiService()
