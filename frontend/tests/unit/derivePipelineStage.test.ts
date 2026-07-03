import { describe, expect, test } from 'vitest';
import {
  derivePipelineStage,
  holdingNeedsAttention,
  type StageHolding,
} from '../../src/lib/pipeline';

// A minimal open holding with no attention signals (owned, not managing).
function openHolding(overrides: Partial<StageHolding> = {}): StageHolding {
  return { status: 'open', levels: null, risk: null, ...overrides };
}

function levelBlock(status: string) {
  // Only `status` matters to the selector; the rest is filler to satisfy the shape.
  return {
    levels_state: 'ok' as const,
    rationale: '',
    status: status as never,
  };
}

describe('derivePipelineStage precedence', () => {
  test('open holding with no attention signals is owned', () => {
    expect(derivePipelineStage({ holding: openHolding(), onWatchlist: true })).toBe('owned');
  });

  test('open holding escalates to managing when a level block is past holding', () => {
    const holding = openHolding({
      levels: {
        original_plan: levelBlock('holding'),
        current_condition: levelBlock('stop_breached'),
        trailing: null,
      } as unknown as StageHolding['levels'],
    });
    expect(derivePipelineStage({ holding })).toBe('managing');
  });

  test('open holding escalates to managing when risk is over budget', () => {
    const holding = openHolding({ risk: { over_risk: true } as StageHolding['risk'] });
    expect(derivePipelineStage({ holding })).toBe('managing');
  });

  test('insufficient_data level alone does not escalate to managing', () => {
    const holding = openHolding({
      levels: {
        original_plan: levelBlock('insufficient_data'),
        current_condition: levelBlock('holding'),
        trailing: null,
      } as unknown as StageHolding['levels'],
    });
    expect(derivePipelineStage({ holding })).toBe('owned');
  });

  test('holdings-derived stage outranks a manual exited override', () => {
    expect(
      derivePipelineStage({ holding: openHolding(), manualStage: 'exited' }),
    ).toBe('owned');
  });

  test('ready<->owned: a stale board still-ready signal never flickers a held name back to ready', () => {
    expect(
      derivePipelineStage({ holding: openHolding(), entryTimingState: 'entry_ready' }),
    ).toBe('owned');
  });

  test('manual exited outranks a board ready signal when not held', () => {
    expect(
      derivePipelineStage({ manualStage: 'exited', entryTimingState: 'entry_ready', onWatchlist: true }),
    ).toBe('exited');
  });

  test('board ready outranks a manual staged override', () => {
    expect(
      derivePipelineStage({ manualStage: 'staged', entryTimingState: 'entry_ready', onWatchlist: true }),
    ).toBe('ready');
  });

  test('entry-ready and not held is ready', () => {
    expect(
      derivePipelineStage({ entryTimingState: 'entry_ready', onWatchlist: true }),
    ).toBe('ready');
  });

  test('manual staged shows when not ready and outranks plain watching', () => {
    expect(
      derivePipelineStage({ manualStage: 'staged', entryTimingState: 'not_entry_ready', onWatchlist: true }),
    ).toBe('staged');
  });

  test('a saved watchlist entry defaults to watching', () => {
    expect(derivePipelineStage({ onWatchlist: true })).toBe('watching');
  });

  test('nothing known yields null', () => {
    expect(derivePipelineStage({})).toBeNull();
  });

  test('a closed holding is not owned (falls through to lifecycle rules)', () => {
    expect(
      derivePipelineStage({ holding: openHolding({ status: 'closed' }), onWatchlist: true }),
    ).toBe('watching');
  });
});

describe('holdingNeedsAttention', () => {
  test('flags over-risk holdings', () => {
    expect(holdingNeedsAttention(openHolding({ risk: { over_risk: true } as StageHolding['risk'] }))).toBe(true);
  });

  test('flags a target-reached level block', () => {
    expect(
      holdingNeedsAttention(
        openHolding({
          levels: {
            original_plan: levelBlock('holding'),
            current_condition: levelBlock('target_reached'),
            trailing: null,
          } as unknown as StageHolding['levels'],
        }),
      ),
    ).toBe(true);
  });

  test('a calm holding needs no attention', () => {
    expect(
      holdingNeedsAttention(
        openHolding({
          levels: {
            original_plan: levelBlock('holding'),
            current_condition: levelBlock('holding'),
            trailing: null,
          } as unknown as StageHolding['levels'],
        }),
      ),
    ).toBe(false);
  });
});
