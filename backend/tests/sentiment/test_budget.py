from __future__ import annotations

from decimal import Decimal

from backend.src.sentiment.budget import BudgetGuard


def test_paid_call_proceeds_only_within_cap(tmp_path):
    guard = BudgetGuard(tmp_path / "spend.json", cap_usd=Decimal("0.010"), period="2026-07")

    assert guard.reserve_if_allowed(Decimal("0.004")) is True
    assert guard.reserve_if_allowed(Decimal("0.007")) is False
    assert guard.current().estimated_spend_usd == Decimal("0.004")


def test_cache_hits_are_unmetered(tmp_path):
    guard = BudgetGuard(tmp_path / "spend.json", cap_usd=Decimal("0.001"), period="2026-07")

    assert guard.reserve_if_allowed(Decimal("0.000"), cache_hit=True) is True
    assert guard.current().estimated_spend_usd == Decimal("0")
