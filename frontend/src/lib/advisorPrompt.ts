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
): Promise<AdvisorPromptResponse> {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
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

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
