"use client";

import { useState } from 'react';
import { IndependentVerifyResponse, verifyCandidate } from '@/lib/api';

const VERDICT_STYLE: Record<string, string> = {
  AGREES: 'bg-emerald-100 text-emerald-800',
  DIVERGES_AND_FLAGGED: 'bg-amber-100 text-amber-900',
  DIVERGES_UNFLAGGED: 'bg-red-100 text-red-800',
  STALE: 'bg-slate-100 text-slate-700',
  UNVERIFIED: 'bg-slate-100 text-slate-600',
};

const VERDICT_NOTE: Record<string, string> = {
  AGREES: 'The independent vendor price is within 10% of the screener price.',
  DIVERGES_AND_FLAGGED:
    'The independent price diverges ≥10% and the screener already flagged this name — verify before acting.',
  DIVERGES_UNFLAGGED:
    'The independent price diverges ≥10% but the screener did NOT flag it — investigate the figure before acting.',
  STALE: 'The divergence is attributable to a genuinely old last bar (stale price).',
  UNVERIFIED:
    'No independent reading was available (no API key configured, or the vendor was unreachable).',
};

function pct(v: number | null | undefined) {
  return v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`;
}
function px(v: number | null | undefined) {
  return v === null || v === undefined ? '—' : `$${v.toFixed(2)}`;
}

export function IndependentVerify({ ticker }: { ticker: string }) {
  const [state, setState] = useState<IndependentVerifyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setState(await verifyCandidate(ticker));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Verification failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Independent data check</h2>
          <p className="text-xs text-slate-600">
            Cross-check this name&apos;s price and 52-week high against a third-party vendor
            (Finnhub / Alpha Vantage). On-demand — not part of the screen.
          </p>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={loading}
          className="shrink-0 border border-slate-950 bg-slate-950 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {loading ? 'Checking…' : 'Verify against independent source'}
        </button>
      </div>

      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}

      {state ? (
        <div className="mt-4 space-y-3">
          <div
            className={`inline-flex items-center px-2 py-1 text-sm font-bold ${
              VERDICT_STYLE[state.verdict] ?? 'bg-slate-100 text-slate-700'
            }`}
          >
            {state.verdict.replace(/_/g, ' ')}
          </div>
          <p className="text-sm text-slate-700">{VERDICT_NOTE[state.verdict] ?? ''}</p>
          {!state.key_configured ? (
            <p className="text-xs text-slate-500">
              No SCREENER_INDEPENDENT_QUOTE_API_KEY configured — set it process-locally to enable
              live vendor lookups.
            </p>
          ) : null}
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs uppercase text-slate-500">Screener price</dt>
              <dd className="font-semibold text-slate-950">{px(state.screener_price)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Independent price</dt>
              <dd className="font-semibold text-slate-950">{px(state.independent_price)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Divergence</dt>
              <dd className="font-semibold text-slate-950">{pct(state.divergence_pct)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Source</dt>
              <dd className="font-semibold text-slate-950">{state.independent_source}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </section>
  );
}
