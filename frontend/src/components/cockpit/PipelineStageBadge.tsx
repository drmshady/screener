"use client";

import type { PipelineStage } from '@/lib/pipeline';
import { STATUS_TONES } from '@/lib/design';

// Neutral lifecycle nouns — no directive verbs. The badge describes where a
// ticker sits in the watch → ready → staged → owned → managing → exited
// pipeline; it never tells the owner to act.
const STAGE_META: Record<PipelineStage, { label: string; tone: string }> = {
  watching: { label: 'Watching', tone: STATUS_TONES.neutral },
  ready: { label: 'Ready', tone: STATUS_TONES.success },
  staged: { label: 'Staged', tone: STATUS_TONES.info },
  owned: { label: 'Owned', tone: STATUS_TONES.info },
  managing: { label: 'Managing', tone: STATUS_TONES.warning },
  exited: { label: 'Exited', tone: STATUS_TONES.neutral },
};

/**
 * A compact, cross-surface badge for a ticker's derived pipeline stage. Renders
 * nothing when the stage is unknown (`null`), so it can be dropped anywhere a
 * ticker appears without guarding at every call site.
 */
export function PipelineStageBadge({ stage }: { stage: PipelineStage | null }) {
  if (!stage) {
    return null;
  }
  const meta = STAGE_META[stage];
  return (
    <span
      className={`inline-flex border px-2 py-0.5 text-xs font-semibold ${meta.tone}`}
      data-testid="pipeline-stage-badge"
      title={`Pipeline stage: ${meta.label}`}
    >
      {meta.label}
    </span>
  );
}
