"use client";

import { useEffect, useState } from 'react';
import {
  MarketEventsResponse,
  MarketEventsResponseSchema,
  fetchApi,
} from '@/lib/api';
import { Abbr } from '@/components/Abbr';
import { eventTerm } from '@/lib/events';
import { STATUS_TONES } from '@/lib/design';

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/New_York',
  }).format(new Date(value));
}

function formatDateOnly(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'America/New_York',
  }).format(new Date(value));
}

export function MarketEventsPanel({ daysAhead = 7 }: { daysAhead?: number }) {
  const [data, setData] = useState<MarketEventsResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchApi(`/events/market?days_ahead=${daysAhead}`, MarketEventsResponseSchema)
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [daysAhead]);

  return (
    <section className="panel space-y-3 p-5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Market Events</h2>
          <p className="text-sm text-slate-600">FOMC, CPI, NFP, PCE, and PPI schedule.</p>
        </div>
        {data?.is_stale ? (
          <span className={`border px-2 py-1 text-xs font-medium ${STATUS_TONES.warning}`}>
            Stale events data
          </span>
        ) : null}
      </div>

      {failed ? (
        <div className={`${STATUS_TONES.warning} border p-3 text-sm`}>Market events unavailable.</div>
      ) : null}

      {!data && !failed ? <div className="text-sm text-slate-500">Loading market events...</div> : null}

      {data ? (
        <div className="divide-y divide-slate-200 border border-slate-200">
          {data.events.map((event) => (
            <a
              className="grid gap-1 p-3 text-sm hover:bg-slate-50 sm:grid-cols-[80px_minmax(0,1fr)_160px]"
              href={event.source_url}
              key={event.event_id}
              rel="noreferrer"
              target="_blank"
            >
              <span className="font-semibold text-slate-950">
                <Abbr term={eventTerm(event.event_type)} />
              </span>
              <span className="text-slate-700">{event.expected_value || event.actual_value || event.status}</span>
              <span className="text-slate-600 sm:text-right">{formatDate(event.scheduled_at)} ET</span>
            </a>
          ))}
          {data.events.length === 0 ? (
            <div className="p-3 text-sm text-slate-500">
              {data.schedule_extends_through
                ? `Official schedule extends through ${formatDateOnly(data.schedule_extends_through)}.`
                : 'No scheduled events in this window.'}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
