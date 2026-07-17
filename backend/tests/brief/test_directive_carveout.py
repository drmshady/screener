"""Feature 018 T006 — directive carve-out truth table (contracts/directive-carveout.md).

`brief_directive_enabled()` returns True ONLY when all of: the personal-use
directive flag is ON, the single-owner access gate is enforced (owner secret set),
and the instance is not multi-user. It is SEPARATE from `personal_use_directive()`,
whose hosted force-OFF must stay unchanged (proving the carve-out did not broaden
directive output to any other surface).
"""
from __future__ import annotations

import pytest

from backend.src.lib import flags
from backend.src.lib.flags import brief_directive_enabled, personal_use_directive


def _clear(monkeypatch) -> None:
    for var in (
        "SCREENER_PERSONAL_USE_DIRECTIVE",
        "SCREENER_OWNER_SECRET",
        "SCREENER_MULTI_USER",
        "SCREENER_HOSTED_MODE",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.parametrize(
    "directive_flag, owner_secret, multi_user, expected",
    [
        # PERSONAL_USE_DIRECTIVE off ⇒ always neutral regardless of gate.
        ("0", None, "0", False),
        ("0", "sekret", "0", False),
        # On but no enforced single-owner gate ⇒ neutral (FR-006 default).
        ("1", None, "0", False),
        # On + owner secret set + single-owner ⇒ directive permitted.
        ("1", "sekret", "0", True),
        # On + owner secret set but multi-user ⇒ reverts to neutral.
        ("1", "sekret", "1", False),
    ],
)
def test_truth_table(monkeypatch, directive_flag, owner_secret, multi_user, expected) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("SCREENER_PERSONAL_USE_DIRECTIVE", directive_flag)
    monkeypatch.setenv("SCREENER_MULTI_USER", multi_user)
    if owner_secret is not None:
        monkeypatch.setenv("SCREENER_OWNER_SECRET", owner_secret)
    assert brief_directive_enabled() is expected


def test_carveout_does_not_broaden_general_ui_directive(monkeypatch) -> None:
    """`personal_use_directive()` must still force OFF under hosted mode even when
    the brief carve-out is True — no other surface's directive behaviour moves."""
    _clear(monkeypatch)
    monkeypatch.setenv("SCREENER_PERSONAL_USE_DIRECTIVE", "1")
    monkeypatch.setenv("SCREENER_OWNER_SECRET", "sekret")
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")

    assert brief_directive_enabled() is True
    assert personal_use_directive() is False  # general UI stays neutral when hosted


def test_helper_exists() -> None:
    assert callable(flags.brief_directive_enabled)
    assert callable(flags.brief_enabled)
