// Maps backend event_type codes to a short display term that exists in the
// glossary (lib/glossary.ts), so the UI can render <Abbr term={eventTerm(code)}>
// and get both a readable label and a hover definition. Falls back to a
// de-underscored code for anything unmapped.

const EVENT_TYPE_TERM: Record<string, string> = {
  FOMC: 'FOMC',
  CPI: 'CPI',
  PCE: 'PCE',
  NFP: 'NFP',
  PPI: 'PPI',
  GDP: 'GDP',
  '8K_filed': '8-K',
  earnings_scheduled: 'Earnings',
};

export function eventTerm(eventType: string): string {
  return EVENT_TYPE_TERM[eventType] ?? eventType.replace(/_/g, ' ');
}
