from __future__ import annotations

from datetime import date

from scripts._session_guard import resolve_guard_decision


def test_noop_when_no_new_completed_session():
    decision = resolve_guard_decision(
        latest_session=date(2026, 6, 19), published_data_as_of=date(2026, 6, 19)
    )
    assert decision.outcome == "noop"


def test_noop_when_published_is_already_newer():
    # Defensive: a published date ahead of "latest completed" (clock skew /
    # stale guard input) must still short-circuit, never regress data_as_of.
    decision = resolve_guard_decision(
        latest_session=date(2026, 6, 19), published_data_as_of=date(2026, 6, 22)
    )
    assert decision.outcome == "noop"


def test_proceed_when_a_new_session_is_available():
    decision = resolve_guard_decision(
        latest_session=date(2026, 6, 22), published_data_as_of=date(2026, 6, 19)
    )
    assert decision.outcome == "proceed"


def test_proceed_when_nothing_is_published_yet():
    decision = resolve_guard_decision(
        latest_session=date(2026, 6, 19), published_data_as_of=None
    )
    assert decision.outcome == "proceed"
