// Feature 016 (US1): pure client-side helpers for the momentum cockpit.
//
// These are deterministic, presentation-only projections over the board the
// backend already returns — they never change a gate, level, or sizing number.
// The cumulative-heat helper answers "if I took these fit-ranked candidates in
// order, past which one would the portfolio-heat ceiling bind?"; the
// sector-clustering helper flags candidates that would pile into one sector.

import type { PipelineBoardItem, PortfolioHoldingWithLevels } from './api';

export interface CumulativeHeat {
  /** Running portfolio-heat fraction after taking items[0..i] in order; null
   *  for items with no actionable size (skipped or zero shares). */
  cumulativeAfter: (number | null)[];
  /** Index of the first candidate whose entry would push cumulative heat past
   *  the ceiling, or null when the whole ranked list stays within budget. */
  bindingIndex: number | null;
}

function actionable(item: PipelineBoardItem): boolean {
  return (
    item.skipped_reason == null &&
    item.sizing_preview != null &&
    item.sizing_preview.suggested_shares > 0
  );
}

/**
 * Walk the (already fit-ranked) items accumulating each candidate's incremental
 * open risk on top of the existing portfolio heat, and mark where the ceiling
 * would bind. `ceilingPct`/`headroomPct` are the board-level values; existing
 * used heat = ceiling − headroom.
 */
export function computeCumulativeHeat(
  items: PipelineBoardItem[],
  ceilingPct: number,
  headroomPct: number,
): CumulativeHeat {
  const existingUsed = Math.max(ceilingPct - headroomPct, 0);
  let running = existingUsed;
  let bindingIndex: number | null = null;
  const cumulativeAfter: (number | null)[] = [];

  items.forEach((item, index) => {
    if (!actionable(item)) {
      cumulativeAfter.push(null);
      return;
    }
    const afterThis = item.sizing_preview?.portfolio_heat_after_pct ?? existingUsed;
    const incremental = Math.max(afterThis - existingUsed, 0);
    running += incremental;
    cumulativeAfter.push(running);
    if (bindingIndex === null && running > ceilingPct) {
      bindingIndex = index;
    }
  });

  return { cumulativeAfter, bindingIndex };
}

export interface SectorCluster {
  sector: string;
  tickers: string[];
}

/**
 * Group the actionable candidates by sector and return only the sectors where
 * more than one candidate clusters (a concentration the owner should notice
 * before taking several at once). Sorted for stable rendering.
 */
export function sectorClusters(items: PipelineBoardItem[]): SectorCluster[] {
  const bySector = new Map<string, string[]>();
  for (const item of items) {
    if (!actionable(item)) continue;
    const sector = item.sector || 'Unclassified';
    const tickers = bySector.get(sector) ?? [];
    tickers.push(item.ticker);
    bySector.set(sector, tickers);
  }
  return [...bySector.entries()]
    .filter(([, tickers]) => tickers.length > 1)
    .map(([sector, tickers]) => ({ sector, tickers }))
    .sort((a, b) => a.sector.localeCompare(b.sector));
}

// ---------------------------------------------------------------------------
// Feature 016 (US3): pure pipeline-stage selector.
//
// A momentum candidate/holding moves through the lifecycle
// watch → ready → staged → owned → managing → exited. Only `staged` and
// `exited` are manual overrides recorded in the frontend-owned pipeline store;
// every other stage is DERIVED from live facts (holdings, board timing,
// watchlist) so the badge can never contradict what the owner actually holds.
// ---------------------------------------------------------------------------

export type PipelineStage =
  | 'watching'
  | 'ready'
  | 'staged'
  | 'owned'
  | 'managing'
  | 'exited';

type HoldingLevels = NonNullable<PortfolioHoldingWithLevels['levels']>;
type HoldingRiskInfo = NonNullable<PortfolioHoldingWithLevels['risk']>;

/** The subset of a `/portfolio/holdings` row the stage selector reads. */
export interface StageHolding {
  status: 'open' | 'closed' | 'anomalous';
  levels?: HoldingLevels | null;
  risk?: HoldingRiskInfo | null;
}

/** Level-block statuses that escalate an open holding from `owned` to
 *  `managing`. `holding` (calm) and `insufficient_data` (missing data, not a
 *  management signal) deliberately do not. */
const ATTENTION_LEVEL_STATUSES = new Set(['stop_breached', 'target_reached', 'gains_protected']);

/**
 * An open holding needs attention (→ `managing`) when it is over its risk
 * budget or any of its level blocks has moved past a calm `holding` status.
 */
export function holdingNeedsAttention(holding: StageHolding): boolean {
  if (holding.risk?.over_risk) {
    return true;
  }
  const levels = holding.levels;
  if (!levels) {
    return false;
  }
  const blocks = [levels.original_plan, levels.current_condition, levels.trailing];
  return blocks.some((block) => block != null && ATTENTION_LEVEL_STATUSES.has(block.status));
}

export interface StageInputs {
  /** Manual override from the frontend-owned pipeline store (the only manual stages). */
  manualStage?: 'staged' | 'exited';
  /** The matching `/portfolio/holdings` row, when the owner holds this ticker. */
  holding?: StageHolding | null;
  /** Live board / analyze entry-timing state for this ticker, if known. */
  entryTimingState?: string | null;
  /** Whether the ticker is on the (non-dismissed) watchlist. */
  onWatchlist?: boolean;
}

/**
 * Resolve the single pipeline stage for a ticker.
 *
 * Precedence (highest first): holdings-derived (owned/managing) > exited >
 * ready > staged > watching. Holdings-derived always wins, so a stale board
 * that still reports `entry_ready` never flickers a held name back to `ready`.
 * Returns `null` when nothing is known about the ticker.
 */
export function derivePipelineStage(input: StageInputs): PipelineStage | null {
  const { manualStage, holding, entryTimingState, onWatchlist } = input;

  if (holding && holding.status === 'open') {
    return holdingNeedsAttention(holding) ? 'managing' : 'owned';
  }
  if (manualStage === 'exited') {
    return 'exited';
  }
  if (entryTimingState === 'entry_ready') {
    return 'ready';
  }
  if (manualStage === 'staged') {
    return 'staged';
  }
  if (onWatchlist) {
    return 'watching';
  }
  return null;
}

/** Stable store key for a `${strategy}-${ticker}` pipeline entry. */
export function pipelineKey(strategySlug: string, ticker: string): string {
  return `${strategySlug}-${ticker}`;
}
