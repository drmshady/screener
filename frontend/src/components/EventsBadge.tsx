import type { Candidate } from '@/lib/api';
import { STATUS_TONES } from '@/lib/design';

function sourceTitle(candidate: Candidate) {
  return candidate.events_source_as_of ? `Events source as of ${candidate.events_source_as_of.slice(0, 10)}` : undefined;
}

export function EventsBadge({ candidate }: { candidate: Candidate }) {
  const badges = [];
  if (candidate.days_to_earnings !== null && candidate.days_to_earnings !== undefined && candidate.days_to_earnings >= 0) {
    badges.push(
      <span
        className={`inline-flex border px-2 py-1 text-xs font-medium ${STATUS_TONES.warning}`}
        key="earnings"
        title={sourceTitle(candidate)}
      >
        Earnings in {candidate.days_to_earnings} days
      </span>,
    );
  }
  if (candidate.recent_8k_count_30d > 0) {
    badges.push(
      <span
        className={`inline-flex border px-2 py-1 text-xs font-medium ${STATUS_TONES.info}`}
        key="8k"
        title={sourceTitle(candidate)}
      >
        Material news ({candidate.recent_8k_count_30d} in 30d)
      </span>,
    );
  }

  if (!badges.length) {
    return <span className="text-xs text-slate-400">-</span>;
  }

  return <div className="flex flex-wrap gap-1">{badges}</div>;
}
