from __future__ import annotations

from backend.src.lib.flags import personal_use_directive


def test_personal_use_directive_forced_off_when_hosted(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.setenv("SCREENER_PERSONAL_USE_DIRECTIVE", "1")

    assert personal_use_directive() is False


def test_personal_use_directive_keeps_local_env_behavior(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "0")
    monkeypatch.setenv("SCREENER_PERSONAL_USE_DIRECTIVE", "1")

    assert personal_use_directive() is True


def test_personal_use_directive_defaults_off_when_local(monkeypatch) -> None:
    monkeypatch.delenv("SCREENER_HOSTED_MODE", raising=False)
    monkeypatch.delenv("SCREENER_PERSONAL_USE_DIRECTIVE", raising=False)

    assert personal_use_directive() is False
