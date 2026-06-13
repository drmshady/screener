import type { Candidate, ShariahStatus } from '@/lib/api';
import { STATUS_TONES } from '@/lib/design';

const SOURCE_LABELS: Record<string, string> = {
  spus_holdings: 'SPUS',
  halal_terminal: 'Halal Terminal',
  finispia: 'Finispia',
};

type BadgeInput = Partial<Candidate> & Partial<ShariahStatus>;

function sourceLabel(source?: string | null) {
  if (!source) {
    return 'Unknown';
  }
  return SOURCE_LABELS[source] ?? source;
}

function asOfText(value?: string | null) {
  if (!value) {
    return null;
  }
  return value.slice(0, 10);
}

export function ShariahBadge({ status }: { status: BadgeInput | null | undefined }) {
  if (!status) {
    return <span className={`inline-flex border px-2 py-1 text-xs ${STATUS_TONES.neutral}`}>Unknown</span>;
  }

  const sourceKind = status.source_kind ?? status.shariah_source_kind;
  const externalSource = status.external_source_name ?? status.shariah_external_source_name;
  const externalAsOf = status.external_source_as_of ?? status.shariah_source_as_of;
  const userNote = status.user_note ?? status.shariah_user_note;
  const isStale = Boolean(status.is_stale ?? status.shariah_is_stale);
  const isCompliant = Boolean(status.is_compliant ?? status.shariah_compliant);
  const title = [
    userNote ? `Note: ${userNote}` : null,
    asOfText(externalAsOf) ? `Source as of ${asOfText(externalAsOf)}` : null,
    isStale ? 'Source may be stale' : null,
  ]
    .filter(Boolean)
    .join(' | ');

  if (sourceKind === 'excluded_by_user') {
    return (
      <span className={`inline-flex border px-2 py-1 text-xs font-medium ${STATUS_TONES.danger}`} title={title || undefined}>
        Excluded by user
      </span>
    );
  }

  if (isCompliant && sourceKind === 'external') {
    return (
      <span className={`inline-flex border px-2 py-1 text-xs font-medium ${STATUS_TONES.success}`} title={title || undefined}>
        Shariah-compliant ({sourceLabel(externalSource)})
        {isStale ? ' - stale' : ''}
      </span>
    );
  }

  if (isCompliant && sourceKind === 'user') {
    return (
      <span className={`inline-flex border px-2 py-1 text-xs font-medium ${STATUS_TONES.info}`} title={title || undefined}>
        Shariah-compliant (User)
      </span>
    );
  }

  if (sourceKind === 'not_listed' || status.is_compliant === false) {
    return (
      <span className={`inline-flex border px-2 py-1 text-xs font-medium ${STATUS_TONES.warning}`} title={title || undefined}>
        Not Shariah-compliant
      </span>
    );
  }

  return <span className={`inline-flex border px-2 py-1 text-xs ${STATUS_TONES.neutral}`}>Unknown</span>;
}
