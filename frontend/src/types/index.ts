// Agent Types
export type AgentStatus = 'pending' | 'in_progress' | 'completed' | 'error' | 'skipped'

export interface Agent {
    id: string
    name: string
    team: string
    status: AgentStatus
    description?: string
    startedAt?: number
    finishedAt?: number
}

export interface AgentTeam {
    name: string
    agents: Agent[]
}

// Analysis Types
export interface InstrumentContext {
    symbol: string
    security_name: string
    market_country: string
    exchange: string
    currency: string
    asset_type: string
}

export interface MarketContext {
    trade_date: string
    timezone: string
    market_country: string
    exchange: string
    market_session: string
    market_is_open: boolean
    analysis_mode: string
    data_as_of: string
    session_note: string
}

export interface UserContext {
    objective?: string
    risk_profile?: string
    investment_horizon?: string
    cash_available?: number
    current_position?: number
    current_position_pct?: number
    average_cost?: number
    max_loss_pct?: number
    constraints?: string[]
    user_notes?: string
}

export interface WorkflowContext {
    context_version: string
    request_source: string
    selected_analysts: string[]
}

export interface GameTheorySignals {
    board?: string
    players?: string[]
    player_states?: Record<string, string>
    likely_actions?: Record<string, string[]>
    dominant_strategy?: string
    fragile_equilibrium?: string
    counter_consensus_signal?: string
    confidence?: number
}

export interface RiskFeedbackState {
    retry_count: number
    max_retries: number
    revision_required: boolean
    latest_risk_verdict: string
    hard_constraints: string[]
    soft_constraints: string[]
    execution_preconditions: string[]
    de_risk_triggers: string[]
    revision_reason: string
}

export interface AnalysisRequest {
    symbol: string
    trade_date: string
    selected_analysts: string[]
    objective?: string
    risk_profile?: string
    investment_horizon?: string
    cash_available?: number
    current_position?: number
    current_position_pct?: number
    average_cost?: number
    max_loss_pct?: number
    constraints?: string[]
    user_notes?: string
    config_overrides?: Record<string, unknown>
    dry_run?: boolean
}

export interface AnalysisResponse {
    job_id: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    created_at: string
}

export interface JobStatus {
    job_id: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    created_at: string
    started_at?: string
    finished_at?: string
    symbol: string
    trade_date: string
    error?: string
    waiting_ahead_count?: number | null
    scheduled_running_count?: number | null
    scheduled_concurrency_limit?: number | null
}

// SSE Event Types
export type SSEEventType =
    | 'job.created'
    | 'job.running'
    | 'job.completed'
    | 'job.failed'
    | 'agent.status'
    | 'agent.message'
    | 'agent.tool_call'
    | 'agent.report'
    | 'agent.report.chunk'
    | 'agent.snapshot'
    | 'agent.milestone'
    | 'agent.writing'
    | 'agent.activity'
    | 'agent.activity_complete'
    | 'agent.token'
    | 'agent.debate'
    | 'agent.debate.token'

export interface SSEEvent {
    event: SSEEventType
    data: Record<string, unknown>
    timestamp: string
}

export interface AgentStatusEvent {
    agent: string
    status: AgentStatus
    previous_status?: AgentStatus
}

export interface AgentMessageEvent {
    agent: string | null
    message_type: string | null
    content: string
}

export interface AgentToolCallEvent {
    agent: string | null
    tool_call: {
        name: string
        args: Record<string, unknown>
    }
}

export interface AgentReportEvent {
    section: string
    content: string
}

export interface ReportChunkEvent {
    section: string
    chunk: string
    index: number
    is_complete: boolean
}

export interface AgentMilestoneEvent {
    stage: string
    title: string
    summary: string
    timestamp: string
}

export interface AgentToolCallDisplayEvent {
    agent: string
    tool: string
    description: string
}

export interface AgentWritingEvent {
    agent: string
    report: string
    report_name: string
    status: 'writing' | 'completed'
}

export interface AgentTokenEvent {
    agent: string
    report: string
    token: string
    horizon?: string
}

export interface AgentActivityEvent {
    agent: string
    type: 'data_fetch' | 'data_analysis' | 'writing' | 'thinking'
    details: string
    tools?: string[]
    is_update?: boolean
}

export interface AgentActivityCompleteEvent {
    agent: string
    type: string
}

export interface AgentSnapshotEvent {
    agents: Array<{
        team: string
        agent: string
        status: AgentStatus
    }>
}

// Streaming Report State
export interface StreamingSectionState {
    buffer: string
    displayed: string
    isTyping: boolean
    isComplete: boolean
}

export interface MilestoneMessage {
    id: string
    stage: string
    title: string
    summary: string
    timestamp: string
}

// Report Types
export interface AnalysisReport {
    symbol: string
    trade_date: string
    decision?: string
    direction?: string
    instrument_context?: InstrumentContext
    market_context?: MarketContext
    user_context?: UserContext
    workflow_context?: WorkflowContext
    market_report?: string
    sentiment_report?: string
    news_report?: string
    fundamentals_report?: string
    macro_report?: string
    smart_money_report?: string
    game_theory_report?: string
    game_theory_signals?: GameTheorySignals
    investment_plan?: string
    trader_investment_plan?: string
    risk_feedback_state?: RiskFeedbackState
    final_trade_decision?: string
}

// UI Types
export interface LogEntry {
    id: string
    timestamp: string
    type: 'system' | 'agent' | 'tool' | 'data' | 'error'
    content: string
    agent?: string
}

export interface StockInfo {
    symbol: string
    name: string
    price: number
    change: number
    changePercent: number
}

export interface KlineCandle {
    date: string
    open: number
    high: number
    low: number
    close: number
    volume?: number | null
    amount?: number | null
    change?: number | null
    change_percent?: number | null
    turnover_rate?: number | null
}

export interface KlineResponse {
    symbol: string
    start_date: string
    end_date: string
    candles: KlineCandle[]
}

// Structured extraction types
export interface RiskItem {
    name: string
    level: 'high' | 'medium' | 'low'
    description?: string
}

export interface KeyMetric {
    name: string
    value: string
    status: 'good' | 'neutral' | 'bad'
}

// Report Types (from database)
export interface Report {
    id: string
    user_id?: string
    symbol: string
    name?: string
    trade_date: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    error?: string
    decision?: string
    direction?: string
    confidence?: number
    target_price?: number
    stop_loss_price?: number
    risk_items?: RiskItem[]
    key_metrics?: KeyMetric[]
    created_at?: string
    updated_at?: string
    waiting_ahead_count?: number | null
    scheduled_running_count?: number | null
    scheduled_concurrency_limit?: number | null
}

export interface ReportDetail extends Report {
    market_report?: string
    sentiment_report?: string
    news_report?: string
    fundamentals_report?: string
    macro_report?: string
    smart_money_report?: string
    game_theory_report?: string
    investment_plan?: string
    trader_investment_plan?: string
    final_trade_decision?: string
    result_data?: AnalysisReport
}

export interface ReportListResponse {
    total: number
    reports: Report[]
}

export interface ReportBatchDeleteResponse {
    deleted_ids: string[]
    missing_ids: string[]
}

export interface AnnouncementItem {
    title: string
    detail: string
}

export interface Announcement {
    id: string
    tag?: string
    title: string
    summary?: string
    published_at: string
    items: AnnouncementItem[]
    cta_label?: string
    cta_path?: string
}

export interface LatestAnnouncementResponse {
    announcement: Announcement | null
}

// Watchlist & Scheduled Analysis
export interface WatchlistItem {
    id: string
    symbol: string
    name: string
    sort_order: number
    created_at: string
    has_scheduled: boolean
}

export interface WatchlistBatchResult {
    input: string
    symbol?: string
    name?: string
    status: 'added' | 'duplicate' | 'invalid' | 'failed'
    message: string
    item?: WatchlistItem
}

export interface WatchlistBatchResponse {
    message: string
    summary: {
        total: number
        added: number
        duplicate: number
        failed: number
    }
    results: WatchlistBatchResult[]
}

export interface ScheduledAnalysis {
    id: string
    symbol: string
    name: string
    horizon: string
    trigger_time: string
    is_active: boolean
    last_run_date: string | null
    last_run_status: string | null
    last_report_id: string | null
    consecutive_failures: number
    created_at: string
    has_imported_context?: boolean
    imported_current_position?: number | null
    imported_average_cost?: number | null
    imported_trade_points_count?: number
}

export interface ScheduledBatchUpdateResponse {
    items: ScheduledAnalysis[]
}

export interface ScheduledBatchDeleteResponse {
    deleted_ids: string[]
    missing_ids: string[]
}

export interface ScheduledBatchTriggerJob {
    item_id: string
    job_id: string
    symbol: string
    name: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    created_at: string
    current_position?: number | null
    average_cost?: number | null
}

export interface ScheduledBatchTriggerResponse {
    summary: {
        total: number
        with_position_context: number
    }
    jobs: ScheduledBatchTriggerJob[]
}

export interface StockSearchResult {
    symbol: string
    name: string
}

export interface ImportedPortfolioPosition {
    symbol: string
    name: string
    current_position?: number | null
    available_position?: number | null
    average_cost?: number | null
    market_value?: number | null
    current_position_pct?: number | null
    trade_points_count: number
    latest_trade_at?: string | null
    latest_trade_action?: string | null
    last_imported_at?: string | null
    recent_trade_points?: Array<Record<string, unknown>>
}

export interface ImportedScheduledSyncSummary {
    created: string[]
    existing: string[]
    skipped_limit: string[]
}

export interface QmtImportState {
    broker: string
    qmt_path?: string | null
    account_id?: string | null
    account_type?: string | null
    auto_apply_scheduled: boolean
    last_synced_at?: string | null
    last_error?: string | null
    summary: {
        positions: number
    }
    scheduled_sync?: ImportedScheduledSyncSummary
    positions: ImportedPortfolioPosition[]
}

export interface PortfolioOverviewResponse {
    watchlist: WatchlistItem[]
    scheduled: ScheduledAnalysis[]
    latest_reports: Report[]
    qmt_import: QmtImportState | null
}

export interface TrackingBoardAnalysis {
    report_id: string
    trade_date: string
    is_previous_trade_day: boolean
    decision?: string | null
    direction?: string | null
    high_price?: number | null
    low_price?: number | null
    trader_advice_summary?: string | null
    trader_investment_plan?: string | null
    final_trade_decision?: string | null
}

export interface TrackingBoardItem {
    symbol: string
    name: string
    current_position?: number | null
    available_position?: number | null
    average_cost?: number | null
    market_value?: number | null
    current_position_pct?: number | null
    live_market_value?: number | null
    floating_pnl?: number | null
    floating_pnl_pct?: number | null
    live_price?: number | null
    day_open?: number | null
    price_change?: number | null
    price_change_pct?: number | null
    day_high?: number | null
    day_low?: number | null
    previous_close?: number | null
    volume?: number | null
    amount?: number | null
    quote_time?: string | null
    quote_source?: string | null
    last_imported_at?: string | null
    analysis?: TrackingBoardAnalysis | null
}

export interface TrackingBoardResponse {
    broker: string
    qmt_path?: string | null
    account_id?: string | null
    account_type?: string | null
    last_synced_at?: string | null
    previous_trade_date: string
    refresh_interval_seconds: number
    items: TrackingBoardItem[]
}

// Runtime config
export interface RuntimeConfig {
    llm_provider: string
    deep_think_llm: string
    quick_think_llm: string
    backend_url: string
    max_debate_rounds: number
    max_risk_discuss_rounds: number
    has_api_key?: boolean
    has_wecom_webhook?: boolean
    wecom_webhook_display?: string | null
    server_fallback_enabled?: boolean
    email_report_enabled?: boolean
    wecom_report_enabled?: boolean
}

export interface RuntimeConfigUpdateResponse {
    message: string
    applied: RuntimeConfigUpdate
    has_api_key: boolean
    current: RuntimeConfig
    warmup?: RuntimeConfigWarmup
}

export interface RuntimeConfigUpdate {
    llm_provider?: string
    deep_think_llm?: string
    quick_think_llm?: string
    backend_url?: string
    max_debate_rounds?: number
    max_risk_discuss_rounds?: number
    api_key?: string
    wecom_webhook_url?: string
    clear_api_key?: boolean
    clear_wecom_webhook?: boolean
    email_report_enabled?: boolean
    wecom_report_enabled?: boolean
    warmup?: boolean
    force_warmup?: boolean
}

export interface RuntimeWarmupRequest extends RuntimeConfigUpdate {
    prompt?: string
}

export interface RuntimeConfigWarmup {
    requested: boolean
    triggered: boolean
    status: 'scheduled' | 'skipped' | 'disabled'
    message: string
    models?: string[]
}

export interface RuntimeWarmupResult {
    model: string
    targets: string[]
    content?: string | null
    error?: string | null
}

export interface RuntimeWarmupResponse {
    prompt: string
    results: RuntimeWarmupResult[]
}

export interface WecomWarmupRequest {
    wecom_webhook_url?: string
    content?: string
}

export interface WecomWarmupResponse {
    sent: boolean
    message: string
    webhook_display?: string | null
}

export interface AuthUser {
    id: string
    email: string
    created_at?: string
    last_login_at?: string
}

export interface AuthVerifyResponse {
    access_token: string
    token_type: string
    user: AuthUser
}

export interface UserToken {
    id: string
    name: string
    token?: string
    token_hint?: string
    last_used_at?: string
    created_at: string
}

export interface UserTokenCreateRequest {
    name: string
}

// Debate message (for battle view)
export interface DebateMessage {
    debate: 'research' | 'risk'
    agent: string
    round: number        // -1 = verdict
    content: string
    isVerdict?: boolean
    horizon?: string
}
