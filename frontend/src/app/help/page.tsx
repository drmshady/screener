import Link from 'next/link';
import { DataFreshnessPanel } from '@/components/DataFreshnessPanel';
import { HelpTooltip } from '@/components/HelpTooltip';
import { GLOSSARY } from '@/lib/glossary';

const STRATEGY_REFERENCES = [
  {
    name: 'Mid-Term 52-Week High Momentum',
    href: '/screen/midterm_52w_high_momentum',
    citation: 'George & Hwang (2004); Barroso & Santa-Clara volatility scaling modification.',
  },
  {
    name: 'Short-Term Minervini VCP',
    href: '/screen/shortterm_minervini_vcp',
    citation: 'Minervini volatility-contraction pattern, implemented with documented local gates.',
  },
  {
    name: 'Short-Term ATR Breakout',
    href: '/screen/shortterm_atr_breakout',
    citation: 'Wilder ATR and Chandelier-style risk reference, implemented with trend and liquidity gates.',
  },
];

export default function HelpPage() {
  return (
    <main className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-semibold text-slate-950">Help</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Interpret screens, chart levels, source freshness, Shariah labels, and local portfolio checks with the same caveats shown throughout the app.
        </p>
      </header>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="panel space-y-4 p-5">
          <h2 className="text-lg font-semibold text-slate-950">Using the app</h2>
          <ol className="space-y-3 text-sm text-slate-700">
            <li>1. Check the global data-as-of label and the source freshness panel before interpreting any screen.</li>
            <li>2. Open a strategy screen and review gates, methodology, and walk-forward evidence before running the current snapshot.</li>
            <li>3. Review candidates as rule matches with reference levels, Shariah labels, event badges, and source timestamps.</li>
            <li>4. Open a candidate detail page to compare price, 52-week high <HelpTooltip term="52-week high" />, 200-day SMA <HelpTooltip term="200-day SMA" />, and levels.</li>
            <li>5. Use Watchlist and Portfolio for local tracking; data stays in this browser unless exported from Settings.</li>
          </ol>
        </div>
        <DataFreshnessPanel />
      </section>

      <section className="panel space-y-4 p-5">
        <h2 className="text-lg font-semibold text-slate-950">Data sources and freshness</h2>
        <div className="grid gap-4 text-sm text-slate-700 md:grid-cols-2">
          <div>
            <h3 className="font-semibold text-slate-950">Prices and indicators</h3>
            <p className="mt-1">
              Screens and candidate charts read local Stooq archive data with yfinance warm-store overlays when available. Every response exposes `data_as_of`.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-950">Fundamentals and sectors</h3>
            <p className="mt-1">
              Quality gates use local EDGAR-derived cache entries where present; missing fundamentals fail closed and appear in data notes.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-950">Events</h3>
            <p className="mt-1">
              Macro events and ticker events show source timestamps and stale-state labels when refresh windows are exceeded.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-950">Shariah sources</h3>
            <p className="mt-1">
              Settings can combine SPUS-family holdings, Halal Terminal, Finispia, and user-maintained include/exclude lists.
            </p>
          </div>
        </div>
      </section>

      <section className="panel space-y-4 p-5">
        <h2 className="text-lg font-semibold text-slate-950">Strategy explainers and citations</h2>
        <div className="grid gap-3">
          {STRATEGY_REFERENCES.map((strategy) => (
            <Link className="border border-slate-200 p-4 hover:bg-slate-50" href={strategy.href} key={strategy.href}>
              <div className="font-semibold text-slate-950">{strategy.name}</div>
              <p className="mt-1 text-sm text-slate-600">{strategy.citation}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="panel space-y-4 p-5">
        <h2 className="text-lg font-semibold text-slate-950">Glossary</h2>
        <dl className="grid gap-4 sm:grid-cols-2">
          {GLOSSARY.map((entry) => (
            <div className="border border-slate-200 p-3" key={entry.term}>
              <dt className="font-semibold text-slate-950">{entry.term}</dt>
              <dd className="mt-1 text-sm text-slate-700">{entry.definition}</dd>
            </div>
          ))}
        </dl>
      </section>
    </main>
  );
}
