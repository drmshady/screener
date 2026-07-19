"use client";

import type { Candidate, InstructionBlock, PortfolioHoldingWithLevels } from '@/lib/api';
import type { PipelineStage } from '@/lib/pipeline';
import { AsOfBadge } from '@/components/AsOfBadge';
import { EventsBadge } from '@/components/EventsBadge';
import { PipelineStageBadge } from '@/components/cockpit/PipelineStageBadge';
import { SentimentReport } from '@/components/SentimentReport';
import { STATUS_TONES } from '@/lib/design';
import { formatMoney } from '@/lib/format';

/**
 * One at-a-glance decision card per open holding (Feature 019, US1): status/stage,
 * current stop + target (and trailing), current price + unrealized P&L, recent
 * news/events, an auto-loaded AI sentiment/narrative, and a deterministic
 * Hold/Trim/Sell call — or the neutral status label when the single-owner
 * directive carve-out is off (FR-008). The shell renders immediately; the
 * sentiment/news sections fill in lazily so the decision surface never blocks
 * on them (SC-005). Every card carries `data_as_of` + the disclaimer (FR-012).
 */

const DIRECTIVE_LABEL: Record<NonNullable<InstructionBlock['directive']>, string> = {
  hold: 'Hold',
  trim: 'Trim',
  sell: 'Sell',
};

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/** Neutral tone for a status label — colour reflects severity, not a directive. */
function statusTone(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes('breach')) return STATUS_TONES.danger;
  if (lower.includes('near') || lower.includes('heat')) return STATUS_TONES.warning;
  if (lower.includes('unavailable')) return STATUS_TONES.neutral;
  if (lower.includes('target') || lower.includes('protected')) return STATUS_TONES.success;
  return STATUS_TONES.neutral;
}

function directiveTone(directive: NonNullable<InstructionBlock['directive']>): string {
  if (directive === 'sell') return STATUS_TONES.danger;
  if (directive === 'trim') return STATUS_TONES.warning;
  return STATUS_TONES.success;
}

export interface PositionCardProps {
  holding: PortfolioHoldingWithLevels;
  /** Whether the Hold/Trim/Sell verb may render (single-owner carve-out, FR-008). */
  directiveEnabled: boolean;
  /** Optional lifecycle stage (browser-owned) — refines the neutral status. */
  stage?: PipelineStage | null;
  /** Optional candidate carrying events/news facts (source + as-of). */
  candidate?: Candidate | null;
  /** Response-level as-of for the card footer (FR-012). */
  dataAsOf?: string | null;
  disclaimer: string;
  /** Auto-load sentiment in the background (SC-005). Off in unit tests. */
  enableSentiment?: boolean;
}

export function PositionCard({
  holding,
  directiveEnabled,
  stage = null,
  candidate = null,
  dataAsOf = null,
  disclaimer,
  enableSentiment = true,
}: PositionCardProps) {
  const instruction = holding.instruction ?? null;
  const current = holding.levels?.current_condition ?? null;
  const trailing = holding.levels?.trailing ?? null;
  const levelsAvailable = !!current && current.levels_state === 'ok';

  const showVerb = directiveEnabled && !!instruction?.directive;
  const unrealized = holding.unrealized_pl;
  const unrealizedGain = unrealized != null ? Number(unrealized) >= 0 : true;

  return (
    <article
      aria-label={`Position card for ${holding.ticker}`}
      className="flex flex-col gap-4 border border-slate-200 bg-white p-5 shadow-sm"
      data-testid="position-card"
    >
      {/* Header: ticker, stage, and the call (verb or neutral status). */}
      <header className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold text-slate-950">{holding.ticker}</h3>
            <PipelineStageBadge stage={stage} />
          </div>
          <p className="mt-0.5 text-xs text-slate-500">{holding.sector}</p>
        </div>
        <div className="text-right">
          {showVerb && instruction?.directive ? (
            <span
              className={`inline-flex border px-2.5 py-1 text-sm font-semibold ${directiveTone(instruction.directive)}`}
              data-testid="instruction-directive"
            >
              {DIRECTIVE_LABEL[instruction.directive]}
            </span>
          ) : instruction ? (
            <span
              className={`inline-flex border px-2.5 py-1 text-sm font-semibold ${statusTone(instruction.status_label)}`}
              data-testid="instruction-status"
            >
              {instruction.status_label}
            </span>
          ) : (
            <span className="text-xs text-slate-400">No status</span>
          )}
        </div>
      </header>

      {instruction?.rationale ? (
        <p className="text-sm text-slate-600" data-testid="instruction-rationale">
          {instruction.rationale}
        </p>
      ) : null}

      {/* Position facts. */}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs uppercase text-slate-500">Shares</dt>
          <dd className="text-slate-900">
            {Number(holding.net_quantity).toLocaleString(undefined, { maximumFractionDigits: 4 })}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-500">Avg cost</dt>
          <dd className="text-slate-900">{formatMoney(holding.avg_cost, holding.ticker)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-500">Price</dt>
          <dd className="text-slate-900">
            {holding.current_price ? formatMoney(holding.current_price, holding.ticker) : '—'}
          </dd>
        </div>
        <div className="col-span-2 sm:col-span-3">
          <dt className="text-xs uppercase text-slate-500">Unrealized P/L</dt>
          <dd className={unrealizedGain ? 'text-emerald-700' : 'text-rose-700'}>
            {unrealized != null ? (
              <>
                {formatMoney(unrealized, holding.ticker)}
                {holding.unrealized_pl_pct != null ? ` (${percent(holding.unrealized_pl_pct)})` : ''}
              </>
            ) : (
              <span className="text-slate-500">—</span>
            )}
          </dd>
        </div>
      </dl>

      {/* Levels: stop / target / trailing, or an explicit unavailable state. */}
      <section aria-label="Levels" className="border-t border-slate-100 pt-3 text-sm">
        {levelsAvailable ? (
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
            <div>
              <span className="text-xs uppercase text-slate-500">Stop</span>
              <div className="text-slate-900">
                {current?.stop_loss ? formatMoney(current.stop_loss, holding.ticker) : '—'}
              </div>
            </div>
            <div>
              <span className="text-xs uppercase text-slate-500">Target</span>
              <div className="text-slate-900">
                {current?.take_profit ? formatMoney(current.take_profit, holding.ticker) : '—'}
              </div>
            </div>
            <div>
              <span className="text-xs uppercase text-slate-500">Trailing</span>
              <div className="text-slate-900">
                {trailing?.stop_loss ? formatMoney(trailing.stop_loss, holding.ticker) : '—'}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-slate-500" data-testid="levels-unavailable">
            Levels unavailable — insufficient data to derive a stop or target.
          </p>
        )}
      </section>

      {/* Recent news/events (source + as-of on the badge) or explicit "nothing new". */}
      <section aria-label="Recent news and events" className="text-sm">
        <span className="text-xs uppercase text-slate-500">News &amp; events</span>
        <div className="mt-1">
          {candidate ? (
            <EventsBadge candidate={candidate} />
          ) : (
            <span className="text-xs text-slate-400" data-testid="events-nothing-new">
              Nothing new
            </span>
          )}
        </div>
      </section>

      {/* Auto-loaded sentiment/narrative (lazy — does not block the shell). */}
      {enableSentiment ? (
        <section aria-label="Sentiment" className="border-t border-slate-100 pt-3">
          <SentimentReport initialSelections={[{ ticker: holding.ticker, origin: 'holding' }]} />
        </section>
      ) : null}

      <footer className="mt-1 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
        {dataAsOf ? <AsOfBadge date={dataAsOf} /> : null}
        {holding.data_as_of ? <AsOfBadge date={holding.data_as_of} /> : null}
        <span data-testid="card-disclaimer">{disclaimer}</span>
      </footer>
    </article>
  );
}
