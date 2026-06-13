// Currency-aware formatting. Saudi (Tadawul) prices are in SAR; everything else
// is USD. We infer currency from the ticker suffix (`.SR` = Saudi) so candidate
// rows, the candidate page, and the portfolio all show the right symbol without
// the backend having to thread a currency field everywhere.

export function currencyForTicker(ticker?: string | null): 'SAR' | 'USD' {
  return ticker && ticker.toUpperCase().endsWith('.SR') ? 'SAR' : 'USD';
}

export function formatMoney(value: string | number | null | undefined, ticker?: string | null): string {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  const num = Number.isFinite(n) ? n.toFixed(2) : String(value);
  return currencyForTicker(ticker) === 'SAR' ? `SAR ${num}` : `$${num}`;
}
