"use client";

import { useState } from 'react';
import { copyText, fetchScreenAdvisorPrompt } from '@/lib/advisorPrompt';

type State = {
  loading?: boolean;
  error?: string;
  prompt?: string;
  directive?: boolean;
  count?: number;
  copied?: boolean;
};

/**
 * Feature 004 (batch): one combined advisor prompt covering every candidate in
 * the current screen. Re-runs the screen on the backend with the same request
 * body so the prompt's numbers match what is displayed, then copies the result.
 */
export function CopyScreenAdvisorPrompt({
  slug,
  getRequestBody,
  disabled,
}: {
  slug: string;
  getRequestBody: () => unknown;
  disabled?: boolean;
}) {
  const [state, setState] = useState<State>({});

  async function generate() {
    setState({ loading: true });
    try {
      const res = await fetchScreenAdvisorPrompt(slug, getRequestBody());
      const copied = await copyText(res.prompt);
      setState({ prompt: res.prompt, directive: res.personal_use_directive, count: res.candidate_count, copied });
    } catch (error) {
      setState({ error: error instanceof Error ? error.message : 'Could not generate the advisor prompt.' });
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
            ? `Copied prompt (${state.count} candidate${state.count === 1 ? '' : 's'})`
            : 'Copy advisor prompt (all results)'}
      </button>
      {state.error ? <p className="mt-2 text-sm text-rose-700">{state.error}</p> : null}
      {state.prompt ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-medium text-slate-600">
            {state.copied ? 'Copied to clipboard — preview' : 'Preview (copy failed — select and copy manually)'}
          </summary>
          <pre
            className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800"
            data-testid="screen-advisor-prompt-preview"
            {...(state.directive ? { 'data-personal-use-prompt': 'true' } : {})}
          >
            {state.prompt}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
