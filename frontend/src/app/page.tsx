"use client";

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { DataFreshnessPanel } from '@/components/DataFreshnessPanel';
import { MarketEventsPanel } from '@/components/MarketEventsPanel';
import { RegimePanel } from '@/components/RegimePanel';
import { HeatGauge } from '@/components/cockpit/HeatGauge';
import { ReadyFitList } from '@/components/cockpit/ReadyFitList';
import { fetchPipelineBoard, type PipelineBoardResponse } from '@/lib/api';
import { computeCumulativeHeat, sectorClusters } from '@/lib/pipeline';
import { PAGE_SHELL } from '@/lib/design';
import { useAppStore } from '@/lib/store';

const MOMENTUM_SLUG = 'midterm_52w_high_momentum';

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

export default function Home() {
  const watchlist = useAppStore((state) => state.watchlist);
  const totalCapital = useAppStore((state) => state.portfolio.total_capital);
  const cashOverride = useAppStore((state) => state.portfolio.cash_balance_override);
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

  // Kept `loading` as the initial state and only transitioned in the async
  // callbacks (never a synchronous setState in the effect body): on a refetch
  // the previous board stays until the new one resolves — no flash, and the
  // 404 (flag-off) / error paths both degrade to today's panels.
  const [state, setState] = useState<BoardState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;
    fetchPipelineBoard({
      tickers: tickersKey ? tickersKey.split(',') : [],
      total_capital: String(totalCapital),
      available_cash: cashOverride != null ? String(cashOverride) : null,
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
  }, [tickersKey, totalCapital, cashOverride, perPositionCap, perSectorCap]);

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

      {state.status === 'unavailable' ? <FallbackLinks /> : null}
    </main>
  );
}
