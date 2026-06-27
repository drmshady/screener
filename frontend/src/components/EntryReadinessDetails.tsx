import type { Candidate } from '@/lib/api';

type EntryTiming = NonNullable<Candidate['entry_timing']>;
type EntryComponent = EntryTiming['components'][number];
type EntryDisqualifier = NonNullable<EntryTiming['disqualifiers']>[number];

function stateLabel(state: EntryTiming['state']) {
  if (state === 'entry_ready') return 'Entry-ready';
  if (state === 'not_entry_ready') return 'Not entry-ready';
  return 'Entry undetermined';
}

function labelFromKey(value: string) {
  return value.replaceAll('_', ' ');
}

function formatValue(value: number | null | undefined, name?: string) {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  if (
    name === 'pivot_proximity' ||
    name === 'base_depth' ||
    name === 'not_extended' ||
    name === 'dist_above_pivot' ||
    name === 'dist_above_sma_200'
  ) {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (name === 'volume_confirmation' || name === 'breakout_volume_ratio') {
    return `${value.toFixed(2)}x`;
  }
  if (name === 'pivot') {
    return value.toFixed(2);
  }
  return value.toFixed(1);
}

function componentClass(status: EntryComponent['status']) {
  if (status === 'pass') return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  if (status === 'fail') return 'border-amber-200 bg-amber-50 text-amber-800';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function disqualifierClass(disqualifier: EntryDisqualifier) {
  if (!disqualifier.triggered) return 'border-slate-200 bg-slate-50 text-slate-600';
  if (disqualifier.forces_not_entry_ready) return 'border-rose-200 bg-rose-50 text-rose-800';
  return 'border-amber-200 bg-amber-50 text-amber-800';
}

export function EntryReadinessDetails({ entryTiming }: { entryTiming: EntryTiming }) {
  const diagnostics = entryTiming.diagnostics;
  const diagnosticItems = [
    { label: 'Pivot', value: formatValue(diagnostics.pivot, 'pivot') },
    {
      label: 'Base',
      value:
        diagnostics.base_type && diagnostics.base_type !== 'none'
          ? diagnostics.base_type.replaceAll('_', '-')
          : null,
    },
    { label: 'Base length', value: formatValue(diagnostics.base_length_weeks) },
    { label: 'Base depth', value: formatValue(diagnostics.base_depth, 'base_depth') },
    {
      label: 'Breakout volume',
      value: formatValue(diagnostics.breakout_volume_ratio, 'breakout_volume_ratio'),
    },
    { label: 'Above pivot', value: formatValue(diagnostics.dist_above_pivot, 'dist_above_pivot') },
    {
      label: 'Above SMA-200',
      value: formatValue(diagnostics.dist_above_sma_200, 'dist_above_sma_200'),
    },
  ].filter((item) => item.value !== null);
  const triggeredDisqualifiers = entryTiming.disqualifiers.filter((item) => item.triggered);

  return (
    <div className="mt-4 border border-slate-200">
      <div className="border-b border-slate-200 bg-slate-50 px-3 py-2">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <h3 className="text-xs font-semibold uppercase text-slate-600">Entry readiness</h3>
          <span className="border border-slate-300 bg-white px-2 py-0.5 text-xs font-semibold text-slate-900">
            {stateLabel(entryTiming.state)}
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-600">{entryTiming.summary}</p>
      </div>

      <div className="space-y-3 p-3">
        <div className="grid gap-2 sm:grid-cols-2">
          {entryTiming.components.map((component) => (
            <div className={`border px-3 py-2 text-sm ${componentClass(component.status)}`} key={component.name}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold capitalize">{labelFromKey(component.name)}</span>
                <span className="text-xs font-semibold uppercase">{component.status}</span>
              </div>
              <div className="mt-1 text-xs">
                {formatValue(component.value, component.name) ? (
                  <span className="font-semibold">{formatValue(component.value, component.name)} - </span>
                ) : null}
                <span>{component.reason}</span>
              </div>
            </div>
          ))}
        </div>

        {diagnosticItems.length > 0 ? (
          <dl className="grid gap-2 text-sm sm:grid-cols-4">
            {diagnosticItems.map((item) => (
              <div className="border border-slate-100 bg-white px-3 py-2" key={item.label}>
                <dt className="text-xs uppercase text-slate-500">{item.label}</dt>
                <dd className="font-semibold text-slate-950">{item.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}

        {entryTiming.disqualifiers.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {(triggeredDisqualifiers.length > 0 ? triggeredDisqualifiers : entryTiming.disqualifiers).map(
              (disqualifier) => (
                <span
                  className={`border px-2 py-1 text-xs ${disqualifierClass(disqualifier)}`}
                  key={disqualifier.name}
                  title={disqualifier.reason}
                >
                  {labelFromKey(disqualifier.name)}
                  {disqualifier.triggered ? ' flagged' : ' clear'}
                </span>
              ),
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
