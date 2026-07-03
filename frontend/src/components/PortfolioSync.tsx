"use client";

import { useEffect, useRef } from 'react';
import { getPortfolioState, putPortfolioState } from '@/lib/api';
import { useAppStore } from '@/lib/store';

type StoreSnapshot = ReturnType<typeof useAppStore.getState>;

export function portfolioSyncPayload(s: StoreSnapshot) {
  return {
    portfolio: s.portfolio,
    watchlist: s.watchlist,
    settings: s.settings,
    transactions: s.transactions,
    sheet_id: s.sheet_id,
    sheet_range: s.sheet_range,
    // Feature 016 (US3): frontend-owned pipeline lifecycle state. Opaque to the
    // backend — it round-trips through the same PUT /portfolio/state blob.
    pipeline: s.pipeline,
  };
}

/**
 * Two-way sync between the local zustand store (localStorage) and the server-side
 * portfolio blob, so the portfolio/watchlist/settings survive across browsers,
 * origins, and restarts — not just this browser's localStorage.
 *
 * On mount: load the server blob (server is the source of truth); if the server
 * has nothing yet, seed it from local. After that, any local change is pushed to
 * the server (debounced). If the backend is unreachable, we silently stay on
 * localStorage only.
 */
export function PortfolioSync() {
  const hydrated = useRef(false);

  // Load from server (or seed it) once on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await getPortfolioState();
        if (cancelled) return;
        if (resp.state) {
          useAppStore.getState().hydrateStored(resp.state);
        } else {
          const s = useAppStore.getState();
          await putPortfolioState(portfolioSyncPayload(s));
        }
      } catch {
        // backend offline — keep using localStorage
      } finally {
        hydrated.current = true;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Push local changes to the server (debounced), once hydrated.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const unsub = useAppStore.subscribe((state, prev) => {
      if (!hydrated.current) return;
      if (
        state.portfolio === prev.portfolio &&
        state.watchlist === prev.watchlist &&
        state.settings === prev.settings &&
        state.transactions === prev.transactions &&
        state.sheet_id === prev.sheet_id &&
        state.sheet_range === prev.sheet_range &&
        state.pipeline === prev.pipeline
      ) {
        return;
      }
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        const s = useAppStore.getState();
        putPortfolioState(portfolioSyncPayload(s)).catch(() => {});
      }, 800);
    });
    return () => {
      if (timer) clearTimeout(timer);
      unsub();
    };
  }, []);

  return null;
}
