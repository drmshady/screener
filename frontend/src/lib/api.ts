import { z } from 'zod';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchApi<T>(endpoint: string, schema: z.ZodType<T>, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const data = await response.json();
  return schema.parse(data);
}

export const ModificationSchema = z.object({
  name: z.string(),
  description: z.string(),
  citation: z.string(),
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
  rank: z.number(),
  score: z.number(),
  reason: z.string(),
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
  data_notes: z.array(z.string()).optional().default([]),
  data_as_of: z.string(),
  disclaimer: z.string(),
});

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

export const BacktestResponseSchema = z.object({
  strategy_slug: z.string(),
  data_window_start: z.string(),
  data_window_end: z.string(),
  window_meets_v1_floor: z.boolean(),
  limited_window_warning: z.string().nullable(),
  data_sources: z.array(z.object({ source_name: z.string(), source_as_of: z.string() })),
  bias_check: z.array(z.object({ item: z.string(), passed: z.boolean(), note: z.string() })),
  coverage_notes: z.array(z.string()).optional(),
  yearly_metrics: z.array(
    z.object({
      year: z.number(),
      trades: z.number(),
      hit_rate: z.number(),
      avg_win: z.number(),
      avg_loss: z.number(),
      total_return: z.number(),
      max_drawdown: z.number(),
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
});

export const SizingResponseSchema = z.object({
  suggested_shares: z.number(),
  suggested_position_value: z.string(),
  resulting_position_pct_of_capital: z.number(),
  resulting_sector_pct_of_capital: z.number(),
  caps_respected: z.boolean(),
  reasoning: z.string(),
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
  data_as_of: z.string(),
  disclaimer: z.string(),
});
export type DataRefreshResponse = z.infer<typeof DataRefreshResponseSchema>;

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
export type SourceMeta = z.infer<typeof SourceMetaSchema>;
export type MetaResponse = z.infer<typeof MetaResponseSchema>;
