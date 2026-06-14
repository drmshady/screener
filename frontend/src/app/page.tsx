import Link from 'next/link';
import { DataFreshnessPanel } from '@/components/DataFreshnessPanel';
import { MarketEventsPanel } from '@/components/MarketEventsPanel';
import { RegimePanel } from '@/components/RegimePanel';

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-semibold text-slate-950">US Stock Screener</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          Run mid-term and short-term screens, review strategy gates, inspect walk-forward metrics, and save candidates locally.
        </p>
      </header>
      <DataFreshnessPanel />
      <RegimePanel />
      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          className="panel p-5 hover:border-slate-400"
          href="/screen/midterm_52w_high_momentum"
        >
          <div className="text-lg font-semibold text-slate-950">Mid-Term 52-Week High Momentum</div>
          <p className="mt-2 text-sm text-slate-600">Default MVP screen with entries, stops, targets, citations, and backtest evidence.</p>
        </Link>
        <Link
          className="panel p-5 hover:border-slate-400"
          href="/screen/midterm_value_composite"
        >
          <div className="text-lg font-semibold text-slate-950">Mid-Term Value Composite</div>
          <p className="mt-2 text-sm text-slate-600">Cheapness screen (book/market, earnings, cash-flow, sales yields) gated by the Piotroski F-Score, with entries, stops, targets, citations, and backtest evidence.</p>
        </Link>
        <Link className="panel p-5 hover:border-slate-400" href="/screen/shortterm_minervini_vcp">
          <div className="text-lg font-semibold text-slate-950">Short-Term Minervini VCP</div>
          <p className="mt-2 text-sm text-slate-600">Volatility-contraction screen with pivot, stop, target, citations, and backtest evidence.</p>
        </Link>
        <Link className="panel p-5 hover:border-slate-400" href="/screen/shortterm_atr_breakout">
          <div className="text-lg font-semibold text-slate-950">Short-Term ATR Breakout</div>
          <p className="mt-2 text-sm text-slate-600">ATR breakout screen with trend filter, Chandelier reference, citations, and backtest evidence.</p>
        </Link>
        <Link className="panel p-5 hover:border-slate-400" href="/watchlist">
          <div className="text-lg font-semibold text-slate-950">Watchlist</div>
          <p className="mt-2 text-sm text-slate-600">Review saved candidates and captured levels from this browser.</p>
        </Link>
        <Link className="panel p-5 hover:border-slate-400" href="/portfolio">
          <div className="text-lg font-semibold text-slate-950">Portfolio</div>
          <p className="mt-2 text-sm text-slate-600">Review local holdings with Shariah source labels and summary counts.</p>
        </Link>
        <Link className="panel p-5 hover:border-slate-400" href="/settings">
          <div className="text-lg font-semibold text-slate-950">Settings</div>
          <p className="mt-2 text-sm text-slate-600">Manage source choices, filters, caps, and local Shariah lists.</p>
        </Link>
        <Link className="panel p-5 hover:border-slate-400" href="/help">
          <div className="text-lg font-semibold text-slate-950">Help</div>
          <p className="mt-2 text-sm text-slate-600">Glossary, source freshness, methodology citations, and reading notes.</p>
        </Link>
      </div>
      <MarketEventsPanel daysAhead={60} />
    </main>
  );
}
