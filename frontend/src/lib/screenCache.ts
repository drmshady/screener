import { ScreenResult } from './api';

// In-memory cache of the last screen result per strategy, so navigating from the
// candidate table into a detail page and back does NOT re-run the (slow,
// whole-universe) screen. Deliberately NOT persisted to localStorage: screen
// results are large and time-sensitive, so a full page reload should start fresh.
// The module stays loaded across client-side navigations, so the cache survives
// Back/Forward within a session.

export interface CachedScreen {
  result: ScreenResult;
  market: 'US' | 'SA';
  ranAt: number;
}

const cache = new Map<string, CachedScreen>();

export function getCachedScreen(strategySlug: string): CachedScreen | undefined {
  return cache.get(strategySlug);
}

export function setCachedScreen(strategySlug: string, entry: CachedScreen): void {
  cache.set(strategySlug, entry);
}

export function clearCachedScreen(strategySlug: string): void {
  cache.delete(strategySlug);
}
