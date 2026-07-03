"use client";

import Link from 'next/link';
import type { PipelineStage } from '@/lib/pipeline';
import { PipelineStageBadge } from './PipelineStageBadge';

export interface WatchingRow {
  ticker: string;
  sector?: string;
  stage: PipelineStage | null;
  /** The manual override currently recorded (so the controls reflect state). */
  manualStage?: 'staged' | 'exited';
}

/**
 * The full watchlist lifecycle view: every watched momentum ticker with its
 * derived pipeline stage and the two manual overrides the owner controls
 * (`staged` / `exited`). Derived stages (owned/managing/ready) always win, so
 * the manual controls are informational when a ticker is held or ready.
 * Empty state is an onboarding prompt (FR-014).
 */
export function WatchingList({
  rows,
  onSetManualStage,
}: {
  rows: WatchingRow[];
  onSetManualStage: (ticker: string, stage: 'staged' | 'exited' | null) => void;
}) {
  if (rows.length === 0) {
    return (
      <section className="panel space-y-2 p-5" data-testid="watching-list">
        <h2 className="text-lg font-semibold text-slate-950">Watching</h2>
        <p className="text-sm text-slate-600">
          Nothing on the watchlist yet. Save momentum candidates from a{' '}
          <Link className="underline underline-offset-2" href="/screen/midterm_52w_high_momentum">
            screen
          </Link>{' '}
          to track them through the pipeline.
        </p>
      </section>
    );
  }

  return (
    <section className="panel space-y-3 p-5" data-testid="watching-list">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-950">Watching</h2>
        <span className="text-xs text-slate-500">{rows.length} tracked</span>
      </div>
      <ul className="space-y-2">
        {rows.map((row) => (
          <li
            key={row.ticker}
            className="flex flex-wrap items-center justify-between gap-2 border border-slate-200 p-3 text-sm"
            data-testid="watching-row"
          >
            <div className="flex items-center gap-2">
              <Link
                className="font-semibold text-slate-950 underline-offset-2 hover:underline"
                href={`/candidate/${row.ticker}?strategy=midterm_52w_high_momentum`}
              >
                {row.ticker}
              </Link>
              {row.sector ? <span className="text-xs text-slate-500">{row.sector}</span> : null}
              <PipelineStageBadge stage={row.stage} />
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                className={`border px-2 py-1 text-xs font-medium ${
                  row.manualStage === 'staged'
                    ? 'border-sky-400 bg-sky-50 text-sky-900'
                    : 'border-slate-300 text-slate-700 hover:bg-slate-100'
                }`}
                onClick={() =>
                  onSetManualStage(row.ticker, row.manualStage === 'staged' ? null : 'staged')
                }
              >
                Staged
              </button>
              <button
                type="button"
                className={`border px-2 py-1 text-xs font-medium ${
                  row.manualStage === 'exited'
                    ? 'border-slate-400 bg-slate-100 text-slate-900'
                    : 'border-slate-300 text-slate-700 hover:bg-slate-100'
                }`}
                onClick={() =>
                  onSetManualStage(row.ticker, row.manualStage === 'exited' ? null : 'exited')
                }
              >
                Exited
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
