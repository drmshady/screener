"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from 'react';
import { useAppStore, type ShariahOverride } from '@/lib/store';

const SOURCE_OPTIONS = [
  { id: 'spus_holdings', label: 'SPUS holdings' },
  { id: 'spwo_holdings', label: 'SPWO holdings (global)' },
  { id: 'spre_holdings', label: 'SPRE holdings (REITs)' },
  { id: 'spte_holdings', label: 'SPTE holdings (tech)' },
  { id: 'halal_terminal', label: 'Halal Terminal' },
  { id: 'finispia', label: 'Finispia' },
];

const STRATEGY_OPTIONS = [
  { id: 'midterm_52w_high_momentum', label: 'Mid-Term 52-Week High Momentum' },
  { id: 'shortterm_minervini_vcp', label: 'Short-Term Minervini VCP' },
  { id: 'shortterm_atr_breakout', label: 'Short-Term ATR Breakout' },
];

function OverrideList({
  entries,
  onRemove,
}: {
  entries: ShariahOverride[];
  onRemove: (ticker: string) => void;
}) {
  if (entries.length === 0) {
    return <div className="border border-gray-200 p-3 text-sm text-gray-500">No tickers.</div>;
  }
  return (
    <div className="divide-y divide-gray-200 border border-gray-200">
      {entries.map((entry) => (
        <div className="flex items-start justify-between gap-3 p-3" key={`${entry.direction}-${entry.ticker}`}>
          <div>
            <div className="font-semibold text-gray-950">{entry.ticker}</div>
            {entry.note ? <div className="text-sm text-gray-600">{entry.note}</div> : null}
          </div>
          <button
            className="border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-100"
            onClick={() => onRemove(entry.ticker)}
            type="button"
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  );
}

export default function SettingsPage() {
  const settings = useAppStore((state) => state.settings);
  const updateSettings = useAppStore((state) => state.updateSettings);
  const addShariahOverride = useAppStore((state) => state.addShariahOverride);
  const removeShariahOverride = useAppStore((state) => state.removeShariahOverride);
  const exportData = useAppStore((state) => state.exportData);
  const importData = useAppStore((state) => state.importData);
  const [includeTicker, setIncludeTicker] = useState('');
  const [includeNote, setIncludeNote] = useState('');
  const [excludeTicker, setExcludeTicker] = useState('');
  const [excludeNote, setExcludeNote] = useState('');
  const [transferStatus, setTransferStatus] = useState<string | null>(null);

  const conflicts = useMemo(() => {
    const includes = new Set(settings.shariah_user_inclusion.map((entry) => entry.ticker));
    return settings.shariah_user_exclusion
      .map((entry) => entry.ticker)
      .filter((ticker) => includes.has(ticker));
  }, [settings.shariah_user_exclusion, settings.shariah_user_inclusion]);

  function toggleSource(sourceId: string, checked: boolean) {
    const next = checked
      ? Array.from(new Set([...settings.shariah_external_sources, sourceId]))
      : settings.shariah_external_sources.filter((source) => source !== sourceId);
    updateSettings({ shariah_external_sources: next });
  }

  function submitInclude(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addShariahOverride('include', includeTicker, includeNote);
    setIncludeTicker('');
    setIncludeNote('');
  }

  function submitExclude(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addShariahOverride('exclude', excludeTicker, excludeNote);
    setExcludeTicker('');
    setExcludeNote('');
  }

  function downloadExport() {
    const blob = new Blob([exportData()], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `screener-export-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setTransferStatus('Export file prepared.');
  }

  async function handleImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const result = importData(await file.text());
    setTransferStatus(result.ok ? 'Import complete.' : result.error ?? 'Import failed.');
    event.target.value = '';
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
      <header className="border-b border-gray-200 pb-5">
        <h1 className="text-2xl font-semibold text-gray-950">Settings</h1>
      </header>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4 border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-950">Shariah</h2>
          <label className="flex items-center justify-between gap-3 text-sm text-gray-800">
            <span>Shariah-compliant only</span>
            <input
              checked={settings.shariah_filter_on}
              className="h-4 w-4"
              onChange={(event) => updateSettings({ shariah_filter_on: event.target.checked })}
              type="checkbox"
            />
          </label>
          <div className="space-y-2">
            <div className="text-sm font-medium text-gray-950">External sources</div>
            {SOURCE_OPTIONS.map((source) => (
              <label className="flex items-center gap-2 text-sm text-gray-800" key={source.id}>
                <input
                  checked={settings.shariah_external_sources.includes(source.id)}
                  className="h-4 w-4"
                  onChange={(event) => toggleSource(source.id, event.target.checked)}
                  type="checkbox"
                />
                <span>{source.label}</span>
              </label>
            ))}
          </div>
          {conflicts.length ? (
            <div className="border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              Conflicting overrides: {conflicts.join(', ')}
            </div>
          ) : null}
        </div>

        <div className="space-y-4 border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-950">Risk And Liquidity</h2>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Per-position cap</span>
            <input
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(event) => updateSettings({ per_position_cap_pct: Number(event.target.value) / 100 })}
              step={0.1}
              type="number"
              value={Number((settings.per_position_cap_pct * 100).toFixed(2))}
            />
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Per-sector cap</span>
            <input
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(event) => updateSettings({ per_sector_cap_pct: Number(event.target.value) / 100 })}
              step={0.1}
              type="number"
              value={Number((settings.per_sector_cap_pct * 100).toFixed(2))}
            />
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Minimum 20-day dollar volume</span>
            <input
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(event) => updateSettings({ liquidity_min_avg_dollar_volume_20d: Number(event.target.value) })}
              step={100000}
              type="number"
              value={settings.liquidity_min_avg_dollar_volume_20d}
            />
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Minimum price</span>
            <input
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(event) => updateSettings({ liquidity_min_price: Number(event.target.value) })}
              step={0.5}
              type="number"
              value={settings.liquidity_min_price}
            />
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Default strategy</span>
            <select
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              onChange={(event) => updateSettings({ default_strategy_slug: event.target.value })}
              value={settings.default_strategy_slug}
            >
              {STRATEGY_OPTIONS.map((strategy) => (
                <option key={strategy.id} value={strategy.id}>
                  {strategy.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4 border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-950">User Include List</h2>
          <form className="grid gap-3 sm:grid-cols-[120px_minmax(0,1fr)_auto]" onSubmit={submitInclude}>
            <input
              className="border border-gray-300 px-3 py-2 text-sm uppercase"
              onChange={(event) => setIncludeTicker(event.target.value)}
              placeholder="Ticker"
              value={includeTicker}
            />
            <input
              className="border border-gray-300 px-3 py-2 text-sm"
              onChange={(event) => setIncludeNote(event.target.value)}
              placeholder="Note"
              value={includeNote}
            />
            <button className="border border-gray-950 bg-gray-950 px-4 py-2 text-sm font-semibold text-white" type="submit">
              Add include
            </button>
          </form>
          <OverrideList entries={settings.shariah_user_inclusion} onRemove={(ticker) => removeShariahOverride('include', ticker)} />
        </div>

        <div className="space-y-4 border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-950">User Exclude List</h2>
          <form className="grid gap-3 sm:grid-cols-[120px_minmax(0,1fr)_auto]" onSubmit={submitExclude}>
            <input
              className="border border-gray-300 px-3 py-2 text-sm uppercase"
              onChange={(event) => setExcludeTicker(event.target.value)}
              placeholder="Ticker"
              value={excludeTicker}
            />
            <input
              className="border border-gray-300 px-3 py-2 text-sm"
              onChange={(event) => setExcludeNote(event.target.value)}
              placeholder="Note"
              value={excludeNote}
            />
            <button className="border border-gray-950 bg-gray-950 px-4 py-2 text-sm font-semibold text-white" type="submit">
              Add exclude
            </button>
          </form>
          <OverrideList entries={settings.shariah_user_exclusion} onRemove={(ticker) => removeShariahOverride('exclude', ticker)} />
        </div>
      </section>

      <section className="space-y-4 border border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-950">Data Transfer</h2>
        <div className="flex flex-wrap items-center gap-3">
          <button
            className="border border-gray-950 bg-gray-950 px-4 py-2 text-sm font-semibold text-white"
            onClick={downloadExport}
            type="button"
          >
            Export JSON
          </button>
          <label className="inline-flex cursor-pointer border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-800 hover:bg-gray-50">
            <span>Import JSON</span>
            <input
              accept="application/json"
              aria-label="Import portfolio JSON"
              className="sr-only"
              onChange={handleImport}
              type="file"
            />
          </label>
        </div>
        {transferStatus ? <div className="text-sm text-gray-600">{transferStatus}</div> : null}
      </section>
    </main>
  );
}
