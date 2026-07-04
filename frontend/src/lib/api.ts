import { z } from 'zod';

const API_BASE_URL = '/api/proxy';

export function apiBaseUrlForTest() {
  return API_BASE_URL;
}

const TRUTHY = new Set(['1', 'true', 'yes', 'on']);

export function hostedModeEnabled(): boolean {
  return TRUTHY.has(
    (process.env.NEXT_PUBLIC_SCREENER_HOSTED_MODE ?? process.env.SCREENER_HOSTED_MODE ?? '0')
      .trim()
      .toLowerCase(),
  );
}

export class ApiError extends Error {
  status?: number;
  retryable: boolean;

  constructor(message: string, options?: { status?: number; retryable?: boolean; cause?: unknown }) {
    super(message);
    this.name = 'ApiError';
    this.status = options?.status;
    this.retryable = options?.retryable ?? false;
    if (options?.cause !== undefined) {
      this.cause = options.cause;
    }
  }
}

async function responseErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string' && body.detail.trim()) {
      return body.detail;
    }
    if (Array.isArray(body?.detail) && body.detail.length) {
      return 'The request could not be completed. Check the inputs and retry.';
    }
    if (typeof body?.message === 'string' && body.message.trim()) {
      return body.message;
    }
  } catch {
    // Fall through to status-based copy.
  }
  return `The backend returned ${response.status}. Retry when the service is available.`;
}

export async function fetchApi<T>(endpoint: string, schema: z.ZodType<T>, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
  } catch (error) {
    throw new ApiError('The backend is unreachable. Check the service and retry.', {
      retryable: true,
      cause: error,
    });
  }

  if (!response.ok) {
    throw new ApiError(await responseErrorMessage(response), {
      status: response.status,
      retryable: response.status === 408 || response.status === 429 || response.status >= 500,
    });
  }

  const data = await response.json();
  return schema.parse(data);
}

export const ModificationSchema = z.object({
  name: z.string(),
  description: z.string(),
  citation: z.string(),
});

export const DataIntegrityWarningSchema = z.object({
  figure: z.string().nullable().optional(),
  rule: z.string(),
  reason: z.string(),
});

export const EntryTimingSchema = z.object({
  state: z.enum(['entry_ready', 'not_entry_ready', 'entry_undetermined']),
  components: z.array(
    z.object({
      name: z.enum([
        'pivot_proximity',
        'trend',
        'volume_confirmation',
        'base_maturity',
        'base_depth',
        'not_extended',
      ]),
      status: z.enum(['pass', 'fail', 'undetermined']),
      value: z.number().nullable().optional(),
      reason: z.string(),
    }),
  ),
  disqualifiers: z
    .array(
      z.object({
        name: z.enum(['climax_top', 'huge_gap', 'short_lived_catalyst']),
        triggered: z.boolean(),
        value: z.number().nullable().optional(),
        reason: z.string(),
        forces_not_entry_ready: z.boolean(),
      }),
    )
    .optional()
    .default([]),
  diagnostics: z.object({
    pivot: z.number().nullable().optional(),
    base_type: z.enum(['flat', 'cup', 'cup_with_handle', 'double_bottom', 'none']).nullable().optional(),
    base_length_weeks: z.number().nullable().optional(),
    base_depth: z.number().nullable().optional(),
    breakout_volume_ratio: z.number().nullable().optional(),
    dist_above_pivot: z.number().nullable().optional(),
    dist_above_sma_200: z.number().nullable().optional(),
  }),
  summary: z.string(),
});

export const StrategySchema = z.object({
  slug: z.string(),
  name: z.string(),
  timeframe: z.string(),
  citation: z.string(),
  description: z.string(),
  holding_period_days: z.record(z.string(), z.number()),
  parameters: z.record(z.string(), z.unknown()),
  regime_favorability: z.record(z.string(), z.string()),
  default_exclude_earnings_within_days: z.number(),
  enabled_by_default: z.boolean(),
  modifications: z.array(ModificationSchema),
  backtest_summary: z
    .object({
      data_window_start: z.string(),
      data_window_end: z.string(),
      total_return: z.number(),
      max_drawdown: z.number(),
      hit_rate: z.number(),
      avg_win: z.number(),
      avg_loss: z.number(),
      turnover: z.number(),
      source_name: z.string(),
      source_as_of: z.string(),
    })
    .nullable()
    .optional(),
});

export const CandidateSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  sector: z.string(),
  strategy_slug: z.string().nullable().optional(),
  strategy_name: z.string().nullable().optional(),
  timeframe: z.string().nullable().optional(),
  current_price: z.string(),
  entry: z.string(),
  stop_loss: z.string(),
  tighter_stop_loss: z.string().nullable().optional(),
  take_profit: z.string(),
  // Feature 011 (US2): bounded-levels metadata
  risk_distance: z.number().nullable().optional(),
  reward_distance: z.number().nullable().optional(),
  reward_ceiling_basis: z.string().nullable().optional(),
  bounds_applied: z.array(z.string()).optional().default([]),
  levels_state: z.string().nullable().optional(),
  rationale: z.string().nullable().optional(),
  rank: z.number(),
  score: z.number(),
  reason: z.string(),
  return_12_1: z.number().nullable().optional(),
  vol_scalar: z.number().nullable().optional(),
  dist_to_high: z.number().nullable().optional(),
  atr: z.number().nullable().optional(),
  debt_to_equity: z.number().nullable().optional(),
  fcf_ttm: z.number().nullable().optional(),
  gp_to_assets: z.number().nullable().optional(),
  asset_growth: z.number().nullable().optional(),
  gate_results: z
    .array(
      z.object({
        gate: z.string(),
        status: z.enum(['pass', 'fail', 'skipped', 'warn']),
        detail: z.string(),
      }),
    )
    .optional()
    .default([]),
  warnings: z.array(z.string()).optional().default([]),
  entry_timing: EntryTimingSchema.nullable().optional(),
  skipped_gates: z
    .array(
      z.object({
        gate: z.string(),
        reason: z.string(),
      }),
    )
    .optional()
    .default([]),
  // Feature 008: integrity warnings (data-model §5).
  data_integrity_warnings: z.array(DataIntegrityWarningSchema).optional().default([]),
  data_suspect: z.boolean().optional().default(false),
  // Value-composite diagnostics (midterm_value_composite); null/absent otherwise.
  value_composite: z.number().nullable().optional(),
  book_to_market: z.number().nullable().optional(),
  earnings_yield: z.number().nullable().optional(),
  cashflow_yield: z.number().nullable().optional(),
  sales_yield: z.number().nullable().optional(),
  f_score: z.number().nullable().optional(),
  f_score_evaluable: z.number().nullable().optional(),
  // Feature 011 (US3): fair-value estimate + trust flag
  fair_value: z.number().nullable().optional(),
  fair_value_basis: z.string().nullable().optional(),
  fair_value_trust_flag: z.string().nullable().optional(),
  shariah_compliant: z.boolean().nullable().optional(),
  shariah_source_kind: z.string().nullable().optional(),
  shariah_external_source_name: z.string().nullable().optional(),
  shariah_source_as_of: z.string().nullable().optional(),
  shariah_source_url: z.string().nullable().optional(),
  shariah_user_note: z.string().nullable().optional(),
  shariah_is_stale: z.boolean().nullable().optional(),
  next_earnings_date: z.string().nullable().optional(),
  days_to_earnings: z.number().nullable().optional(),
  recent_8k_count_30d: z.number(),
  events_source_as_of: z.string().nullable().optional(),
  // §8 Series-integrity signals
  series_dates_ok: z.boolean().nullable().optional(),
  series_max_session_move: z.number().nullable().optional(),
  seam_consistent: z.boolean().nullable().optional(),
  seam_factor: z.number().nullable().optional(),
  corporate_action_in_window: z.boolean().nullable().optional(),
  adj_close_basis_used: z.boolean().nullable().optional(),
  share_class_consistent: z.boolean().nullable().optional(),
});

export const ScreenResultSchema = z.object({
  id: z.string(),
  strategy_slug: z.string(),
  as_of_date: z.string(),
  parameters_snapshot: z.record(z.string(), z.unknown()),
  filters_snapshot: z.record(z.string(), z.unknown()),
  candidate_count: z.number(),
  candidates: z.array(CandidateSchema),
  computed_at: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
  stale_sources: z.array(z.string()).optional(),
  data_notes: z.array(z.string()).optional(),
  regime: z.string().nullable().optional(),
  regime_allows_new_entries: z.boolean().nullable().optional(),
  regime_note: z.string().nullable().optional(),
});

export const AnalyzeResponseSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  sector: z.string(),
  strategy: z.string(),
  as_of: z.string(),
  would_be_selected: z.boolean(),
  current_price: z.string(),
  entry: z.string(),
  stop_loss: z.string(),
  tighter_stop_loss: z.string().nullable().optional(),
  take_profit: z.string(),
  gate_results: z.array(
    z.object({
      gate: z.string(),
      status: z.enum(['pass', 'fail', 'skipped', 'warn']),
      detail: z.string(),
    }),
  ),
  entry_timing: EntryTimingSchema.nullable().optional(),
  value_composite: z.number().nullable().optional(),
  book_to_market: z.number().nullable().optional(),
  earnings_yield: z.number().nullable().optional(),
  cashflow_yield: z.number().nullable().optional(),
  sales_yield: z.number().nullable().optional(),
  f_score: z.number().nullable().optional(),
  f_score_evaluable: z.number().nullable().optional(),
  data_integrity_warnings: z.array(DataIntegrityWarningSchema).optional().default([]),
  data_suspect: z.boolean().optional().default(false),
  data_notes: z.array(z.string()).optional().default([]),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const AdvisorPromptResponseSchema = z.object({
  ticker: z.string(),
  strategy: z.string(),
  personal_use_directive: z.boolean(),
  prompt: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const ScreenAdvisorPromptResponseSchema = z.object({
  strategy: z.string(),
  candidate_count: z.number(),
  personal_use_directive: z.boolean(),
  prompt: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const IndependentVerifyResponseSchema = z.object({
  ticker: z.string(),
  screener_price: z.number().nullable().optional(),
  screener_52w_high: z.number().nullable().optional(),
  independent_price: z.number().nullable().optional(),
  independent_52w_high: z.number().nullable().optional(),
  independent_source: z.string(),
  divergence_pct: z.number().nullable().optional(),
  verdict: z.string(),
  screener_flagged: z.boolean().optional().default(false),
  key_configured: z.boolean().optional().default(false),
  fetched_at: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});
export type IndependentVerifyResponse = z.infer<typeof IndependentVerifyResponseSchema>;

export async function verifyCandidate(ticker: string): Promise<IndependentVerifyResponse> {
  return fetchApi(`/candidate/${encodeURIComponent(ticker)}/verify`, IndependentVerifyResponseSchema);
}

export const TickerEventSchema = z.object({
  ticker: z.string().nullable().optional(),
  event_type: z.string(),
  event_date: z.string(),
  event_time: z.string().nullable().optional(),
  source_name: z.string(),
  source_as_of: z.string().nullable().optional(),
  source_url: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export const EventSourceStatusSchema = z.object({
  source_name: z.string(),
  source_as_of: z.string(),
  is_stale: z.boolean(),
});

export const MarketEventSchema = z.object({
  event_id: z.string(),
  event_type: z.string(),
  scheduled_at: z.string(),
  expected_value: z.string().nullable().optional(),
  actual_value: z.string().nullable().optional(),
  status: z.string(),
  source_url: z.string(),
});

export const MarketEventsResponseSchema = z.object({
  events: z.array(MarketEventSchema),
  source_name: z.string(),
  source_as_of: z.string(),
  is_stale: z.boolean(),
  schedule_extends_through: z.string().nullable().optional(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const TickerEventsResponseSchema = z.object({
  ticker: z.string(),
  next_earnings_date: z.string().nullable().optional(),
  days_to_earnings: z.number().nullable().optional(),
  recent_8k_count_30d: z.number(),
  events: z.array(TickerEventSchema),
  sources: z.array(EventSourceStatusSchema),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const StrategiesResponseSchema = z.object({
  strategies: z.array(StrategySchema),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const SourceMetaSchema = z.object({
  source_name: z.string(),
  kind: z.string(),
  source_as_of: z.string(),
  is_stale: z.boolean(),
  refresh_interval_days: z.number(),
  source_url: z.string().nullable().optional(),
  last_success_at: z.string().nullable().optional(),
  last_bar_date: z.string().nullable().optional(),
  display_name: z.string().nullable().optional(),
});

export const MetaResponseSchema = z.object({
  sources: z.array(SourceMetaSchema),
  disclaimer: z.string(),
  data_as_of: z.string().optional(),
});

export const DataFreshnessSourceSchema = z.object({
  source_name: z.string(),
  kind: z.string(),
  data_as_of: z.string().nullable(),
  latest_session: z.string(),
  sessions_behind: z.number().nullable(),
  is_stale: z.boolean(),
  last_refresh_outcome: z.string(),
});

export const DataFreshnessResponseSchema = z.object({
  sources: z.array(DataFreshnessSourceSchema),
  any_stale: z.boolean(),
  latest_session: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const BacktestResponseSchema = z.object({
  strategy_slug: z.string(),
  data_window_start: z.string(),
  data_window_end: z.string(),
  window_meets_v1_floor: z.boolean(),
  limited_window_warning: z.string().nullable(),
  data_sources: z.array(z.object({ source_name: z.string(), source_as_of: z.string() })),
  bias_check: z.array(z.object({ item: z.string(), passed: z.boolean(), note: z.string() })),
  coverage_notes: z.array(z.string()).optional(),
  // Feature 015 (US1/US7): cadence + disclosed cost model surfaced read-only.
  rebalance_cadence: z.string().nullable().optional(),
  cost_model: z
    .object({ per_side_bps: z.number(), applied: z.boolean() })
    .nullable()
    .optional(),
  yearly_metrics: z.array(
    z.object({
      year: z.number(),
      trades: z.number(),
      hit_rate: z.number(),
      avg_win: z.number(),
      avg_loss: z.number(),
      total_return: z.number(),
      max_drawdown: z.number(),
      // Feature 015 (US1/US7): per-year trade count + thin-sample reliability flag.
      trade_count: z.number().nullable().optional(),
      reliability: z.enum(['ok', 'low_sample']).nullable().optional(),
    }),
  ),
  summary_metrics: z.object({
    total_return: z.number(),
    max_drawdown: z.number(),
    hit_rate: z.number(),
    avg_win: z.number(),
    avg_loss: z.number(),
    turnover: z.number(),
  }),
  code_version: z.string().optional(),
  computed_at: z.string().optional(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const EquityCurveResponseSchema = z.object({
  strategy_slug: z.string(),
  points: z.array(
    z.object({
      step: z.number(),
      equity: z.number(),
    }),
  ),
  data_window_start: z.string().nullable().optional(),
  data_window_end: z.string().nullable().optional(),
  data_sources: z.array(z.object({ source_name: z.string(), source_as_of: z.string() })),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const CandidateDetailSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  sector: z.string(),
  current_price: z.string(),
  matches: z.array(CandidateSchema),
  events: z.array(TickerEventSchema),
  shariah: z.object({
    ticker: z.string(),
    is_compliant: z.boolean(),
    source_kind: z.string(),
    external_source_name: z.string().nullable(),
    external_source_as_of: z.string().nullable(),
    is_stale: z.boolean(),
    source_url: z.string().nullable(),
    user_note: z.string().nullable(),
    conflict: z.boolean().optional(),
    active_sources: z.array(z.string()).optional(),
  }),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const CandidateHistoryResponseSchema = z.object({
  ticker: z.string(),
  points: z.array(
    z.object({
      date: z.string(),
      close: z.number(),
      high: z.number(),
      low: z.number(),
      sma_200: z.number().nullable().optional(),
      high_52w: z.number().nullable().optional(),
    }),
  ),
  source_name: z.string(),
  source_as_of: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const ShariahStatusSchema = z.object({
  ticker: z.string(),
  is_compliant: z.boolean(),
  source_kind: z.string(),
  external_source_name: z.string().nullable().optional(),
  external_source_as_of: z.string().nullable().optional(),
  is_stale: z.boolean(),
  source_url: z.string().nullable().optional(),
  user_note: z.string().nullable().optional(),
  conflict: z.boolean().optional(),
  active_sources: z.array(z.string()).optional(),
  data_as_of: z.string().optional(),
  disclaimer: z.string().optional(),
});

export const SizingHoldingSchema = z.object({
  ticker: z.string(),
  shares: z.string(),
  current_price: z.string(),
  sector: z.string(),
});

export const SizingRequestSchema = z.object({
  candidate_ticker: z.string(),
  entry: z.string(),
  candidate_sector: z.string(),
  total_capital: z.string(),
  holdings: z.array(SizingHoldingSchema),
  caps: z
    .object({
      per_position_cap_pct: z.number(),
      per_sector_cap_pct: z.number(),
    })
    .optional(),
  // Feature 016 (US2): optional cash-first hard limit (Decimal string).
  available_cash: z.string().nullable().optional(),
});

export const SizingResponseSchema = z.object({
  suggested_shares: z.number(),
  suggested_position_value: z.string(),
  resulting_position_pct_of_capital: z.number(),
  resulting_sector_pct_of_capital: z.number(),
  caps_respected: z.boolean(),
  reasoning: z.string(),
  // Feature 011 (US3): risk-per-trade + conviction-modulation metadata
  risk_per_trade_target: z.string().nullable().optional(),
  risk_per_share: z.string().nullable().optional(),
  conviction_signal: z.string().nullable().optional(),
  conviction_adjustment: z.string().nullable().optional(),
  // "risk_target" | "conviction" | "position_cap" | "sector_cap" | "portfolio_heat" |
  // "conservative_fallback" | "available_cash" (Feature 016 US2)
  binding_constraint: z.string().nullable().optional(),
  conviction_used: z.boolean().optional().default(false),
  // Feature 015 (US4/US7): safe-fallback + portfolio-heat metadata (additive).
  conservative_fallback: z.boolean().optional().default(false),
  reward_to_risk: z.number().nullable().optional(),
  portfolio_heat_after_pct: z.number().nullable().optional(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const PortfolioQuotesRequestSchema = z.object({
  holdings: z.array(
    z.object({
      ticker: z.string(),
      strategy_slug: z.string().optional(),
    }),
  ),
});

export const PortfolioQuoteSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  sector: z.string(),
  strategy_slug: z.string(),
  latest_price: z.string().nullable().optional(),
  entry: z.string().nullable().optional(),
  stop_loss: z.string().nullable().optional(),
  tighter_stop_loss: z.string().nullable().optional(),
  take_profit: z.string().nullable().optional(),
  is_stale: z.boolean(),
  data_notes: z.array(z.string()).optional().default([]),
  data_as_of: z.string(),
});

export const PortfolioQuotesResponseSchema = z.object({
  quotes: z.array(PortfolioQuoteSchema),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

const NullableNumberLikeSchema = z
  .union([z.string(), z.number()])
  .nullable()
  .optional();

export const RegimeResponseSchema = z.object({
  regime: z.enum(['Trending up', 'Range-bound', 'Trending down']),
  rule_summary: z.string(),
  inputs: z.object({
    spy_close: NullableNumberLikeSchema,
    spy_sma200: NullableNumberLikeSchema,
    spy_above_sma200: z.boolean().nullable().optional(),
    breadth_pct_above_sma200: z.number().nullable().optional(),
    breadth_above_count: z.number(),
    breadth_eligible_count: z.number(),
    breadth_total_constituents: z.number(),
    price_source_name: z.string(),
    unavailable_reason: z.string().nullable().optional(),
    breadth_source_name: z.string(),
    breadth_source_as_of: z.string().nullable().optional(),
  }),
  as_of_date: z.string(),
  per_strategy_favorability: z.array(
    z.object({
      slug: z.string(),
      name: z.string(),
      favorability: z.enum(['Favorable', 'Neutral', 'Unfavorable']),
      explanation: z.string(),
    }),
  ),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const SentimentSelectionSchema = z.object({
  ticker: z.string(),
  origin: z.enum(['screener', 'holding', 'manual']),
  as_of: z.string().nullable().optional(),
});

export const SentimentSourceSchema = z.object({
  id: z.string(),
  source_class: z.enum(['news', 'filing_8k', 'earnings', 'analyst_opinion', 'social']),
  title: z.string(),
  publisher: z.string().nullable().optional(),
  published_at: z.string(),
  reference_url: z.string().nullable().optional(),
  is_stale: z.boolean(),
  score: z.number().nullable().optional(),
});

export const SentimentReportItemSchema = z.object({
  ticker: z.string(),
  origin: z.enum(['screener', 'holding', 'manual']),
  label: z.enum(['positive', 'mixed', 'negative', 'no_signal']),
  label_basis: z.string().optional().default(''),
  sentiment_composite: z.number().nullable().optional(),
  narrative_risk: z
    .object({
      score: z.number(),
      label: z.string(),
      signals: z.array(z.string()),
    })
    .nullable()
    .optional(),
  narrative: z.string(),
  narrative_source: z.enum(['model', 'template', 'absent']),
  budget_state: z.enum(['ok', 'budget_exhausted', 'unavailable']),
  source_classes_present: z.array(z.string()).optional().default([]),
  source_classes_omitted: z.array(z.string()).optional().default([]),
  sources: z.array(SentimentSourceSchema),
  fingerprint: z.string(),
  resolution: z.string().nullable().optional(),
});

export const SentimentReportResponseSchema = z.object({
  reports: z.array(SentimentReportItemSchema),
  period_spend_usd: z.string(),
  monthly_cap_usd: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const PortfolioStateEnvelopeSchema = z.object({
  state: z.record(z.string(), z.unknown()).nullable().optional(),
  updated_at: z.string().nullable().optional(),
});

export async function getPortfolioState() {
  return fetchApi('/portfolio/state', PortfolioStateEnvelopeSchema);
}

export const DataRefreshResponseSchema = z.object({
  refreshed_tickers: z.number(),
  fetched_rows: z.number(),
  latest_bar: z.string().nullable().optional(),
  capped: z.boolean(),
  notices: z.array(z.string()).optional().default([]),
  data_as_of: z.string(),
  disclaimer: z.string(),
});
export type DataRefreshResponse = z.infer<typeof DataRefreshResponseSchema>;

export type DataFreshnessSource = z.infer<typeof DataFreshnessSourceSchema>;
export type DataFreshnessResponse = z.infer<typeof DataFreshnessResponseSchema>;

export async function getDataFreshness(): Promise<DataFreshnessResponse> {
  return fetchApi('/data/freshness', DataFreshnessResponseSchema);
}

export async function refreshData(market?: string): Promise<DataRefreshResponse> {
  const response = await fetch(`${API_BASE_URL}/data/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ market }),
  });
  if (!response.ok) {
    throw new Error(`Refresh failed: ${response.status}`);
  }
  return DataRefreshResponseSchema.parse(await response.json());
}

export async function putPortfolioState(state: unknown): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/portfolio/state`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ state }),
  });
  if (!response.ok) {
    throw new Error(`Persist failed: ${response.status}`);
  }
}

export async function postSizing(request: SizingRequest): Promise<{ status: number; result: SizingResponse }> {
  const response = await fetch(`${API_BASE_URL}/sizing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  const data = await response.json();
  const result = SizingResponseSchema.parse(data);
  if (!response.ok && response.status !== 422) {
    throw new Error(`API error: ${response.status}`);
  }
  return { status: response.status, result };
}

export type Candidate = z.infer<typeof CandidateSchema>;
export type EntryTiming = z.infer<typeof EntryTimingSchema>;
export type Strategy = z.infer<typeof StrategySchema>;
export type BacktestResponse = z.infer<typeof BacktestResponseSchema>;
export type EquityCurveResponse = z.infer<typeof EquityCurveResponseSchema>;
export type ScreenResult = z.infer<typeof ScreenResultSchema>;
export type AnalyzeResponse = z.infer<typeof AnalyzeResponseSchema>;
export type CandidateDetail = z.infer<typeof CandidateDetailSchema>;
export type CandidateHistoryResponse = z.infer<typeof CandidateHistoryResponseSchema>;
export type ShariahStatus = z.infer<typeof ShariahStatusSchema>;
export type TickerEvent = z.infer<typeof TickerEventSchema>;
export type MarketEvent = z.infer<typeof MarketEventSchema>;
export type MarketEventsResponse = z.infer<typeof MarketEventsResponseSchema>;
export type TickerEventsResponse = z.infer<typeof TickerEventsResponseSchema>;
export type SizingRequest = z.infer<typeof SizingRequestSchema>;
export type SizingResponse = z.infer<typeof SizingResponseSchema>;
export type PortfolioQuote = z.infer<typeof PortfolioQuoteSchema>;
export type PortfolioQuotesResponse = z.infer<typeof PortfolioQuotesResponseSchema>;
export type RegimeResponse = z.infer<typeof RegimeResponseSchema>;
export type SentimentSelection = z.infer<typeof SentimentSelectionSchema>;
export type SentimentReportItem = z.infer<typeof SentimentReportItemSchema>;
export type SentimentReportResponse = z.infer<typeof SentimentReportResponseSchema>;
export type AdvisorPromptResponse = z.infer<typeof AdvisorPromptResponseSchema>;
export type ScreenAdvisorPromptResponse = z.infer<typeof ScreenAdvisorPromptResponseSchema>;
export type SourceMeta = z.infer<typeof SourceMetaSchema>;
export type MetaResponse = z.infer<typeof MetaResponseSchema>;

// ---------------------------------------------------------------------------
// Feature 013: Portfolio import (POST /portfolio/import)
// ---------------------------------------------------------------------------

export const RejectedRowSchema = z.object({
  source_row: z.number(),
  raw: z.record(z.string(), z.unknown()),
  reason: z.string(),
});

export const ImportResultSchema = z.object({
  accepted_count: z.number(),
  duplicate_count: z.number(),
  rejected: z.array(RejectedRowSchema),
  transactions_total: z.number(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export type RejectedRow = z.infer<typeof RejectedRowSchema>;
export type ImportResult = z.infer<typeof ImportResultSchema>;

/**
 * POST /portfolio/import — validate and idempotently apply transaction rows.
 *
 * The browser reads the raw sheet rows via googleSheets.ts and passes them here.
 * The backend does all normalisation, validation, and deduplication.
 * Always resolves (partial success = success); throws only on network/5xx.
 */
export async function importTransactions(body: {
  rows: Record<string, unknown>[];
  sheet_id?: string;
  sheet_range?: string;
}): Promise<ImportResult> {
  return fetchApi('/portfolio/import', ImportResultSchema, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Feature 016 (US4): in-app buy/sell recording (POST/DELETE /portfolio/transactions)
// ---------------------------------------------------------------------------

/**
 * POST /portfolio/transactions — record one or more manual transactions.
 * Reuses the same row shape and ImportResult response as the Sheet import.
 */
export async function recordTransactions(
  rows: Record<string, unknown>[],
): Promise<ImportResult> {
  return fetchApi('/portfolio/transactions', ImportResultSchema, {
    method: 'POST',
    body: JSON.stringify({ rows }),
  });
}

/** DELETE /portfolio/transactions/{id} — remove one transaction and re-aggregate. */
export async function deleteTransaction(id: string): Promise<ImportResult> {
  return fetchApi(`/portfolio/transactions/${encodeURIComponent(id)}`, ImportResultSchema, {
    method: 'DELETE',
  });
}

// Feature 016 (US4): one FIFO realized round-trip (informational, neutral labels).
export const RealizedTradeSchema = z.object({
  ticker: z.string(),
  shares: z.string(),
  buy_date: z.string(),
  sell_date: z.string(),
  proceeds: z.string(),
  cost_basis: z.string(),
  fees: z.string(),
  realized_pnl: z.string(),
  outcome: z.enum(['win', 'loss', 'flat']),
  holding_days: z.number(),
});

export type RealizedTrade = z.infer<typeof RealizedTradeSchema>;

// ---------------------------------------------------------------------------
// Feature 013: Portfolio holdings with purchase-anchored levels
// ---------------------------------------------------------------------------

export const LevelBlockSchema = z.object({
  entry: z.string().nullable().optional(),
  stop_loss: z.string().nullable().optional(),
  tighter_stop_loss: z.string().nullable().optional(),
  take_profit: z.string().nullable().optional(),
  risk_distance: z.string().nullable().optional(),
  reward_distance: z.string().nullable().optional(),
  reward_ceiling_basis: z.string().nullable().optional(),
  bounds_applied: z.array(z.string()).optional().default([]),
  levels_state: z.enum(['ok', 'insufficient_data']),
  rationale: z.string(),
  distance_to_stop_pct: z.number().nullable().optional(),
  distance_to_target_pct: z.number().nullable().optional(),
  // Feature 015 (US3/US7): `gains_protected` — a trailing stop sitting above cost.
  status: z.enum([
    'holding',
    'stop_breached',
    'target_reached',
    'gains_protected',
    'insufficient_data',
  ]),
});

export const HoldingLevelsSchema = z.object({
  original_plan: LevelBlockSchema,
  current_condition: LevelBlockSchema,
  // Feature 015 (US3): a third, current-price-anchored trailing block from the
  // chandelier exit. Null when price <= cost or the chandelier value is missing.
  trailing: LevelBlockSchema.nullable().optional(),
});

export const HoldingRiskSchema = z.object({
  recommended_shares: z.number(),
  recommended_value: z.string(),
  actual_shares: z.string(),
  actual_value: z.string(),
  actual_capital_at_risk: z.string(),
  actual_capital_at_risk_pct: z.number(),
  per_trade_risk_budget: z.string(),
  over_risk: z.boolean(),
  binding_constraint: z.enum(['per_trade_budget', 'position_cap', 'sector_cap']).nullable().optional(),
  sizing_reasoning: z.string(),
  fail_open: z.boolean(),
});

export const PortfolioHoldingSchema = z.object({
  ticker: z.string(),
  net_quantity: z.string(),
  avg_cost: z.string(),
  cost_basis: z.string(),
  earliest_buy_date: z.string(),
  most_recent_buy_date: z.string(),
  realized_pl: z.string(),
  status: z.enum(['open', 'closed', 'anomalous']),
  priceable: z.boolean(),
  sector: z.string(),
  current_price: z.string().nullable().optional(),
  unrealized_pl: z.string().nullable().optional(),
  unrealized_pl_pct: z.number().nullable().optional(),
  data_notes: z.array(z.string()).optional().default([]),
  data_as_of: z.string().nullable().optional(),
  levels: HoldingLevelsSchema.nullable().optional(),
  risk: HoldingRiskSchema.nullable().optional(),
});

export const PortfolioTotalsSchema = z.object({
  total_invested: z.string(),
  total_capital_at_risk: z.string(),
  total_capital_at_risk_pct: z.number(),
  // Feature 015 (US4/US7): aggregate open-risk (portfolio heat) ceiling + headroom.
  heat_ceiling_pct: z.number().optional().default(0),
  heat_headroom_pct: z.number().optional().default(0),
  // Feature 016 (US4): additive/optional win/loss + mark-to-market P&L.
  realized_pnl: z.string().nullable().optional(),
  unrealized_pnl: z.string().nullable().optional(),
  total_pnl: z.string().nullable().optional(),
  win_rate: z.number().nullable().optional(),
  closed_trade_count: z.number().optional().default(0),
  winning_trade_count: z.number().optional().default(0),
});

export const PortfolioHoldingsResponseSchema = z.object({
  holdings: z.array(PortfolioHoldingSchema),
  totals: PortfolioTotalsSchema,
  // Feature 016 (US4): FIFO realized round-trip history (empty when no closed lots).
  realized_trades: z.array(RealizedTradeSchema).optional().default([]),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export type PortfolioTotals = z.infer<typeof PortfolioTotalsSchema>;

export type LevelBlock = z.infer<typeof LevelBlockSchema>;
export type HoldingRisk = z.infer<typeof HoldingRiskSchema>;
export type PortfolioHoldingWithLevels = z.infer<typeof PortfolioHoldingSchema>;
export type PortfolioHoldingsResponse = z.infer<typeof PortfolioHoldingsResponseSchema>;

export async function fetchHoldings(body: {
  total_capital: string;
  strategy_slug?: string;
  // Feature 016 (US2): optional cash-first limit threaded into per-holding sizing.
  available_cash?: string | null;
}): Promise<PortfolioHoldingsResponse> {
  return fetchApi('/portfolio/holdings', PortfolioHoldingsResponseSchema, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function postSentimentReport(body: {
  selections: SentimentSelection[];
}): Promise<SentimentReportResponse> {
  return fetchApi('/sentiment/report', SentimentReportResponseSchema, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// Feature 014: held-position advisor prompts. The backend builder is the single
// source of truth; these clients only fetch (and the component copies). Both
// reuse the same {total_capital} body the holdings table already sends.
export const HoldingAdvisorPromptResponseSchema = z.object({
  ticker: z.string(),
  strategy: z.string(),
  personal_use_directive: z.boolean(),
  prompt: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export const PortfolioAdvisorPromptResponseSchema = z.object({
  strategy: z.string(),
  holding_count: z.number(),
  personal_use_directive: z.boolean(),
  prompt: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export type HoldingAdvisorPromptResponse = z.infer<typeof HoldingAdvisorPromptResponseSchema>;
export type PortfolioAdvisorPromptResponse = z.infer<typeof PortfolioAdvisorPromptResponseSchema>;

export async function fetchPortfolioAdvisorPrompt(body: {
  total_capital: string;
  strategy_slug?: string;
}): Promise<PortfolioAdvisorPromptResponse> {
  return fetchApi('/portfolio/holdings/advisor-prompt', PortfolioAdvisorPromptResponseSchema, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function fetchHoldingAdvisorPrompt(
  ticker: string,
  body: { total_capital: string; strategy_slug?: string },
): Promise<HoldingAdvisorPromptResponse> {
  return fetchApi(
    `/portfolio/holdings/${encodeURIComponent(ticker)}/advisor-prompt`,
    HoldingAdvisorPromptResponseSchema,
    { method: 'POST', body: JSON.stringify(body) },
  );
}

// ---------------------------------------------------------------------------
// Feature 017 (US3): new watchlist advisor-prompt export in the screener format
// ---------------------------------------------------------------------------

export const WatchlistAdvisorPromptResponseSchema = z.object({
  strategy: z.string(),
  watched_count: z.number(),
  personal_use_directive: z.boolean(),
  prompt: z.string(),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export type WatchlistAdvisorPromptResponse = z.infer<typeof WatchlistAdvisorPromptResponseSchema>;

export async function fetchWatchlistAdvisorPrompt(body: {
  strategy_slug: string;
  tickers: string[];
  as_of?: string | null;
}): Promise<WatchlistAdvisorPromptResponse> {
  return fetchApi('/portfolio/watchlist/advisor-prompt', WatchlistAdvisorPromptResponseSchema, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Feature 013 (US4): live entry-timing status for a watchlist ticker
// ---------------------------------------------------------------------------

/**
 * Thin live entry-timing read-out for the "watch until entry-ready" view.
 * Reuses feature-012's `GET /analyze/{ticker}` (which already returns
 * `entry_timing`) and exposes only the timing block plus freshness/disclaimer.
 * No new backend logic (FR-021).
 */
export interface EntryStatus {
  ticker: string;
  entry_timing: EntryTiming | null;
  data_as_of: string;
  disclaimer: string;
}

export async function fetchEntryStatus(ticker: string, strategySlug: string): Promise<EntryStatus> {
  const query = new URLSearchParams({ strategy: strategySlug });
  const response = await fetchApi(
    `/analyze/${encodeURIComponent(ticker)}?${query.toString()}`,
    AnalyzeResponseSchema,
  );
  return {
    ticker: response.ticker,
    entry_timing: response.entry_timing ?? null,
    data_as_of: response.data_as_of,
    disclaimer: response.disclaimer,
  };
}

// ---------------------------------------------------------------------------
// Feature 016 (US1): momentum cockpit pipeline board
// ---------------------------------------------------------------------------
// Schemas widen additively: `directive_label` is optional (present only in the
// personal-use, non-hosted path), and the whole response 404s gracefully when
// the board is disabled (the home page falls back to today's panels).

export const FitFactsSchema = z.object({
  entry_ready: z.boolean(),
  meaningful_size_survives: z.boolean(),
  heat_headroom_ok: z.boolean(),
  sector_room_ok: z.boolean(),
  not_overconcentrated: z.boolean(),
  regime_allows_entries: z.boolean(),
  reward_to_risk_ok: z.boolean(),
  cash_sufficient: z.boolean(),
});

export const FitResultSchema = z.object({
  score: z.number(),
  fit_band: z.enum(['strong_fit', 'partial_fit', 'poor_fit', 'blocked']),
  facts: FitFactsSchema,
  failed_facts: z.array(z.string()).optional().default([]),
  rationale: z.string(),
  directive_label: z
    .enum(['consider_entry', 'hold_off', 'size_down', 'pass'])
    .nullable()
    .optional(),
});

export const PipelineBoardItemSchema = z.object({
  ticker: z.string(),
  entry_timing_state: z.string().nullable().optional(),
  sizing_preview: SizingResponseSchema.nullable().optional(),
  fit: FitResultSchema.nullable().optional(),
  sector: z.string().optional().default('Unclassified'),
  skipped_reason: z.string().nullable().optional(),
});

export const PipelineBoardResponseSchema = z.object({
  items: z.array(PipelineBoardItemSchema).optional().default([]),
  regime: z.record(z.string(), z.unknown()).nullable().optional(),
  regime_allows_new_entries: z.boolean().optional().default(false),
  heat_ceiling_pct: z.number().optional().default(0),
  heat_headroom_pct: z.number().optional().default(0),
  available_cash: z.string().nullable().optional(),
  personal_use_directive: z.boolean().optional().default(false),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

export type FitFacts = z.infer<typeof FitFactsSchema>;
export type FitResult = z.infer<typeof FitResultSchema>;
export type PipelineBoardItem = z.infer<typeof PipelineBoardItemSchema>;
export type PipelineBoardResponse = z.infer<typeof PipelineBoardResponseSchema>;

export interface PipelineBoardRequest {
  tickers: string[];
  strategy_slug?: string;
  total_capital: string;
  available_cash?: string | null;
  caps?: { per_position_cap_pct: number; per_sector_cap_pct: number };
}

/**
 * Fetch the momentum fit board. Throws an {@link ApiError} with status 404 when
 * the pipeline is disabled — callers should catch that and degrade gracefully
 * to today's home panels (no build-time env flag).
 */
export async function fetchPipelineBoard(
  body: PipelineBoardRequest,
): Promise<PipelineBoardResponse> {
  return fetchApi('/pipeline/board', PipelineBoardResponseSchema, {
    method: 'POST',
    body: JSON.stringify({ strategy_slug: 'midterm_52w_high_momentum', ...body }),
  });
}
