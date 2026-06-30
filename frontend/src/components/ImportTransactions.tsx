"use client";

/**
 * ImportTransactions — connect-sheet + import-summary UI (Feature 013, US1).
 *
 * The owner connects their Google Sheet via a short-lived GIS OAuth token
 * (browser-only, never sent to the backend or persisted). Raw rows are POSTed
 * to POST /portfolio/import; the backend normalises, validates, and persists.
 *
 * Graceful degradation: when NEXT_PUBLIC_GOOGLE_CLIENT_ID or the GIS script
 * is absent, the connect button is disabled with an explanatory note (plan.md
 * Deployment Compatibility item 5).
 *
 * All copy is descriptive — no directive language (FR-020).
 */

import { useState, useEffect } from 'react';
import Script from 'next/script';
import { importTransactions, ImportResult } from '@/lib/api';
import { googleSheetsAvailable, gisScriptLoaded, readSheetRows } from '@/lib/googleSheets';
import { useAppStore } from '@/lib/store';

interface Props {
  /** Called when a successful import completes, so the parent can re-fetch holdings. */
  onImported?: (result: ImportResult) => void;
}

function sheetIdFromUrl(raw: string): string {
  // Extract the sheet id from a full Google Sheets URL or return as-is.
  const match = raw.match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : raw.trim();
}

export function ImportTransactions({ onImported }: Props) {
  const setTransactions = useAppStore((s) => s.setTransactions);
  const transactions = useAppStore((s) => s.transactions);
  const sheet_id = useAppStore((s) => s.sheet_id);
  const sheet_range = useAppStore((s) => s.sheet_range);

  const [sheetUrl, setSheetUrl] = useState(sheet_id ?? '');
  const [range, setRange] = useState(sheet_range ?? 'Transactions!A1:I');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  // Lazy initializer (not an effect) handles the "script already loaded" case —
  // e.g. navigating back to /portfolio — without a synchronous setState in an
  // effect body. On SSR/first hydration it is false (no window / not yet loaded).
  const [gisReady, setGisReady] = useState<boolean>(() => gisScriptLoaded());

  // Poll until the GIS script loads (it may arrive after hydration). The
  // <Script onLoad> below also flips this; the poll is the fallback for a
  // remount where the cached script's onLoad does not refire.
  useEffect(() => {
    if (gisReady) return;
    const interval = window.setInterval(() => {
      if (gisScriptLoaded()) {
        setGisReady(true);
        clearInterval(interval);
      }
    }, 500);
    return () => clearInterval(interval);
  }, [gisReady]);

  // Gate the GIS library load on a configured client id (inlined at build time,
  // so this is identical server- and client-side — no hydration mismatch). When
  // the id is absent we render no <Script> and make no Google network call,
  // preserving the headless/offline graceful-degradation guarantee.
  const clientConfigured = Boolean(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim());
  const available = googleSheetsAvailable() && gisReady;

  async function handleImport() {
    setLoading(true);
    setError(null);
    setResult(null);

    const sheetId = sheetIdFromUrl(sheetUrl);
    const readResult = await readSheetRows(sheetId, range.trim() || 'Transactions!A1:I');
    if (!readResult.ok) {
      setError(readResult.error);
      setLoading(false);
      return;
    }

    try {
      const importResult = await importTransactions({
        rows: readResult.rows as Record<string, unknown>[],
        sheet_id: readResult.sheetId,
        sheet_range: readResult.range,
      });
      // Persist the full transaction list to the store for PortfolioSync re-seeding.
      // We don't have the full list from the response, so we trigger a re-fetch
      // via the parent callback; store updates happen there.
      setResult(importResult);
      onImported?.(importResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed. Retry when the service is available.');
    } finally {
      setLoading(false);
    }
  }

  const disabledReason = !googleSheetsAvailable()
    ? 'Google Sheets import is not configured on this deployment (NEXT_PUBLIC_GOOGLE_CLIENT_ID missing).'
    : !gisReady
    ? 'Google Identity Services script is loading…'
    : null;

  return (
    <section aria-label="Import transactions from Google Sheet" className="space-y-4 border border-gray-200 p-5">
      {clientConfigured ? (
        <Script
          src="https://accounts.google.com/gsi/client"
          strategy="afterInteractive"
          onLoad={() => setGisReady(true)}
        />
      ) : null}
      <h2 className="text-lg font-semibold text-gray-950">Import from Google Sheet</h2>

      {disabledReason ? (
        <p className="text-sm text-amber-800 border border-amber-300 bg-amber-50 px-3 py-2">
          {disabledReason}
        </p>
      ) : null}

      <label className="block text-sm text-gray-800">
        <span className="font-medium">Google Sheet URL or ID</span>
        <input
          aria-label="Google Sheet URL or ID"
          className="mt-1 w-full border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-400"
          disabled={!available || loading}
          onChange={(e) => setSheetUrl(e.target.value)}
          placeholder="https://docs.google.com/spreadsheets/d/…"
          type="text"
          value={sheetUrl}
        />
      </label>

      <label className="block text-sm text-gray-800">
        <span className="font-medium">Range</span>
        <input
          aria-label="Sheet range"
          className="mt-1 w-full border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-400"
          disabled={!available || loading}
          onChange={(e) => setRange(e.target.value)}
          placeholder="Transactions!A1:I"
          type="text"
          value={range}
        />
      </label>

      <button
        className="border border-gray-950 bg-gray-950 px-4 py-2 text-sm font-semibold text-white disabled:border-gray-300 disabled:bg-gray-100 disabled:text-gray-400"
        disabled={!available || loading || !sheetUrl.trim()}
        onClick={handleImport}
        type="button"
      >
        {loading ? 'Reading sheet…' : 'Connect and import'}
      </button>

      {error ? (
        <div className="border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-900" role="alert">
          {error}
        </div>
      ) : null}

      {result ? (
        <div className="space-y-3">
          <div className="border border-gray-200 p-3 text-sm">
            <div className="font-medium text-gray-950">Import summary</div>
            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-gray-700 sm:grid-cols-4">
              <div>
                <dt className="text-xs text-gray-500">New transactions</dt>
                <dd className="font-semibold">{result.accepted_count}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Already present</dt>
                <dd className="font-semibold">{result.duplicate_count}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Not imported</dt>
                <dd className="font-semibold">{result.rejected.length}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Total in ledger</dt>
                <dd className="font-semibold">{result.transactions_total}</dd>
              </div>
            </dl>
          </div>

          {result.rejected.length > 0 ? (
            <div className="border border-amber-300 bg-amber-50 p-3 text-sm">
              <div className="font-medium text-amber-900">Rows that could not be imported</div>
              <p className="mt-1 text-xs text-amber-800">
                These rows were not added to your ledger. Correct them in the sheet and re-import.
              </p>
              <ul className="mt-2 space-y-2">
                {result.rejected.map((row) => (
                  <li className="text-xs text-amber-900" key={row.source_row}>
                    <span className="font-medium">Row {row.source_row}:</span> {row.reason}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {transactions.length > 0 && !result ? (
        <p className="text-xs text-gray-500">
          Ledger contains {transactions.length} transaction{transactions.length !== 1 ? 's' : ''}.
          Re-import to add new rows (duplicates are skipped automatically).
        </p>
      ) : null}
    </section>
  );
}
