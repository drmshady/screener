// Feature 016 (US1): pure client-side helpers for the momentum cockpit.
//
// These are deterministic, presentation-only projections over the board the
// backend already returns — they never change a gate, level, or sizing number.
// The cumulative-heat helper answers "if I took these fit-ranked candidates in
// order, past which one would the portfolio-heat ceiling bind?"; the
// sector-clustering helper flags candidates that would pile into one sector.

import type { PipelineBoardItem } from './api';

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
