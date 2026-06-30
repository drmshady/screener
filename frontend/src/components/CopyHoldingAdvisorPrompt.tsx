"use client";

import { useState } from 'react';
import { copyText } from '@/lib/advisorPrompt';
import { fetchHoldingAdvisorPrompt, fetchPortfolioAdvisorPrompt } from '@/lib/api';

type State = {
  loading?: boolean;
  error?: string;
  prompt?: string;
  directive?: boolean;
  copied?: boolean;
};

/**
 * Feature 014: one-click "Copy prompt" for a position the owner ALREADY HOLDS.
 * Fetches the app-generated, self-contained hold/trim/exit review prompt (single
 * holding when `ticker` is set, otherwise the whole portfolio), copies it, and
 * shows a collapsible preview. When the backend reports personal-use directive
 * mode, the preview is marked with `data-personal-use-prompt` so the no-directive
 * lint can scope its exemption to that element only. The backend is the single
 * source of truth — this component holds no strategy or sizing knowledge.
 */
export function CopyHoldingAdvisorPrompt({
  totalCapital,
  ticker,
  strategySlug,
}: {
  totalCapital: string;
  ticker?: string;
  strategySlug?: string;
}) {
  const [state, setState] = useState<State>({});
  const whole = !ticker;
  const label = whole ? 'Copy portfolio prompt' : 'Copy prompt';

  async function generate() {
    setState({ loading: true });
    try {
      const body = { total_capital: totalCapital, strategy_slug: strategySlug };
      const res = ticker
        ? await fetchHoldingAdvisorPrompt(ticker, body)
        : await fetchPortfolioAdvisorPrompt(body);
      const copied = await copyText(res.prompt);
      setState({ prompt: res.prompt, directive: res.personal_use_directive, copied });
    } catch (error) {
      setState({
        error: error instanceof Error ? error.message : 'Could not generate the advisor prompt.',
      });
    }
  }

  return (
    <div className="inline-block">
      <button
        className="border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-800 disabled:opacity-50"
        disabled={state.loading}
        onClick={generate}
        type="button"
      >
        {state.loading ? 'Generating...' : state.copied ? 'Copied' : label}
      </button>
      {state.error ? <p className="mt-2 text-xs text-rose-700">{state.error}</p> : null}
      {state.prompt ? (
        <details className="mt-2" open>
          <summary className="cursor-pointer text-xs font-medium text-slate-600">
            {state.copied
              ? 'Copied to clipboard — preview'
              : 'Preview (copy failed — select and copy manually)'}
          </summary>
          <pre
            className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800"
            data-testid="holding-advisor-prompt-preview"
            {...(state.directive ? { 'data-personal-use-prompt': 'true' } : {})}
          >
            {state.prompt}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
