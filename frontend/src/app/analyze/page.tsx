"use client";

import { FormEvent, useEffect, useState } from 'react';
import { Abbr } from '@/components/Abbr';
import { AsOfBadge } from '@/components/AsOfBadge';
import {
  AnalyzeResponse,
  AnalyzeResponseSchema,
  StrategiesResponseSchema,
  Strategy,
  fetchApi,
} from '@/lib/api';

function money(value: string | null | undefined) {
  if (!value) return '--';
  return `$${Number(value).toFixed(2)}`;
}

type GateStatus = 'pass' | 'fail' | 'skipped' | 'warn';

function badgeClass(status: GateStatus) {
  if (status === 'pass') return 'bg-emerald-100 text-emerald-800';
  if (status === 'fail') return 'bg-rose-100 text-rose-800';
  if (status === 'warn') return 'bg-amber-100 text-amber-800';
  return 'bg-slate-100 text-slate-600';
}

function badgeLabel(status: GateStatus) {
  if (status === 'pass') return 'PASS';
  if (status === 'fail') return 'FAIL';
  if (status === 'warn') return 'WARN';
  return 'SKIP';
}

export default function AnalyzePage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [ticker, setTicker] = useState('AAPL');
  const [strategy, setStrategy] = useState('midterm_52w_high_momentum');
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi('/strategies?enabled_only=false', StrategiesResponseSchema)
      .then((response) => setStrategies(response.strategies))
      .catch(() => setStrategies([]));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const query = new URLSearchParams({ strategy });
      const response = await fetchApi(`/analyze/${encodeURIComponent(symbol)}?${query.toString()}`, AnalyzeResponseSchema);
      setResult(response);
    } catch {
      setError('Analysis data is unavailable for that symbol.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-semibold tracking-normal text-slate-950">Analyze</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Check one symbol against a strategy gate by gate, including failed and skipped gates.
        </p>
      </header>

      <form className="panel grid gap-3 p-4 sm:grid-cols-[minmax(160px,220px)_minmax(220px,1fr)_auto]" onSubmit={handleSubmit}>
        <label className="grid gap-1 text-sm">
          <span className="font-medium text-slate-900">Symbol</span>
          <input
            className="border border-slate-300 px-3 py-2 uppercase"
            onChange={(event) => setTicker(event.target.value)}
            value={ticker}
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="font-medium text-slate-900">Strategy</span>
          <select
            className="border border-slate-300 px-3 py-2"
            onChange={(event) => setStrategy(event.target.value)}
            value={strategy}
          >
            {strategies.length ? (
              strategies.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.name}
                </option>
              ))
            ) : (
              <option value="midterm_52w_high_momentum">Mid-Term 52-Week High Momentum</option>
            )}
          </select>
        </label>
        <button
          className="border border-slate-950 bg-slate-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 sm:self-end"
          disabled={loading}
          type="submit"
        >
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </form>

      {error ? <div className="border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">{error}</div> : null}

      {result ? (
        <section className="space-y-4">
          <div
            className={`border p-4 ${
              result.would_be_selected
                ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
                : 'border-rose-300 bg-rose-50 text-rose-900'
            }`}
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold">{result.ticker}</h2>
                <p className="text-sm">
                  {result.name} - {result.sector} - Current {money(result.current_price)}
                </p>
              </div>
              <div className="text-sm font-semibold">
                {result.would_be_selected ? 'Would match applied gates' : 'Would not match applied gates'}
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <section className="panel p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-slate-950">Levels</h2>
                  <p className="text-sm text-slate-600">As of {result.as_of}</p>
                </div>
                <AsOfBadge date={result.data_as_of} />
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-xs uppercase text-slate-500">Entry</dt>
                  <dd className="font-semibold text-slate-950">{money(result.entry)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Stop</dt>
                  <dd className="font-semibold text-slate-950">{money(result.stop_loss)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Tighter stop</dt>
                  <dd className="font-semibold text-slate-950">{money(result.tighter_stop_loss)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Target</dt>
                  <dd className="font-semibold text-slate-950">{money(result.take_profit)}</dd>
                </div>
              </dl>
              {result.data_notes.length ? (
                <div className="mt-4 border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                  <p className="font-medium">Data notes</p>
                  <ul className="mt-1 list-disc pl-5">
                    {result.data_notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>

            <section className="panel overflow-hidden">
              <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
                <h2 className="text-lg font-semibold text-slate-950">Gate checklist</h2>
              </div>
              <ul className="divide-y divide-slate-100">
                {result.gate_results.map((gate) => (
                  <li className="flex items-start gap-3 px-4 py-3 text-sm" key={gate.gate}>
                    <span className={`mt-0.5 inline-flex h-5 min-w-[3.5rem] items-center justify-center px-1 text-xs font-semibold ${badgeClass(gate.status)}`}>
                      {badgeLabel(gate.status)}
                    </span>
                    <span>
                      <span className="font-medium text-slate-900">{gate.gate}</span>
                      <span className="text-slate-600"> - {gate.detail}</span>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
                <Abbr term="SMA" /> and percentile gates use the same definitions as the screen.
              </p>
            </section>
          </div>
        </section>
      ) : null}
    </main>
  );
}
