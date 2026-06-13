"use client";

import { useState } from 'react';
import { copyText, fetchAdvisorPrompt } from '@/lib/advisorPrompt';

type State = {
  loading?: boolean;
  error?: string;
  prompt?: string;
  directive?: boolean;
  copied?: boolean;
};

/**
 * Feature 004: one-click "Copy advisor prompt". Fetches the app-generated,
 * self-contained prompt for a candidate, copies it to the clipboard, and shows
 * a collapsible preview. When the backend reports personal-use directive mode,
 * the preview is marked with `data-personal-use-prompt` so the no-directive
 * lint can scope its exemption to that element only.
 */
export function CopyAdvisorPrompt({ ticker, asOf }: { ticker: string; asOf?: string }) {
  const [state, setState] = useState<State>({});

  async function generate() {
    setState({ loading: true });
    try {
      const res = await fetchAdvisorPrompt(ticker, asOf);
      const copied = await copyText(res.prompt);
      setState({ prompt: res.prompt, directive: res.personal_use_directive, copied });
    } catch (error) {
      setState({ error: error instanceof Error ? error.message : 'Could not generate the advisor prompt.' });
    }
  }

  return (
    <div className="mt-2 inline-block">
      <button
        className="border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 disabled:opacity-50"
        disabled={state.loading}
        onClick={generate}
        type="button"
      >
        {state.loading ? 'Generating...' : state.copied ? 'Copied advisor prompt' : 'Copy advisor prompt'}
      </button>
      {state.error ? (
        <p className="mt-2 text-sm text-rose-700">{state.error}</p>
      ) : null}
      {state.prompt ? (
        <details className="mt-2" open>
          <summary className="cursor-pointer text-xs font-medium text-slate-600">
            {state.copied ? 'Copied to clipboard — preview' : 'Preview (copy failed — select and copy manually)'}
          </summary>
          <pre
            className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800"
            data-testid="advisor-prompt-preview"
            {...(state.directive ? { 'data-personal-use-prompt': 'true' } : {})}
          >
            {state.prompt}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
