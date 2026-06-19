"use client";

import { useEffect, useMemo, useState } from 'react';
import { DataFreshnessResponse, getDataFreshness } from '@/lib/api';

function primaryAsOf(freshness: DataFreshnessResponse | null) {
  const priceSource =
    freshness?.sources.find((source) => source.kind === 'prices' && source.source_name === 'yfinance') ??
    freshness?.sources.find((source) => source.kind === 'prices') ??
    freshness?.sources[0];
  return priceSource?.data_as_of ?? freshness?.latest_session ?? null;
}

export function GlobalDataAsOf() {
  const [freshness, setFreshness] = useState<DataFreshnessResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getDataFreshness()
      .then((payload) => {
        setFreshness(payload);
        setFailed(false);
      })
      .catch(() => setFailed(true));
  }, []);

  const asOf = useMemo(() => primaryAsOf(freshness), [freshness]);

  if (failed) {
    return <span className="text-xs font-medium text-amber-800">Data freshness unavailable</span>;
  }

  return (
    <span className="text-xs font-medium text-slate-600">
      Data as of {asOf ?? 'loading...'}
    </span>
  );
}
