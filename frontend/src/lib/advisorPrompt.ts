import {
  AdvisorPromptResponse,
  AdvisorPromptResponseSchema,
  ScreenAdvisorPromptResponse,
  ScreenAdvisorPromptResponseSchema,
  fetchApi,
} from './api';

// Feature 004: fetch the app-generated, self-contained advisor prompt for a
// candidate. The backend is the single source of truth — this helper only
// fetches and copies; it holds no strategy knowledge.

export async function fetchAdvisorPrompt(
  ticker: string,
  asOf?: string,
  strategy?: string,
): Promise<AdvisorPromptResponse> {
  const params = new URLSearchParams();
  if (strategy) params.set('strategy', strategy);
  if (asOf) params.set('as_of', asOf);
  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchApi(
    `/analyze/${encodeURIComponent(ticker)}/advisor-prompt${query}`,
    AdvisorPromptResponseSchema,
  );
}

export async function fetchScreenAdvisorPrompt(
  slug: string,
  body: unknown,
): Promise<ScreenAdvisorPromptResponse> {
  return fetchApi(
    `/strategies/${encodeURIComponent(slug)}/advisor-prompt`,
    ScreenAdvisorPromptResponseSchema,
    { method: 'POST', body: JSON.stringify(body) },
  );
}

// Strategies the advisor-prompt endpoints support (single-ticker analyze is
// gated to these on the backend; batch works for any but we surface the button
// only for the supported mid-term strategies). Keep in sync with the backend
// allow-list in api/analyze.py::compute_candidate_result.
export const ADVISOR_PROMPT_SLUGS = new Set([
  'midterm_52w_high_momentum',
  'midterm_value_composite',
]);

export function supportsAdvisorPrompt(slug: string | null | undefined): boolean {
  return !!slug && ADVISOR_PROMPT_SLUGS.has(slug);
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
