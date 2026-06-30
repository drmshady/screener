import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Holding {
  ticker: string;
  shares: number;
  avg_cost: number;
  current_price: number;
  sector: string;
  avg_dollar_volume_20d?: number;
  added_at: string;
  updated_at?: string;
  note?: string;
}

export interface Portfolio {
  schema_version: 3;
  total_capital: number;
  holdings: Holding[];
  cash_balance_override?: number;
  created_at: string;
  updated_at: string;
  local_storage_notice_acknowledged: boolean;
}

export interface ShariahOverride {
  ticker: string;
  direction: 'include' | 'exclude';
  added_at: string;
  note?: string;
}

export interface UserSettings {
  per_position_cap_pct: number;
  per_sector_cap_pct: number;
  shariah_filter_on: boolean;
  shariah_external_sources: string[];
  shariah_user_inclusion: ShariahOverride[];
  shariah_user_exclusion: ShariahOverride[];
  liquidity_min_avg_dollar_volume_20d: number;
  liquidity_min_price: number;
  exclude_earnings_within_days_overrides: Record<string, number>;
  default_strategy_slug: string;
}

export interface WatchlistEntry {
  id: string;
  ticker: string;
  name: string;
  sector: string;
  strategy_slug: string;
  saved_at: string;
  state: 'saved' | 'dismissed' | 'acted_on';
  levels_snapshot: {
    entry: string;
    stop_loss: string;
    take_profit: string;
  };
  note?: string;
  /**
   * Feature 013 (US4): last observed live entry-timing state + when it was
   * checked, so a ticker that newly became entry-ready since the owner last
   * looked can be visually flagged. Informational only.
   */
  last_entry_state?: 'entry_ready' | 'not_entry_ready' | 'entry_undetermined';
  last_checked_at?: string;
}

/** A transaction row as persisted in the browser store (mirrors the backend Transaction model). */
export interface Transaction {
  id: string;
  ticker: string;
  action: 'buy' | 'sell';
  quantity: string;   // Decimal serialised as string
  price: string;      // Decimal serialised as string
  trade_date: string; // ISO date string YYYY-MM-DD
  fees: string | null;
  note: string | null;
  source_row: number;
}

interface ImportResult {
  ok: boolean;
  error?: string;
}

interface StoredState {
  portfolio: Portfolio;
  watchlist: WatchlistEntry[];
  settings: UserSettings;
  /** Feature 013: imported transactions (source of truth for holdings). */
  transactions: Transaction[];
  sheet_id: string | null;
  sheet_range: string | null;
}

interface AppState extends StoredState {
  setTotalCapital: (amount: number) => void;
  addHolding: (holding: Omit<Holding, 'added_at' | 'updated_at'> & Partial<Pick<Holding, 'added_at' | 'updated_at'>>) => void;
  updateHolding: (ticker: string, patch: Partial<Holding>) => void;
  removeHolding: (ticker: string) => void;
  acknowledgeLocalStorageWarning: () => void;
  saveCandidate: (entry: Omit<WatchlistEntry, 'id' | 'saved_at' | 'state'>) => void;
  updateWatchlistState: (id: string, state: WatchlistEntry['state']) => void;
  setWatchlistEntryStatus: (
    id: string,
    entryState: NonNullable<WatchlistEntry['last_entry_state']>,
    checkedAt: string,
  ) => void;
  updateSettings: (settings: Partial<UserSettings>) => void;
  addShariahOverride: (direction: ShariahOverride['direction'], ticker: string, note?: string) => void;
  removeShariahOverride: (direction: ShariahOverride['direction'], ticker: string) => void;
  exportData: () => string;
  importData: (payload: string) => ImportResult;
  hydrateStored: (raw: unknown) => void;
  /** Feature 013: persist imported transactions from POST /portfolio/import. */
  setTransactions: (transactions: Transaction[], sheetId?: string | null, sheetRange?: string | null) => void;
  clearTransactions: () => void;
}

function nowIso() {
  return new Date().toISOString();
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function numberValue(value: unknown, fallback = 0): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function tickerValue(value: unknown): string {
  return String(value ?? '').trim().toUpperCase();
}

function normalizeHolding(value: unknown): Holding | null {
  const record = asRecord(value);
  const ticker = tickerValue(record.ticker);
  const shares = numberValue(record.shares);
  const avgCost = numberValue(record.avg_cost);
  const currentPrice = numberValue(record.current_price, avgCost);
  if (!ticker || shares <= 0 || currentPrice < 0 || avgCost < 0) {
    return null;
  }
  const addedAt = typeof record.added_at === 'string' ? record.added_at : nowIso();
  const updatedAt = typeof record.updated_at === 'string' ? record.updated_at : addedAt;
  const dollarVolume = numberValue(record.avg_dollar_volume_20d, 0);
  return {
    ticker,
    shares,
    avg_cost: avgCost,
    current_price: currentPrice,
    sector: String(record.sector || 'Unclassified'),
    avg_dollar_volume_20d: dollarVolume > 0 ? dollarVolume : undefined,
    added_at: addedAt,
    updated_at: updatedAt,
    note: typeof record.note === 'string' && record.note.trim() ? record.note.trim() : undefined,
  };
}

function defaultPortfolio(): Portfolio {
  const timestamp = nowIso();
  return {
    schema_version: 3,
    total_capital: 100000,
    holdings: [],
    created_at: timestamp,
    updated_at: timestamp,
    local_storage_notice_acknowledged: false,
  };
}

// Shariah filter is ON by default with every populated halal source enabled
// (operator decision, Phase 12). Finispia is omitted — it has no rows yet, so
// including it would only surface a spurious stale-source warning.
const DEFAULT_SHARIAH_SOURCES = [
  'spus_holdings',
  'spwo_holdings',
  'spre_holdings',
  'spte_holdings',
  'halal_terminal',
];

function defaultSettings(): UserSettings {
  return {
    per_position_cap_pct: 0.1,
    per_sector_cap_pct: 0.25,
    shariah_filter_on: true,
    shariah_external_sources: [...DEFAULT_SHARIAH_SOURCES],
    shariah_user_inclusion: [],
    shariah_user_exclusion: [],
    liquidity_min_avg_dollar_volume_20d: 1_000_000,
    liquidity_min_price: 5,
    exclude_earnings_within_days_overrides: {},
    default_strategy_slug: 'midterm_52w_high_momentum',
  };
}

function normalizeSettings(value: unknown): UserSettings {
  const record = asRecord(value);
  return {
    ...defaultSettings(),
    ...record,
    per_position_cap_pct: numberValue(record.per_position_cap_pct, 0.1),
    per_sector_cap_pct: numberValue(record.per_sector_cap_pct, 0.25),
    shariah_filter_on:
      typeof record.shariah_filter_on === 'boolean' ? record.shariah_filter_on : true,
    shariah_external_sources: Array.isArray(record.shariah_external_sources)
      ? record.shariah_external_sources.map(String)
      : [...DEFAULT_SHARIAH_SOURCES],
    shariah_user_inclusion: Array.isArray(record.shariah_user_inclusion)
      ? (record.shariah_user_inclusion as ShariahOverride[])
      : [],
    shariah_user_exclusion: Array.isArray(record.shariah_user_exclusion)
      ? (record.shariah_user_exclusion as ShariahOverride[])
      : [],
    liquidity_min_avg_dollar_volume_20d: numberValue(record.liquidity_min_avg_dollar_volume_20d, 1_000_000),
    liquidity_min_price: numberValue(record.liquidity_min_price, 5),
    exclude_earnings_within_days_overrides:
      typeof record.exclude_earnings_within_days_overrides === 'object' && record.exclude_earnings_within_days_overrides
        ? (record.exclude_earnings_within_days_overrides as Record<string, number>)
        : {},
    default_strategy_slug: String(record.default_strategy_slug || 'midterm_52w_high_momentum'),
  };
}

function normalizePortfolio(value: unknown): Portfolio {
  const record = asRecord(value);
  const fallback = defaultPortfolio();
  const holdings = Array.isArray(record.holdings)
    ? record.holdings.map(normalizeHolding).filter((holding): holding is Holding => Boolean(holding))
    : [];
  return {
    ...fallback,
    ...record,
    schema_version: 3,
    total_capital: numberValue(record.total_capital, fallback.total_capital),
    cash_balance_override:
      record.cash_balance_override === undefined ? undefined : numberValue(record.cash_balance_override),
    holdings,
    created_at: typeof record.created_at === 'string' ? record.created_at : fallback.created_at,
    updated_at: typeof record.updated_at === 'string' ? record.updated_at : fallback.updated_at,
    local_storage_notice_acknowledged: Boolean(record.local_storage_notice_acknowledged),
  };
}

function normalizeStoredState(value: unknown): StoredState {
  const record = asRecord(value);
  const stateRecord = asRecord(record.state ?? record);
  return {
    portfolio: normalizePortfolio(stateRecord.portfolio),
    watchlist: Array.isArray(stateRecord.watchlist) ? (stateRecord.watchlist as WatchlistEntry[]) : [],
    settings: normalizeSettings(stateRecord.settings),
    transactions: Array.isArray(stateRecord.transactions) ? (stateRecord.transactions as Transaction[]) : [],
    sheet_id: typeof stateRecord.sheet_id === 'string' ? stateRecord.sheet_id : null,
    sheet_range: typeof stateRecord.sheet_range === 'string' ? stateRecord.sheet_range : null,
  };
}

function exportSnapshot(state: StoredState) {
  return {
    schema_version: 3,
    exported_at: nowIso(),
    portfolio: state.portfolio,
    watchlist: state.watchlist,
    settings: state.settings,
    transactions: state.transactions,
    sheet_id: state.sheet_id,
    sheet_range: state.sheet_range,
  };
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      portfolio: defaultPortfolio(),
      watchlist: [],
      settings: defaultSettings(),
      transactions: [],
      sheet_id: null,
      sheet_range: null,
      setTotalCapital: (amount) =>
        set((state) => ({
          portfolio: {
            ...state.portfolio,
            total_capital: Math.max(0, amount),
            updated_at: nowIso(),
          },
        })),
      addHolding: (holding) =>
        set((state) => {
          const normalized = normalizeHolding({ ...holding, added_at: holding.added_at ?? nowIso(), updated_at: nowIso() });
          if (!normalized) {
            return state;
          }
          const existing = state.portfolio.holdings.find((item) => item.ticker === normalized.ticker);
          if (existing) {
            const shares = existing.shares + normalized.shares;
            const avgCost =
              shares > 0
                ? (existing.avg_cost * existing.shares + normalized.avg_cost * normalized.shares) / shares
                : normalized.avg_cost;
            const merged = normalizeHolding({
              ...existing,
              ...normalized,
              shares,
              avg_cost: avgCost,
              added_at: existing.added_at,
              updated_at: nowIso(),
              note: normalized.note ?? existing.note,
            });
            if (!merged) {
              return state;
            }
            return {
              portfolio: {
                ...state.portfolio,
                holdings: state.portfolio.holdings.map((item) => (item.ticker === merged.ticker ? merged : item)),
                updated_at: nowIso(),
              },
            };
          }
          return {
            portfolio: {
              ...state.portfolio,
              holdings: [
                ...state.portfolio.holdings.filter((item) => item.ticker !== normalized.ticker),
                normalized,
              ],
              updated_at: nowIso(),
            },
          };
        }),
      updateHolding: (ticker, patch) =>
        set((state) => {
          const symbol = tickerValue(ticker);
          const holdings = state.portfolio.holdings.map((holding) => {
            if (holding.ticker !== symbol) {
              return holding;
            }
            return normalizeHolding({ ...holding, ...patch, ticker: symbol, updated_at: nowIso() }) ?? holding;
          });
          return {
            portfolio: {
              ...state.portfolio,
              holdings,
              updated_at: nowIso(),
            },
          };
        }),
      removeHolding: (ticker) =>
        set((state) => ({
          portfolio: {
            ...state.portfolio,
            holdings: state.portfolio.holdings.filter((holding) => holding.ticker !== tickerValue(ticker)),
            updated_at: nowIso(),
          },
        })),
      acknowledgeLocalStorageWarning: () =>
        set((state) => ({
          portfolio: {
            ...state.portfolio,
            local_storage_notice_acknowledged: true,
            updated_at: nowIso(),
          },
        })),
      saveCandidate: (entry) =>
        set((state) => ({
          watchlist: [
            ...state.watchlist.filter((item) => !(item.ticker === entry.ticker && item.strategy_slug === entry.strategy_slug)),
            {
              ...entry,
              id: `${entry.strategy_slug}-${entry.ticker}`,
              saved_at: nowIso(),
              state: 'saved',
            },
          ],
        })),
      updateWatchlistState: (id, nextState) =>
        set((state) => ({
          watchlist: state.watchlist.map((item) => (item.id === id ? { ...item, state: nextState } : item)),
        })),
      setWatchlistEntryStatus: (id, entryState, checkedAt) =>
        set((state) => ({
          watchlist: state.watchlist.map((item) =>
            item.id === id
              ? { ...item, last_entry_state: entryState, last_checked_at: checkedAt }
              : item,
          ),
        })),
      updateSettings: (settings) => set((state) => ({ settings: { ...state.settings, ...settings } })),
      addShariahOverride: (direction, ticker, note) =>
        set((state) => {
          const symbol = tickerValue(ticker);
          if (!symbol) {
            return state;
          }
          const key = direction === 'include' ? 'shariah_user_inclusion' : 'shariah_user_exclusion';
          const nextEntry: ShariahOverride = {
            ticker: symbol,
            direction,
            added_at: nowIso(),
            note: note?.trim() || undefined,
          };
          return {
            settings: {
              ...state.settings,
              [key]: [
                ...state.settings[key].filter((entry) => entry.ticker !== symbol),
                nextEntry,
              ],
            },
          };
        }),
      removeShariahOverride: (direction, ticker) =>
        set((state) => {
          const symbol = tickerValue(ticker);
          const key = direction === 'include' ? 'shariah_user_inclusion' : 'shariah_user_exclusion';
          return {
            settings: {
              ...state.settings,
              [key]: state.settings[key].filter((entry) => entry.ticker !== symbol),
            },
          };
        }),
      setTransactions: (transactions, sheetId = null, sheetRange = null) =>
        set(() => ({ transactions, sheet_id: sheetId ?? null, sheet_range: sheetRange ?? null })),
      clearTransactions: () => set(() => ({ transactions: [], sheet_id: null, sheet_range: null })),
      exportData: () => JSON.stringify(exportSnapshot(get()), null, 2),
      importData: (payload) => {
        try {
          const parsed = JSON.parse(payload) as unknown;
          const nextState = normalizeStoredState(parsed);
          set(nextState);
          return { ok: true };
        } catch {
          return { ok: false, error: 'Import failed. Check that the JSON file came from this app.' };
        }
      },
      // Replace local state with the server-persisted blob (server is the source
      // of truth on load). Used by PortfolioSync so the portfolio survives across
      // browsers/origins/restarts, not just this browser's localStorage.
      hydrateStored: (raw) => set(() => normalizeStoredState(raw)),
    }),
    {
      name: 'screener-storage',
      version: 6,
      migrate: (persisted, version) => {
        const state = normalizeStoredState(persisted) as AppState;
        if (version < 4) {
          // One-time (Phase 12): turn the Shariah filter ON by default with all
          // populated halal sources, preserving the user's lists/caps.
          state.settings = {
            ...state.settings,
            shariah_filter_on: true,
            shariah_external_sources: [...DEFAULT_SHARIAH_SOURCES],
          };
        }
        // version < 5 (Phase 013): transactions/sheet fields are already handled
        // by normalizeStoredState (defaults to [] / null when absent).
        // version < 6 (Phase 013, US4): watchlist last_entry_state/last_checked_at
        // are optional and preserved as-is by normalizeStoredState (absent = unset).
        return state;
      },
    },
  ),
);
