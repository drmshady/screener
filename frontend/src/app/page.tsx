"use client";

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { DataFreshnessPanel } from '@/components/DataFreshnessPanel';
import { MarketEventsPanel } from '@/components/MarketEventsPanel';
import { RegimePanel } from '@/components/RegimePanel';
import { HeatGauge } from '@/components/cockpit/HeatGauge';
import { ReadyFitList } from '@/components/cockpit/ReadyFitList';
import { AttentionList, type AttentionRow } from '@/components/cockpit/AttentionList';
import { TransitionAlert, type ReadyAlert } from '@/components/cockpit/TransitionAlert';
import { WatchingList, type WatchingRow } from '@/components/cockpit/WatchingList';
import {
  fetchHoldings,
  fetchPipelineBoard,
  type PipelineBoardResponse,
  type PortfolioHoldingWithLevels,
} from '@/lib/api';
import {
  computeCumulativeHeat,
  derivePipelineStage,
  holdingNeedsAttention,
  pipelineKey,
  sectorClusters,
  type StageHolding,
} from '@/lib/pipeline';
import { PAGE_SHELL } from '@/lib/design';
import { effectiveTotalCapital, useAppStore } from '@/lib/store';

const MOMENTUM_SLUG = 'midterm_52w_high_momentum';
const MS_PER_DAY = 24 * 60 * 60 * 1000;

type BoardState =
  | { status: 'loading' }
  | { status: 'ready'; board: PipelineBoardResponse }
  | { status: 'unavailable' };

/** Momentum-only quick links shown when the pipeline board is unavailable
 *  (flag off / backend error) — the graceful degradation path (FR-012, D7). */
function FallbackLinks() {
  return (
    <div className="grid gap-4 sm:grid-cols-2" data-testid="cockpit-fallback">
      <Link className="panel p-5 hover:border-slate-400" href={`/screen/${MOMENTUM_SLUG}`}>
        <div className="text-lg font-semibold text-slate-950">Mid-Term 52-Week High Momentum</div>
        <p className="mt-2 text-sm text-slate-600">
          Run the momentum screen with entries, stops, targets, citations, and backtest evidence.
        </p>
      </Link>
      <Link className="panel p-5 hover:border-slate-400" href="/watchlist">
        <div className="text-lg font-semibold text-slate-950">Watchlist</div>
        <p className="mt-2 text-sm text-slate-600">Review saved momentum candidates and captured levels.</p>
      </Link>
      <Link className="panel p-5 hover:border-slate-400" href="/portfolio">
        <div className="text-lg font-semibold text-slate-950">Portfolio</div>
        <p className="mt-2 text-sm text-slate-600">Review holdings, levels, and risk-aware sizing.</p>
      </Link>
      <Link className="panel p-5 hover:border-slate-400" href="/sentiment">
        <div className="text-lg font-semibold text-slate-950">Sentiment Report</div>
        <p className="mt-2 text-sm text-slate-600">Run a sourced narrative report for selected tickers.</p>
      </Link>
    </div>
  );
}

function toStageHolding(holding: PortfolioHoldingWithLevels): StageHolding {
  return { status: holding.status, levels: holding.levels, risk: holding.risk };
}

/** Neutral, descriptive reason an open holding surfaced in the attention list
 *  (no directive language, FR-020). */
function describeAttention(holding: PortfolioHoldingWithLevels): { message: string; severity: 'high' | 'medium' } {
  if (holding.risk?.over_risk) {
    return { message: 'Over its risk budget', severity: 'high' };
  }
  const blocks = [holding.levels?.current_condition, holding.levels?.original_plan, holding.levels?.trailing];
  for (const block of blocks) {
    if (block?.status === 'stop_breached') return { message: 'Stop level breached', severity: 'high' };
    if (block?.status === 'target_reached') return { message: 'Target level reached', severity: 'high' };
  }
  for (const block of blocks) {
    if (block?.status === 'gains_protected') {
      return { message: 'Trailing stop is protecting gains', severity: 'medium' };
    }
  }
  return { message: 'Level status changed', severity: 'medium' };
}

export default function Home() {
  const watchlist = useAppStore((state) => state.watchlist);
  const portfolio = useAppStore((state) => state.portfolio);
  const pipeline = useAppStore((state) => state.pipeline);
  const updatePipelineEntry = useAppStore((state) => state.updatePipelineEntry);
  const availableCash = portfolio.available_cash;
  const perPositionCap = useAppStore((state) => state.settings.per_position_cap_pct);
  const perSectorCap = useAppStore((state) => state.settings.per_sector_cap_pct);

  const tickers = useMemo(
    () =>
      watchlist
        .filter((entry) => entry.strategy_slug === MOMENTUM_SLUG && entry.state !== 'dismissed')
        .map((entry) => entry.ticker),
    [watchlist],
  );
  const tickersKey = tickers.join(',');
  const effectiveCapital = effectiveTotalCapital(portfolio);

  // Kept `loading` as the initial state and only transitioned in the async
  // callbacks (never a synchronous setState in the effect body): on a refetch
  // the previous board stays until the new one resolves — no flash, and the
  // 404 (flag-off) / error paths both degrade to today's panels.
  const [state, setState] = useState<BoardState>({ status: 'loading' });
  const [holdings, setHoldings] = useState<PortfolioHoldingWithLevels[]>([]);
  // Reference "now" for the ready-for-N-days counter, sampled in an effect so
  // render stays pure (React 19 hooks-purity rule); refreshed on each board load.
  const [nowMs, setNowMs] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchPipelineBoard({
      tickers: tickersKey ? tickersKey.split(',') : [],
      total_capital: String(effectiveCapital),
      available_cash: availableCash != null ? String(availableCash) : null,
      caps: { per_position_cap_pct: perPositionCap, per_sector_cap_pct: perSectorCap },
    })
      .then((board) => {
        if (!cancelled) setState({ status: 'ready', board });
      })
      .catch(() => {
        // 404 (flag off) or any backend error → degrade to today's panels.
        if (!cancelled) setState({ status: 'unavailable' });
      });
    return () => {
      cancelled = true;
    };
  }, [tickersKey, effectiveCapital, availableCash, perPositionCap, perSectorCap]);

  // Feature 016 (US3): the holdings-derived owned/managing stages + the
  // needs-attention list read the same purchase-anchored levels the portfolio
  // page shows. Server-derived from persisted transactions; graceful on error.
  useEffect(() => {
    let cancelled = false;
    fetchHoldings({
      total_capital: String(effectiveCapital || 1),
      strategy_slug: MOMENTUM_SLUG,
      available_cash: availableCash != null ? String(availableCash) : undefined,
    })
      .then((resp) => {
        if (!cancelled) setHoldings(resp.holdings);
      })
      .catch(() => {
        if (!cancelled) setHoldings([]);
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveCapital, availableCash]);

  const derived = useMemo(() => {
    if (state.status !== 'ready') return null;
    const { board } = state;
    return {
      board,
      cumulativeHeat: computeCumulativeHeat(
        board.items,
        board.heat_ceiling_pct,
        board.heat_headroom_pct,
      ),
      clusters: sectorClusters(board.items),
    };
  }, [state]);

  const holdingByTicker = useMemo(() => {
    const map = new Map<string, PortfolioHoldingWithLevels>();
    for (const holding of holdings) {
      map.set(holding.ticker.toUpperCase(), holding);
    }
    return map;
  }, [holdings]);

  // Track how long each watched candidate has been entry-ready. Writes to the
  // frontend-owned pipeline store only; the board (`derived`) does not depend on
  // it, so there is no update loop. Clears when a ticker is no longer ready.
  // Sample the reference clock for the ready-for-N-days counter, deferred out of
  // the synchronous effect body (React 19 no-setState-in-effect rule).
  useEffect(() => {
    const id = window.setTimeout(() => setNowMs(Date.now()), 0);
    return () => window.clearTimeout(id);
  }, [derived]);

  useEffect(() => {
    if (!derived) return;
    const store = useAppStore.getState();
    for (const item of derived.board.items) {
      const key = pipelineKey(MOMENTUM_SLUG, item.ticker);
      const entry = store.pipeline[key];
      const ready = item.entry_timing_state === 'entry_ready';
      if (ready && !entry?.ready_since) {
        store.updatePipelineEntry(key, { ready_since: new Date().toISOString() });
      } else if (!ready && (entry?.ready_since || entry?.acknowledged_ready_at)) {
        store.updatePipelineEntry(key, { ready_since: undefined, acknowledged_ready_at: undefined });
      }
    }
  }, [derived]);

  const boardByTicker = useMemo(() => {
    const map = new Map<string, string | null>();
    for (const item of derived?.board.items ?? []) {
      map.set(item.ticker.toUpperCase(), item.entry_timing_state ?? null);
    }
    return map;
  }, [derived]);

  // Readiness alerts: watched momentum candidates that are entry-ready and not
  // yet held, joined with the persisted ready-since / acknowledgement state.
  const readyAlerts = useMemo<ReadyAlert[]>(() => {
    const items = derived?.board.items ?? [];
    return items
      .filter((item) => {
        const held = holdingByTicker.get(item.ticker.toUpperCase());
        return item.entry_timing_state === 'entry_ready' && !(held && held.status === 'open');
      })
      .map((item) => {
        const entry = pipeline[pipelineKey(MOMENTUM_SLUG, item.ticker)];
        const readySince = entry?.ready_since;
        const days = readySince
          ? Math.max(0, Math.floor((nowMs - Date.parse(readySince)) / MS_PER_DAY))
          : 0;
        const acknowledged =
          entry?.acknowledged_ready_at != null &&
          (readySince == null || entry.acknowledged_ready_at >= readySince);
        return { ticker: item.ticker, days, acknowledged };
      });
  }, [derived, holdingByTicker, pipeline, nowMs]);

  const attentionRows = useMemo<AttentionRow[]>(
    () =>
      holdings
        .filter((holding) => holding.status === 'open' && holdingNeedsAttention(toStageHolding(holding)))
        .map((holding) => ({ ticker: holding.ticker, ...describeAttention(holding) })),
    [holdings],
  );

  const watchingRows = useMemo<WatchingRow[]>(
    () =>
      watchlist
        .filter((entry) => entry.strategy_slug === MOMENTUM_SLUG && entry.state !== 'dismissed')
        .map((entry) => {
          const held = holdingByTicker.get(entry.ticker.toUpperCase());
          const manualStage = pipeline[pipelineKey(MOMENTUM_SLUG, entry.ticker)]?.manual_stage;
          const stage = derivePipelineStage({
            manualStage,
            holding: held ? toStageHolding(held) : null,
            entryTimingState: boardByTicker.get(entry.ticker.toUpperCase()) ?? entry.last_entry_state ?? null,
            onWatchlist: true,
          });
          return { ticker: entry.ticker, sector: entry.sector, stage, manualStage };
        }),
    [watchlist, holdingByTicker, boardByTicker, pipeline],
  );

  function acknowledgeReady(ticker: string) {
    updatePipelineEntry(pipelineKey(MOMENTUM_SLUG, ticker), {
      acknowledged_ready_at: new Date().toISOString(),
    });
  }

  function setManualStage(ticker: string, stage: 'staged' | 'exited' | null) {
    updatePipelineEntry(pipelineKey(MOMENTUM_SLUG, ticker), { manual_stage: stage ?? undefined });
  }

  return (
    <main className={PAGE_SHELL.narrow} data-testid="cockpit-home">
      <header className={PAGE_SHELL.header}>
        <h1 className="text-2xl font-semibold text-slate-950">Momentum Cockpit</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          What is ready to enter and fits your portfolio right now — synthesised from the
          momentum screen, entry timing, sizing, and portfolio heat you already produce.
        </p>
        {derived ? (
          <p className="mt-1 text-xs text-slate-500">Board as of {derived.board.data_as_of}</p>
        ) : null}
      </header>

      <DataFreshnessPanel />
      <RegimePanel />
      <MarketEventsPanel daysAhead={60} />

      {state.status === 'loading' ? (
        <section className="panel p-5 text-sm text-slate-600">Loading the fit board…</section>
      ) : null}

      {derived ? (
        <>
          <TransitionAlert alerts={readyAlerts} onAcknowledge={acknowledgeReady} />
          <HeatGauge
            ceilingPct={derived.board.heat_ceiling_pct}
            headroomPct={derived.board.heat_headroom_pct}
          />
          <ReadyFitList
            items={derived.board.items}
            cumulativeHeat={derived.cumulativeHeat}
            clusters={derived.clusters}
          />
        </>
      ) : null}

      <AttentionList rows={attentionRows} />
      <WatchingList rows={watchingRows} onSetManualStage={setManualStage} />

      {state.status === 'unavailable' ? <FallbackLinks /> : null}
    </main>
  );
}
