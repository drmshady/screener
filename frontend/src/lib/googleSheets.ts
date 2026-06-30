/**
 * Browser-only Google Sheets reader for the owner's transaction sheet.
 *
 * Flow:
 *   1. Request a short-lived spreadsheets.readonly GIS token (never stored).
 *   2. Call the Sheets REST v4 values endpoint with that token.
 *   3. Map the header row + data rows into raw dicts with 'source_row' attached.
 *   4. Return the raw rows for POST /portfolio/import — the backend normalises.
 *
 * Security properties (FR-001 / api-keys-never-write):
 *   - The access token is used immediately and never written to any persistent store,
 *     never sent to the backend, and never logged.
 *   - The client id (NEXT_PUBLIC_GOOGLE_CLIENT_ID) is public; it is NOT a secret.
 *
 * Graceful degradation: if the client id or the GIS script is absent, all helpers
 * return a disabled state — no error is thrown (plan.md Deployment Compatibility 5).
 */

/** A raw row dict keyed by the sheet's header names, plus 'source_row' (1-based). */
export type RawSheetRow = Record<string, string>;

/** The result of reading a Google Sheet — either rows or a readable error. */
export type SheetReadResult =
  | { ok: true; rows: RawSheetRow[]; sheetId: string; range: string }
  | { ok: false; error: string };

/** Whether the feature is available in the current runtime. */
export function googleSheetsAvailable(): boolean {
  if (typeof window === 'undefined') return false;
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim();
  if (!clientId) return false;
  return true;
}

/** True when the GIS script has already finished loading. */
export function gisScriptLoaded(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof (window as Window & { google?: unknown }).google !== 'undefined'
  );
}

declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initTokenClient(config: {
            client_id: string;
            scope: string;
            callback: (response: { access_token?: string; error?: string }) => void;
          }): { requestAccessToken(opts?: { prompt?: string }): void };
        };
      };
    };
  }
}

/** Request a short-lived Google OAuth access token via GIS. */
async function requestAccessToken(): Promise<string> {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim();
  if (!clientId) {
    throw new Error('NEXT_PUBLIC_GOOGLE_CLIENT_ID is not configured');
  }
  if (!gisScriptLoaded()) {
    throw new Error('Google Identity Services script is not loaded');
  }

  return new Promise((resolve, reject) => {
    const tokenClient = window.google!.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: 'https://www.googleapis.com/auth/spreadsheets.readonly',
      callback: (response) => {
        if (response.error) {
          reject(new Error(`Token error: ${response.error}`));
        } else if (response.access_token) {
          resolve(response.access_token);
        } else {
          reject(new Error('No access token returned'));
        }
      },
    });
    tokenClient.requestAccessToken({ prompt: 'select_account' });
  });
}

/**
 * Parse the Sheets REST v4 values response into raw row dicts.
 *
 * The first row is treated as the header. Each subsequent row becomes a dict
 * keyed by header name. Missing trailing cells are treated as empty strings.
 * 'source_row' (1-based, matching the visual sheet row) is always present.
 */
function parseSheetValues(
  values: string[][],
  range: string,
): RawSheetRow[] {
  if (!values || values.length < 2) return [];
  const [headers, ...dataRows] = values;
  return dataRows.map((row, idx) => {
    const dict: RawSheetRow = {};
    headers.forEach((header, col) => {
      dict[header] = row[col] ?? '';
    });
    dict['source_row'] = String(idx + 2); // +1 for 0-index, +1 for header row
    return dict;
  });
}

/**
 * Read the owner's transaction sheet and return raw row dicts.
 *
 * @param sheetId   Google Spreadsheet id (from the URL).
 * @param range     A1 notation range, e.g. 'Transactions!A1:I'.
 */
export async function readSheetRows(
  sheetId: string,
  range: string,
): Promise<SheetReadResult> {
  if (!googleSheetsAvailable()) {
    return { ok: false, error: 'Google Sheets import is not configured on this deployment.' };
  }

  let accessToken: string;
  try {
    accessToken = await requestAccessToken();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { ok: false, error: `Could not obtain Google authorisation: ${msg}` };
  }

  const encodedRange = encodeURIComponent(range);
  const url = `https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(sheetId)}/values/${encodedRange}`;

  let response: Response;
  try {
    response = await fetch(url, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { ok: false, error: `Network error reading Google Sheet: ${msg}` };
  }

  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = body?.error?.message ?? '';
    } catch {
      // ignore parse error
    }
    return {
      ok: false,
      error: `Google Sheets returned ${response.status}${detail ? `: ${detail}` : ''}`,
    };
  }

  let data: { values?: string[][]; range?: string };
  try {
    data = await response.json();
  } catch {
    return { ok: false, error: 'Could not parse the Google Sheets response.' };
  }

  const rows = parseSheetValues(data.values ?? [], range);
  return { ok: true, rows, sheetId, range };
}
