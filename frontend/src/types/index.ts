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
    volume_price_report?: string
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
    name?: string
    start_date: string
    end_date: string
    candles: KlineCandle[]
}

export interface NiuxiongPoint {
    date: string
    close: number
    decision_line?: number | null
    bull_line?: number | null
    bear_line?: number | null
    orbit_line?: number | null
    orbit_direction?: number | null
    buy_signal?: boolean
    sell_signal?: boolean
}

export interface NiuxiongResponse {
    symbol: string
    name?: string | null
    points: NiuxiongPoint[]
    signal?: Record<string, any> | null
}

export interface GSPoint {
    date: string
    close: number
    bb_line?: number | null
    a_line?: number | null
    trend_state?: string | null
    kline_color?: number | null
    zj_bias?: number | null
    buy_signal?: boolean
    sell_signal?: boolean
}

export interface GSResponse {
    symbol: string
    name?: string | null
    points: GSPoint[]
    signal?: Record<string, any> | null
}

export interface RadarPoint {
    date: string
    close: number
    radar_wave?: number | null
    radar_avg?: number | null
    radar_buy?: boolean
    radar_sell?: boolean
    radar_top?: boolean
    radar_down?: boolean
}

export interface RadarResponse {
    symbol: string
    name?: string | null
    points: RadarPoint[]
    signal?: Record<string, any> | null
}

export interface PositionPoint {
    date: string
    close: number
    position_index?: number | null
    zone?: string | null
}

export interface PositionResponse {
    symbol: string
    name?: string | null
    points: PositionPoint[]
    signal?: Record<string, any> | null
}

export interface VolumeWashPoint {
    date: string
    close: number
    volume: number
    vol_wash_type: number  // 0=普通, 2=缩量洗盘, 3=温和放量, 4=放量突破, 5=缩量试盘
}

export interface VolumeWashResponse {
    symbol: string
    name?: string | null
    points: VolumeWashPoint[]
    signal?: Record<string, any> | null
}

export interface FundFlowPoint {
    date: string
    close: number
    main_net?: number | null
    main_pct?: number | null
    super_large_net?: number | null
    large_net?: number | null
    medium_net?: number | null
    small_net?: number | null
}

export interface FundFlowResponse {
    symbol: string
    name?: string | null
    points: FundFlowPoint[]
    signal?: Record<string, any> | null
}

export interface DarkPoolEvent {
    start: string
    end: string
    duration_min: number
    direction: string
    volume: number
    base_score: number
    quality_score: number
    level: string
    indicators: string
}

export interface DarkPoolMarket {
    open: number; high: number; low: number; close: number; chg_pct: number
    total_vol: number; total_amt_wan: number; tick_count: number
}

export interface DarkPoolInstitutional {
    inst_participation_pct: number; inst_net_wan: number; retail_net_wan: number
    tick_net_wan: number; big_active_buy_wan: number; big_active_sell_wan: number
    intent: string
}

export interface DarkPoolTail {
    tail_vol_ratio_pct: number; tail_chg_pct: number; full_chg_pct: number; signal: string
}

export interface DarkPoolDimension {
    total_events: number; high_conf_count: number; suspected_count: number
    split_vol: number; split_vol_pct: number
    active_buy_vol: number; active_sell_vol: number
    direction: string; events: DarkPoolEvent[]
}

export interface DarkPoolComposite {
    signals: string[]; confidence: number; verdict: string
    intent: string; prediction: string; key_facts: string[]
}

export interface DarkPoolAnalysisResponse {
    symbol: string; name?: string | null; date: string
    market?: DarkPoolMarket | null
    dim1_institutional?: DarkPoolInstitutional | null
    dim2_tail?: DarkPoolTail | null
    dim3_split?: DarkPoolDimension | null
    composite?: DarkPoolComposite | null
    error?: string | null
}

export type IndicatorMode = 'niuxiong' | 'gs' | 'combined' | 'off'

export type KlinePeriod = 'daily' | 'weekly' | 'monthly'

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
    volume_price_report?: string
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
    notes: string
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

export interface PortfolioImportState {
    auto_apply_scheduled: boolean
    last_synced_at?: string | null
    last_error?: string | null
    summary: {
        positions: number
    }
    scheduled_sync?: ImportedScheduledSyncSummary
    positions: ImportedPortfolioPosition[]
}

export interface PortfolioPositionInput {
    symbol: string
    name?: string
    current_position?: number | null
    available_position?: number | null
    average_cost?: number | null
    market_value?: number | null
    current_position_pct?: number | null
}

export interface PortfolioOverviewResponse {
    watchlist: WatchlistItem[]
    scheduled: ScheduledAnalysis[]
    latest_reports: Report[]
    portfolio_import: PortfolioImportState | null
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
    default_analysts?: string[]
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
    default_analysts?: string[]
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
    is_admin?: boolean
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

// Feedback types
export interface FeedbackItem {
    id: string
    user_email: string
    subject: string
    content: string
    admin_reply?: string | null
    replied_at?: string | null
    is_read: boolean
    created_at?: string
    updated_at?: string
}

export interface FeedbackListResponse {
    total: number
    feedbacks: FeedbackItem[]
}

export interface FeedbackUnreadResponse {
    unread_count: number
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

// ─── Pre-market Briefing ───────────────────────────────────────────

export interface BriefingItem {
    id: string
    date: string
    status: 'pending' | 'running' | 'completed' | 'failed'
}

export interface BriefingMarketData {
    us_indices?: Array<{ name: string; symbol: string; close: number; change_pct: number }>
    hk_index?: Array<{ name: string; close: number; change_pct: number }>
    a50_futures?: { name: string; symbol: string; close: number; change_pct: number; change_amt?: number; high?: number; low?: number; open?: number; prev_settle?: number } | null
    commodities?: Array<{ name: string; close: number; change_pct: number }>
    fx?: Array<{ name: string; close: number; change_pct: number }>
    fund_flow?: { date: string; main_net: number; super_large_net: number; large_net: number } | null
    chinese_adrs?: Array<{ symbol: string; name: string; close: number; change_pct: number; change_amt?: number }>
    market_sentiment?: BriefingSentiment | null
    north_bound?: BriefingNorthBound | null
    dragon_tiger?: BriefingDragonTiger | null
    industry_ranking?: BriefingIndustryRanking | null
    hot_stocks?: BriefingHotStock[]
    global_news?: BriefingGlobalNewsItem[]
    macro_data?: BriefingMacroData | null
    sector_fund_flow?: BriefingSectorFundFlow | null
    announcements?: BriefingAnnouncements | null
    us_tech_mapping?: USTechMapping | null
}

export interface USTechMapping {
    sectors: USTechSector[]
    risk_indicators?: {
        VIX?: { name: string; close: number; change_pct: number }
        TLT?: { name: string; close: number; change_pct: number }
    }
    overall_sentiment: 'bullish' | 'bearish' | 'mixed' | 'neutral'
    update_time?: string
    error?: string
}

export interface USTechSector {
    name: string
    stocks: USTechStock[]
    a_mapping: string
    sentiment: 'bullish' | 'bearish' | 'mixed'
}

export interface USTechStock {
    symbol: string
    name: string
    close: number
    change_pct: number
    is_stock?: boolean
}

export interface BriefingSentiment {
    limit_up_count: number
    limit_down_count: number
    bust_rate_pct: number
    max_streak: number
    top_streak_stocks: Array<{
        name: string; code: string; streak: number; reason: string
        seal_amount_wan?: number
        first_seal_time?: string
        last_seal_time?: string
        bust_count?: number
        change_pct?: number
    }>
    prev_volume?: number | null
    volume_change_pct?: number | null
}

export interface BriefingSectorFundFlow {
    top_inflow: Array<{ name: string; net_inflow_yi: number }>
    top_outflow: Array<{ name: string; net_inflow_yi: number }>
}

export interface BriefingAnnouncements {
    major_events?: Array<{ code: string; name: string; title: string }>
    shareholder_changes?: Array<{ code: string; name: string; title: string }>
}

export interface BriefingNorthBound {
    hgt_net?: number | null
    sgt_net?: number | null
    total_net?: number | null
    recent_days?: Array<{ date: string; net_flow_yi: number }>
}

export interface BriefingDragonTiger {
    total_records: number
    top_net_buy: Array<{ code: string; name: string; net_buy_wan: number; buy_wan: number; sell_wan: number }>
    top_net_sell: Array<{ code: string; name: string; net_buy_wan: number; buy_wan: number; sell_wan: number }>
    institution_net?: number | null
}

export interface BriefingIndustryRanking {
    top: Array<{ name: string; change_pct: number; up_count: number; down_count: number; leader: string; leader_change: number }>
    bottom: Array<{ name: string; change_pct: number; up_count: number; down_count: number; leader: string; leader_change: number }>
    total: number
}

export interface BriefingHotStock {
    code: string
    name: string
    change_pct: number
    turnover: number
    reason: string
    amount: number
}

export interface BriefingGlobalNewsItem {
    title: string
    summary: string
    time: string
}

export interface BriefingMacroData {
    pmi?: { date: string; manufacturing: number; non_manufacturing: number }
    cpi?: { date: string; national_yoy: number }
    social_financing?: { date: string; value_yi: number }
}

export interface BriefingNewsItem {
    title: string
    content_preview: string
    source: string
}

export interface BriefingWatchlistItem {
    symbol: string
    name: string
    notes?: string
    latest_price?: number | null
    change_pct?: number | null
    news_summary: string
    signals: Array<{ name: string; value: string; interpretation: string }>
}

export interface BriefingPortfolioItem {
    symbol: string
    name: string
    position: number
    avg_cost: number
    current_price?: number | null
    market_value: number
    pnl?: number | null
    pnl_pct?: number | null
    risk_signals: string[]
}

export interface WatchlistPlanItem {
    股票: string
    策略类型: string
    入场条件: string
    理由: string
}

export interface PortfolioPlanItem {
    股票: string
    盈亏: string
    止盈条件: string
    止损条件: string
    建议: string
}

export interface BriefingTradingAdvice {
    content?: string
    sentiment: string
    watchlist_plan: WatchlistPlanItem[]
    portfolio_plan: PortfolioPlanItem[]
    error?: string
}

export interface BriefingDetailResponse {
    id: string
    date: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    error?: string | null
    market_data?: BriefingMarketData | null
    top_news?: BriefingNewsItem[] | null
    watchlist_analysis?: BriefingWatchlistItem[] | null
    portfolio_analysis?: BriefingPortfolioItem[] | null
    trading_advice?: BriefingTradingAdvice | null
    generated_at?: string | null
    created_at?: string | null
}

export interface BriefingListResponse {
    items: BriefingItem[]
}

export interface YangYinHistoryPoint {
    trade_date: string
    yang_pct: number
    yin_pct: number
    updated_at?: string
}

export interface GoldFingerPoint {
    trade_date: string
    signal: number   // 1 = 金, 0 = 银
    prob: number
}

export interface RedGreenBgPoint {
    trade_date: string
    background: string  // "红" | "绿"
    gs_signal: string   // "G" | "S"
    a_line: number
    bb_line: number
}

// Bias Analysis Types (乖离率分析)
export interface BiasStats {
    mean: number
    median: number
    std: number
    max_val: number
    min_val: number
    skewness: number
    quantile_10: number
    quantile_25: number
    quantile_75: number
    quantile_90: number
}

export interface BiasProbabilityRow {
    threshold_label: string
    threshold_value: number
    day_1_pct: number
    day_3_pct: number
    day_5_pct: number
    day_10_pct: number
    day_10_avg_ret: number
    sample_count: number
}

export interface BiasPoint {
    date: string
    close: number
    ma13: number
    bias_pct: number
    zj_bias?: number | null
}

export interface BiasAnalysisResponse {
    symbol: string
    name?: string
    start_date: string
    end_date: string
    total_days: number
    stats: BiasStats
    points: BiasPoint[]
    distribution: Record<string, number>
    pullback_after_high: BiasProbabilityRow[]
    rebound_after_low: BiasProbabilityRow[]
    pullback_summary: string
    rebound_summary: string
}

export interface BiasSnapshotResponse {
    symbol: string
    name?: string | null
    price: number
    change_pct: number
    ma13: number
    bias_pct: number
    zj_bias?: number | null
    timestamp: string
    market_phase: string  // pre_open | in_session | lunch_break | post_close | closed
}

// 39-Rules Strategy Decision Types
export interface StrategyDecisionResponse {
    symbol: string
    name: string
    market_state: string
    phase: string
    phase_reasoning: string
    effort_result: string
    checklist_score: string
    paths: {
        bullish: string
        neutral: string
        bearish: string
    }
    final_action: string
    confidence: string
    summary: string
}
