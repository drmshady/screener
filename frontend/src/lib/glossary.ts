export type GlossaryTerm = {
  term: string;
  definition: string;
};

export const GLOSSARY: GlossaryTerm[] = [
  {
    term: '52-week high',
    definition: 'The highest traded high over the prior 252 trading sessions.',
  },
  {
    term: '200-day SMA',
    definition: 'The simple moving average of the last 200 closing prices.',
  },
  {
    term: 'ATR',
    definition: 'Average True Range, a volatility measure built from high, low, and close ranges.',
  },
  {
    term: 'Breadth',
    definition: 'The share of eligible universe members trading above their own 200-day SMA.',
  },
  {
    term: 'Entry level',
    definition: 'A reference price level produced by the strategy rules for review.',
  },
  {
    term: 'Stop level',
    definition: 'A reference risk level calculated from the strategy rules.',
  },
  {
    term: 'Target level',
    definition: 'A reference upside level calculated from the strategy rules.',
  },
  {
    term: 'Walk-forward',
    definition: 'A backtest style that evaluates rules through time using only information available at each period.',
  },
  {
    term: 'Survivorship bias',
    definition: 'A distortion that can appear when historical tests omit names that delisted or disappeared.',
  },
  {
    term: 'Shariah source',
    definition: 'The external or user-maintained list used to label compliance status.',
  },
  // ---- Macro / market-wide event abbreviations ----
  { term: 'FOMC', definition: 'Federal Open Market Committee — the Fed meeting that sets US interest rates. High market-wide impact.' },
  { term: 'CPI', definition: 'Consumer Price Index — the main US inflation reading; moves rate expectations and the whole market.' },
  { term: 'PCE', definition: 'Personal Consumption Expenditures price index — the inflation measure the Fed watches most closely.' },
  { term: 'NFP', definition: 'Non-Farm Payrolls — monthly US jobs added; a key gauge of economic strength.' },
  { term: 'PPI', definition: 'Producer Price Index — wholesale inflation; an early signal for consumer inflation.' },
  { term: 'GDP', definition: 'Gross Domestic Product — the broadest measure of US economic output.' },
  { term: '8-K', definition: 'SEC Form 8-K — a filing companies make for material events: M&A, leadership changes, results, etc.' },
  { term: 'Earnings', definition: 'A scheduled quarterly earnings report — results can move the stock sharply.' },
  // ---- Liquidity / price ----
  { term: 'ADV', definition: 'Average Daily Dollar Volume — typical $ traded per day (price × shares); a liquidity floor so positions are tradeable.' },
  { term: 'ADR', definition: 'Average Daily Range — average high-to-low move per day; used to detect volatility contraction.' },
  { term: 'SMA', definition: 'Simple Moving Average — the average closing price over N days (e.g., 200-day); a trend reference.' },
  // ---- Fundamentals / quality ----
  { term: 'FCF', definition: 'Free Cash Flow — operating cash flow minus capital spending; cash the business actually generates.' },
  { term: 'D/E', definition: 'Debt-to-Equity — total liabilities divided by shareholder equity; a leverage gauge.' },
  { term: 'GP/A', definition: 'Gross Profit / Assets — Novy-Marx gross profitability; a quality measure where higher is better.' },
  { term: 'Asset growth', definition: 'Year-over-year change in total assets. Low asset growth predicts higher 52-week-high momentum returns (George–Hwang–Li q-theory).' },
  { term: 'EPS', definition: 'Earnings Per Share — net income divided by shares outstanding.' },
  { term: 'P/E', definition: 'Price-to-Earnings — share price divided by earnings per share; a valuation multiple.' },
  // ---- Strategy / methodology ----
  { term: 'PTH', definition: 'Price-to-High ratio — current price relative to the 52-week high (George–Hwang 2004).' },
  { term: '12-1 momentum', definition: 'Return over the past 12 months excluding the most recent month.' },
  { term: 'VCP', definition: "Volatility Contraction Pattern — Minervini's tightening price/volume base before a breakout." },
  { term: 'R-multiple', definition: 'Reward measured in units of risk (R = entry − stop). A 3R target risks 1 to make 3.' },
  { term: 'point-in-time', definition: 'Only data actually available on the historical date — prevents look-ahead bias.' },
  { term: 'Liquidity gate', definition: 'A universe-wide filter (price ≥ $5, ADV ≥ $1M) applied before any strategy runs.' },
];

export function glossaryDefinition(term: string) {
  return GLOSSARY.find((entry) => entry.term.toLowerCase() === term.toLowerCase())?.definition;
}
