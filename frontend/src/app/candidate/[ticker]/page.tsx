"use client";

import { use, useEffect, useState } from 'react';
import { Abbr } from '@/components/Abbr';
import { AsOfBadge } from '@/components/AsOfBadge';
import { CandidatePriceChart } from '@/components/ChartPanels';
import { CopyAdvisorPrompt } from '@/components/CopyAdvisorPrompt';
import { ShariahBadge } from '@/components/ShariahBadge';
import { supportsAdvisorPrompt } from '@/lib/advisorPrompt';
import { eventTerm } from '@/lib/events';
import { formatMoney } from '@/lib/format';
import {
  Candidate,
  CandidateDetail,
  CandidateDetailSchema,
  CandidateHistoryResponse,
  CandidateHistoryResponseSchema,
  SizingResponse,
  fetchApi,
  postSizing,
} from '@/lib/api';
import { useAppStore } from '@/lib/store';

function money(value: string) {
  return `$${Number(value).toFixed(2)}`;
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

type SizingState = {
  loading?: boolean;
  status?: number;
  result?: SizingResponse;
  error?: string;
};

export default function CandidatePage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const [detail, setDetail] = useState<CandidateDetail | null>(null);
  const [history, setHistory] = useState<CandidateHistoryResponse | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const settings = useAppStore((state) => state.settings);
  const portfolio = useAppStore((state) => state.portfolio);
  const addHolding = useAppStore((state) => state.addHolding);
  const [sizing, setSizing] = useState<Record<string, SizingState>>({});
  const [addingPortfolio, setAddingPortfolio] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const query = new URLSearchParams();
    if (settings.shariah_external_sources.length) {
      query.set('sources', settings.shariah_external_sources.join(','));
    }
    if (settings.shariah_user_inclusion.length) {
      query.set('include', settings.shariah_user_inclusion.map((entry) => entry.ticker).join(','));
    }
    if (settings.shariah_user_exclusion.length) {
      query.set('exclude', settings.shariah_user_exclusion.map((entry) => entry.ticker).join(','));
    }
    // Scope the detail re-run to the strategy + sector-gate toggle the screen used,
    // so the gate breakdown matches the screen (forwarded via the candidate link).
    const fromScreen = new URLSearchParams(window.location.search);
    const scopedStrategy = fromScreen.get('strategy');
    const sectorFraction = fromScreen.get('sector');
    if (scopedStrategy) query.set('strategy', scopedStrategy);
    if (sectorFraction) query.set('sector_strength_top_fraction', sectorFraction);
    const queryText = query.toString();
    setDetail(null);
    setDetailError(null);
    fetchApi(`/candidates/${ticker}${queryText ? `?${queryText}` : ''}`, CandidateDetailSchema)
      .then(setDetail)
      .catch(() => setDetailError('Candidate not found in the latest screen snapshot.'));
    fetchApi(`/candidates/${ticker}/history?days=400`, CandidateHistoryResponseSchema)
      .then(setHistory)
      .catch(() => setHistory(null));
  }, [settings.shariah_external_sources, settings.shariah_user_exclusion, settings.shariah_user_inclusion, ticker]);

  async function sizeMatch(match: Candidate) {
    const key = `${match.strategy_slug ?? 'strategy'}-${match.rank}`;
    setSizing((current) => ({ ...current, [key]: { loading: true } }));
    try {
      const response = await postSizing({
        candidate_ticker: detail?.ticker ?? match.ticker,
        entry: match.entry,
        candidate_sector: detail?.sector ?? match.sector,
        total_capital: String(portfolio.total_capital),
        holdings: portfolio.holdings.map((holding) => ({
          ticker: holding.ticker,
          shares: String(holding.shares),
          current_price: String(holding.current_price),
          sector: holding.sector,
        })),
        caps: {
          per_position_cap_pct: settings.per_position_cap_pct,
          per_sector_cap_pct: settings.per_sector_cap_pct,
        },
      });
      setSizing((current) => ({ ...current, [key]: { status: response.status, result: response.result } }));
    } catch (error) {
      setSizing((current) => ({
        ...current,
        [key]: { error: error instanceof Error ? error.message : 'Sizing failed.' },
      }));
    }
  }

  async function addMatchToPortfolio(match: Candidate) {
    const key = `${match.strategy_slug ?? 'strategy'}-${match.rank}`;
    setAddingPortfolio((current) => ({ ...current, [key]: true }));
    try {
      const existingSizing = sizing[key]?.result;
      let suggested = existingSizing?.caps_respected ? existingSizing.suggested_shares : 0;
      if (!existingSizing) {
        const response = await postSizing({
          candidate_ticker: detail?.ticker ?? match.ticker,
          entry: match.entry,
          candidate_sector: detail?.sector ?? match.sector,
          total_capital: String(portfolio.total_capital),
          holdings: portfolio.holdings.map((holding) => ({
            ticker: holding.ticker,
            shares: String(holding.shares),
            current_price: String(holding.current_price),
            sector: holding.sector,
          })),
          caps: {
            per_position_cap_pct: settings.per_position_cap_pct,
            per_sector_cap_pct: settings.per_sector_cap_pct,
          },
        });
        suggested = response.result.caps_respected ? response.result.suggested_shares : 0;
      }
      const rawShares = window.prompt(`Shares for ${match.ticker}`, suggested > 0 ? String(suggested) : '1');
      const shares = Number(rawShares);
      if (!Number.isFinite(shares) || shares <= 0) {
        return;
      }
      addHolding({
        ticker: match.ticker,
        shares,
        avg_cost: Number(match.entry),
        current_price: Number(match.current_price),
        sector: match.sector,
      });
    } finally {
      setAddingPortfolio((current) => ({ ...current, [key]: false }));
    }
  }

  if (detailError) {
    return (
      <main className="mx-auto max-w-4xl space-y-4 px-6 py-8">
        <header className="border-b border-slate-200 pb-5">
          <h1 className="text-2xl font-semibold text-slate-950">{ticker.toUpperCase()}</h1>
          <p className="text-sm text-slate-600">{detailError}</p>
        </header>
        <CandidatePriceChart history={history} levels={null} />
      </main>
    );
  }

  if (!detail) {
    return <main className="mx-auto max-w-4xl px-6 py-8 text-sm text-slate-600">Loading candidate...</main>;
  }

  const primaryMatch = detail.matches[0] ?? null;

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-semibold text-slate-950">{detail.ticker}</h1>
        <p className="text-sm text-slate-600">
          {detail.name} - {detail.sector} - Current {formatMoney(detail.current_price, detail.ticker)}
        </p>
        <div className="mt-3">
          <AsOfBadge date={detail.data_as_of} />
        </div>
        <div className="mt-3">
          <ShariahBadge status={detail.shariah} />
        </div>
      </header>

      <CandidatePriceChart
        history={history}
        levels={
          primaryMatch
            ? {
                entry: primaryMatch.entry,
                stop_loss: primaryMatch.stop_loss,
                take_profit: primaryMatch.take_profit,
              }
            : null
        }
      />

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-950">Strategy matches</h2>
        <div className="grid gap-3">
          {detail.matches.map((match) => (
            <article
              className="panel p-4"
              key={`${match.strategy_slug ?? match.strategy_name ?? 'strategy'}-${match.ticker}-${match.rank}`}
            >
              {(() => {
                const sizingKey = `${match.strategy_slug ?? 'strategy'}-${match.rank}`;
                const sizingState = sizing[sizingKey];
                return (
                  <>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-950">{match.strategy_name ?? 'Strategy match'}</div>
                  {match.timeframe ? <div className="text-xs font-medium text-slate-600">{match.timeframe}</div> : null}
                  <p className="text-sm text-slate-600">{match.reason}</p>
                </div>
                <div className="text-sm text-slate-600">Rank #{match.rank}</div>
              </div>
              <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
                <div>
                  <dt className="text-xs uppercase text-slate-500">Entry</dt>
                  <dd className="font-semibold text-slate-950">{formatMoney(match.entry, detail.ticker)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Stop</dt>
                  <dd className="font-semibold text-slate-950">{formatMoney(match.stop_loss, detail.ticker)}</dd>
                  {match.tighter_stop_loss &&
                  Number(match.tighter_stop_loss) > Number(match.stop_loss) ? (
                    <dd className="mt-1 text-xs text-emerald-700">tighter: {formatMoney(match.tighter_stop_loss, detail.ticker)}</dd>
                  ) : null}
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Target</dt>
                  <dd className="font-semibold text-slate-950">{formatMoney(match.take_profit, detail.ticker)}</dd>
                </div>
              </dl>
              {match.gate_results && match.gate_results.length > 0 ? (
                <div className="mt-4 border border-slate-200">
                  <div className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase text-slate-600">
                    Why this was selected — gate-by-gate
                  </div>
                  <ul className="divide-y divide-slate-100">
                    {match.gate_results.map((g) => (
                      <li className="flex items-start gap-2 px-3 py-2 text-sm" key={g.gate}>
                        <span
                          className={`mt-0.5 inline-flex h-5 min-w-[3.5rem] items-center justify-center px-1 text-xs font-semibold ${
                            g.status === 'pass'
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {g.status === 'pass' ? 'PASS' : 'SKIP'}
                        </span>
                        <span>
                          <span className="font-medium text-slate-900">{g.gate}</span>
                          <span className="text-slate-600"> — {g.detail}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
                    A listed candidate passed every applied gate. &quot;SKIP&quot; means the gate
                    could not be evaluated for this name (data unavailable) and did not exclude it.
                  </p>
                </div>
              ) : null}
              <div className="mt-4">
                <button
                  className="border border-slate-950 bg-slate-950 px-4 py-2 text-sm font-semibold text-white"
                  disabled={sizingState?.loading}
                  onClick={() => sizeMatch(match)}
                  type="button"
                >
                  {sizingState?.loading ? 'Sizing...' : 'Size this trade'}
                </button>
                <button
                  className="ml-2 border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800"
                  disabled={addingPortfolio[sizingKey]}
                  onClick={() => addMatchToPortfolio(match)}
                  type="button"
                >
                  {addingPortfolio[sizingKey] ? 'Adding...' : 'Add to portfolio'}
                </button>
                {supportsAdvisorPrompt(match.strategy_slug ?? 'midterm_52w_high_momentum') ? (
                  <CopyAdvisorPrompt
                    ticker={detail.ticker}
                    asOf={detail.data_as_of?.slice(0, 10)}
                    strategy={match.strategy_slug ?? 'midterm_52w_high_momentum'}
                  />
                ) : null}
              </div>
              {sizingState?.error ? (
                <div className="mt-3 border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">{sizingState.error}</div>
              ) : null}
              {sizingState?.result ? (
                <div className="mt-3 grid gap-3 border border-slate-200 p-3 text-sm sm:grid-cols-5">
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Suggested shares</dt>
                    <dd className="font-semibold text-slate-950">{sizingState.result.suggested_shares}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Dollar value</dt>
                    <dd className="font-semibold text-slate-950">{money(sizingState.result.suggested_position_value)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Per-position</dt>
                    <dd className="font-semibold text-slate-950">{percent(sizingState.result.resulting_position_pct_of_capital)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Per-sector</dt>
                    <dd className="font-semibold text-slate-950">{percent(sizingState.result.resulting_sector_pct_of_capital)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Caps respected</dt>
                    <dd className="font-semibold text-slate-950">{sizingState.result.caps_respected ? 'Yes' : 'No'}</dd>
                  </div>
                  <p className="sm:col-span-5 text-slate-600">{sizingState.result.reasoning}</p>
                </div>
              ) : null}
                  </>
                );
              })()}
            </article>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-950">Events</h2>
        {detail.events.length === 0 ? (
          <div className="border border-slate-200 bg-white p-4 text-sm text-slate-600">No earnings or 8-K events in the current window.</div>
        ) : (
          <div className="divide-y divide-slate-200 border border-slate-200 bg-white">
            {detail.events.map((event) => (
              <a
                className="grid gap-1 p-3 text-sm hover:bg-slate-50 sm:grid-cols-[160px_minmax(0,1fr)_140px]"
                href={event.source_url}
                key={`${event.event_type}-${event.event_date}-${event.source_url}`}
                rel="noreferrer"
                target="_blank"
              >
                <span className="font-semibold text-slate-950"><Abbr term={eventTerm(event.event_type)} /></span>
                <span className="text-slate-700">{event.source_name}</span>
                <span className="text-slate-600 sm:text-right">{event.event_date}</span>
              </a>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
