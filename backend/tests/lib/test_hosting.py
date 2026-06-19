from __future__ import annotations

import pytest

from backend.src.lib import hosting


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("", False),
    ],
)
def test_hosted_mode_reflects_env(monkeypatch, value: str, expected: bool) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", value)

    assert hosting.hosted_mode() is expected


def test_hosted_mode_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("SCREENER_HOSTED_MODE", raising=False)

    assert hosting.hosted_mode() is False


@pytest.mark.parametrize("value", [None, "", "   "])
def test_require_hosted_config_raises_when_secret_missing(
    monkeypatch, value: str | None
) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    if value is None:
        monkeypatch.delenv("SCREENER_OWNER_SECRET", raising=False)
    else:
        monkeypatch.setenv("SCREENER_OWNER_SECRET", value)

    with pytest.raises(RuntimeError, match="SCREENER_OWNER_SECRET"):
        hosting.require_hosted_config()


def test_require_hosted_config_passes_when_hosted_secret_present(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.setenv("SCREENER_OWNER_SECRET", "owner-secret")

    hosting.require_hosted_config()


def test_require_hosted_config_noops_when_local(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "0")
    monkeypatch.delenv("SCREENER_OWNER_SECRET", raising=False)

    hosting.require_hosted_config()


def test_snapshot_root_resolves_backend_data() -> None:
    root = hosting.snapshot_root()

    assert root.name == "data"
    assert root.parent.name == "backend"
