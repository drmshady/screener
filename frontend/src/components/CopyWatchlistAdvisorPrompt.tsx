"use client";

import { useState } from 'react';
import { copyText } from '@/lib/advisorPrompt';
import { fetchWatchlistAdvisorPrompt } from '@/lib/api';

type State = {
  loading?: boolean;
  error?: string;
  prompt?: string;
  directive?: boolean;
  count?: number;
  copied?: boolean;
};

/**
 * Feature 017 (US3): one combined advisor prompt over the owner's watched names,
 * in the same screener-results format as the screen export. Posts the active
 * strategy slug + the watched tickers to the backend (the single source of
 * truth), which re-computes each name against the current snapshot and embeds
 * any already-captured sentiment, then copies the result. An empty watchlist is
 * a valid request that yields a clear "no watched names" prompt state.
 */
export function CopyWatchlistAdvisorPrompt({
  tickers,
  strategySlug,
  asOf,
  disabled,
  idleLabel = 'Copy watchlist advisor prompt',
}: {
  tickers: string[];
  strategySlug: string;
  asOf?: string | null;
  disabled?: boolean;
  idleLabel?: string;
}) {
  const [state, setState] = useState<State>({});

  async function generate() {
    setState({ loading: true });
    try {
      const res = await fetchWatchlistAdvisorPrompt({
        strategy_slug: strategySlug,
        tickers,
        as_of: asOf ?? null,
      });
      const copied = await copyText(res.prompt);
      setState({
        prompt: res.prompt,
        directive: res.personal_use_directive,
        count: res.watched_count,
        copied,
      });
    } catch (error) {
      setState({
        error: error instanceof Error ? error.message : 'Could not generate the advisor prompt.',
      });
    }
  }

  return (
    <div className="inline-block">
      <button
        className="border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 disabled:opacity-50"
        disabled={state.loading || disabled}
        onClick={generate}
        type="button"
      >
        {state.loading
          ? 'Generating...'
          : state.copied
            ? `Copied prompt (${state.count} watched name${state.count === 1 ? '' : 's'})`
            : idleLabel}
      </button>
      {state.error ? <p className="mt-2 text-sm text-rose-700">{state.error}</p> : null}
      {state.prompt ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-medium text-slate-600">
            {state.copied
              ? 'Copied to clipboard — preview'
              : 'Preview (copy failed — select and copy manually)'}
          </summary>
          <pre
            className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800"
            data-testid="watchlist-advisor-prompt-preview"
            {...(state.directive ? { 'data-personal-use-prompt': 'true' } : {})}
          >
            {state.prompt}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
