"use client";

import { useEffect, useState } from 'react';
import { MetaResponse, MetaResponseSchema, fetchApi } from '@/lib/api';
import { STATUS_TONES } from '@/lib/design';

function sourceLabel(sourceName: string) {
  if (sourceName === 'yfinance') {
    return 'yfinance';
  }
  if (sourceName === 'stooq') {
    return 'Stooq';
  }
  return sourceName;
}

export function DataFreshnessPanel() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchApi('/meta', MetaResponseSchema)
      .then(setMeta)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <section className={`${STATUS_TONES.warning} border p-4 text-sm`}>
        Data freshness is unavailable.
      </section>
    );
  }

  const priceSources =
    meta?.sources.filter((source) => source.kind === 'prices') ?? [];
  const primaryPriceSource =
    priceSources.find((source) => source.source_name === 'yfinance') ??
    priceSources[0];

  if (!primaryPriceSource) {
    return (
      <section className="panel p-4 text-sm text-slate-600">
        Loading data freshness...
      </section>
    );
  }

  const asOf = primaryPriceSource.last_bar_date ?? primaryPriceSource.source_as_of.slice(0, 10);

  return (
    <section className="panel flex flex-col gap-2 p-4 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div className="font-medium text-slate-950">Prices as of {asOf}</div>
        <div className="text-slate-600">
          Source: {primaryPriceSource.display_name ?? sourceLabel(primaryPriceSource.source_name)}
        </div>
      </div>
      <span
        className={`w-fit border px-2 py-1 text-xs font-medium ${
          primaryPriceSource.is_stale
            ? STATUS_TONES.warning
            : STATUS_TONES.success
        }`}
      >
        {primaryPriceSource.is_stale ? 'Stale' : 'Fresh'}
      </span>
    </section>
  );
}
