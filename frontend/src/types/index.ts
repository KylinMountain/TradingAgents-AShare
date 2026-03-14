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
    trade_date: string
    decision?: string
    direction?: string
    confidence?: number
    target_price?: number
    stop_loss_price?: number
    risk_items?: RiskItem[]
    key_metrics?: KeyMetric[]
    created_at?: string
    updated_at?: string
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

// Hot stock from market hot rank
export interface HotStock {
    rank: number
    symbol: string
    name: string
    price: number
    change: number
    change_pct: number
    extra: string  // Additional info like "连涨11天" or "关注 3,551,238"
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
    server_fallback_enabled?: boolean
}

export interface RuntimeConfigUpdateResponse {
    message: string
    applied: RuntimeConfigUpdate
    has_api_key: boolean
    current: RuntimeConfig
}

export interface RuntimeConfigUpdate {
    llm_provider?: string
    deep_think_llm?: string
    quick_think_llm?: string
    backend_url?: string
    max_debate_rounds?: number
    max_risk_discuss_rounds?: number
    api_key?: string
    clear_api_key?: boolean
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
    token: string
    last_used_at?: string
    created_at: string
}

export interface UserTokenCreateRequest {
    name: string
}
