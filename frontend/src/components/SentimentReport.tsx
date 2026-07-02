"use client";

import { FormEvent, useMemo, useState } from 'react';
import { ApiError, SentimentReportResponse, SentimentSelection, postSentimentReport } from '@/lib/api';

function cleanTicker(value: string) {
  return value.trim().toUpperCase();
}

function labelText(label: string) {
  if (label === 'no_signal') return 'No signal';
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function sourceClassText(value: string) {
  return value.replaceAll('_', ' ');
}

export function SentimentReport({ initialSelections = [] }: { initialSelections?: SentimentSelection[] }) {
  const [manualTicker, setManualTicker] = useState('');
  const [selections, setSelections] = useState<SentimentSelection[]>(() => dedupeSelections(initialSelections));
  const [result, setResult] = useState<SentimentReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const selectedTickers = useMemo(() => selections.map((selection) => selection.ticker).join(', '), [selections]);

  function addManual(event: FormEvent) {
    event.preventDefault();
    const ticker = cleanTicker(manualTicker);
    if (!ticker) return;
    setSelections((current) => dedupeSelections([...current, { ticker, origin: 'manual' }]));
    setManualTicker('');
    setError(null);
  }

  async function runReport() {
    if (!selections.length) {
      setError('Select at least one stock.');
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const payload = await postSentimentReport({ selections });
      setResult(payload);
    } catch (err) {
      const retry = err instanceof ApiError && err.retryable ? ' Retry when the backend is available.' : '';
      setError(err instanceof Error ? `${err.message}${retry}` : 'The report could not be created.');
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="panel space-y-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-950">Selections</h2>
            <p className="mt-1 text-sm text-slate-600">
              {selectedTickers || 'No stocks selected.'}
            </p>
          </div>
          <button
            className="border border-slate-950 bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
            disabled={running}
            onClick={runReport}
            type="button"
          >
            {running ? 'Running...' : 'Run report'}
          </button>
        </div>
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={addManual}>
          <input
            aria-label="Manual ticker"
            className="min-w-0 flex-1 border border-slate-300 px-3 py-2 text-sm"
            onChange={(event) => setManualTicker(event.target.value)}
            placeholder="Manual ticker"
            value={manualTicker}
          />
          <button className="border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-100" type="submit">
            Add ticker
          </button>
        </form>
        {selections.length ? (
          <div className="flex flex-wrap gap-2">
            {selections.map((selection) => (
              <button
                className="border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                key={`${selection.origin}-${selection.ticker}`}
                onClick={() =>
                  setSelections((current) =>
                    current.filter((item) => !(item.ticker === selection.ticker && item.origin === selection.origin)),
                  )
                }
                type="button"
              >
                {selection.ticker} · {selection.origin}
              </button>
            ))}
          </div>
        ) : null}
        {error ? <p className="border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">{error}</p> : null}
      </section>

      {result ? (
        <section className="space-y-3">
          <div className="text-sm text-slate-600">
            Spend this period: {result.period_spend_usd} / {result.monthly_cap_usd}
          </div>
          {result.reports.map((report) => (
            <article className="border border-slate-200 bg-white p-4" key={`${report.origin}-${report.ticker}`}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-950">{report.ticker}</h3>
                  <p className="text-sm text-slate-600">{report.origin}</p>
                </div>
                <span className="border border-slate-300 px-2 py-1 text-sm font-semibold text-slate-800">
                  {labelText(report.label)}
                </span>
              </div>
              {report.resolution === 'symbol_not_found' ? (
                <p className="mt-3 text-sm text-slate-700">Symbol not found.</p>
              ) : (
                <>
                  <p className="mt-3 text-sm leading-6 text-slate-700">{report.narrative}</p>
                  {report.narrative_risk ? (
                    <p className="mt-2 text-sm text-slate-600">
                      Narrative activity: {report.narrative_risk.label} ({report.narrative_risk.score}/100)
                    </p>
                  ) : null}
                  <p className="mt-2 text-xs text-slate-500">{report.label_basis}</p>
                </>
              )}
              {report.sources.length ? (
                <div className="mt-4 space-y-2">
                  <h4 className="text-sm font-semibold text-slate-950">Sources</h4>
                  <ul className="space-y-2">
                    {report.sources.map((source) => (
                      <li className="border-l border-slate-300 pl-3 text-sm text-slate-700" key={source.id}>
                        <div className="font-medium text-slate-900">{source.title}</div>
                        <div className="text-xs text-slate-500">
                          {source.publisher ?? sourceClassText(source.source_class)} ·{' '}
                          {new Date(source.published_at).toISOString().slice(0, 10)}
                          {source.is_stale ? ' · stale' : ''}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {report.source_classes_omitted.length ? (
                <p className="mt-3 text-xs text-slate-500">
                  Omitted: {report.source_classes_omitted.map(sourceClassText).join(', ')}
                </p>
              ) : null}
            </article>
          ))}
        </section>
      ) : null}
    </div>
  );
}

function dedupeSelections(selections: SentimentSelection[]) {
  const seen = new Set<string>();
  const out: SentimentSelection[] = [];
  for (const selection of selections) {
    const ticker = cleanTicker(selection.ticker);
    if (!ticker) continue;
    const key = `${selection.origin}:${ticker}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ ...selection, ticker });
  }
  return out;
}
