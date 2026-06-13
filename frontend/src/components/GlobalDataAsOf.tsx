"use client";

import { useEffect, useMemo, useState } from 'react';
import { MetaResponse, MetaResponseSchema, fetchApi } from '@/lib/api';

function primaryAsOf(meta: MetaResponse | null) {
  const priceSource =
    meta?.sources.find((source) => source.kind === 'prices' && source.source_name === 'yfinance') ??
    meta?.sources.find((source) => source.kind === 'prices') ??
    meta?.sources[0];
  return priceSource?.last_bar_date ?? priceSource?.source_as_of.slice(0, 10) ?? null;
}

export function GlobalDataAsOf() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchApi('/meta', MetaResponseSchema)
      .then((payload) => {
        setMeta(payload);
        setFailed(false);
      })
      .catch(() => setFailed(true));
  }, []);

  const asOf = useMemo(() => primaryAsOf(meta), [meta]);

  if (failed) {
    return <span className="text-xs font-medium text-amber-800">Data freshness unavailable</span>;
  }

  return (
    <span className="text-xs font-medium text-slate-600">
      Data as of {asOf ?? 'loading...'}
    </span>
  );
}
