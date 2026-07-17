"""Feature 018 T010 — owner-only email transport (contracts/email-delivery.md).

`brief.email.send_brief` sends via an injectable transport (no live network in
tests): a successful send calls the transport once with the owner recipient; a
foreign recipient is overridden to `SCREENER_BRIEF_RECIPIENT` (FR-009); transient
failures retry within a bound; a permanent failure raises after the bound with no
plaintext password in the message (FR-012/FR-015).
"""
from __future__ import annotations

import smtplib

import pytest

from backend.src.brief import email as brief_email


class _StubTransport:
    """Records send calls; optionally fails the first N attempts."""

    def __init__(self, fail_times: int = 0, exc: Exception | None = None) -> None:
        self.fail_times = fail_times
        self.exc = exc or smtplib.SMTPException("transient")
        self.calls: list[dict] = []

    def __call__(self, *, host, port, user, password, message) -> None:
        self.calls.append(
            {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "to": message["To"],
                "subject": message["Subject"],
            }
        )
        if len(self.calls) <= self.fail_times:
            raise self.exc


def _env(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_BRIEF_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SCREENER_BRIEF_SMTP_PORT", "587")
    monkeypatch.setenv("SCREENER_BRIEF_SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SCREENER_BRIEF_SMTP_PASSWORD", "super-secret-app-pw")
    monkeypatch.setenv("SCREENER_BRIEF_RECIPIENT", "owner@example.com")


def test_successful_send_calls_transport_once_with_owner(monkeypatch) -> None:
    _env(monkeypatch)
    transport = _StubTransport()
    brief_email.send_brief("Daily brief", "text body", "<p>html</p>", transport=transport)
    assert len(transport.calls) == 1
    assert transport.calls[0]["to"] == "owner@example.com"
    assert transport.calls[0]["subject"] == "Daily brief"


def test_foreign_recipient_is_overridden_to_owner(monkeypatch) -> None:
    _env(monkeypatch)
    transport = _StubTransport()
    brief_email.send_brief(
        "Daily brief",
        "text",
        "<p>html</p>",
        recipient="attacker@evil.example",
        transport=transport,
    )
    assert transport.calls[0]["to"] == "owner@example.com"


def test_transient_failure_retries_then_succeeds(monkeypatch) -> None:
    _env(monkeypatch)
    transport = _StubTransport(fail_times=2)
    attempts = brief_email.send_brief(
        "Daily brief", "text", "<p>html</p>", transport=transport
    )
    assert len(transport.calls) == 3
    assert attempts == 3


def test_permanent_failure_raises_without_leaking_password(monkeypatch) -> None:
    _env(monkeypatch)
    transport = _StubTransport(fail_times=99)
    with pytest.raises(brief_email.BriefSendError) as excinfo:
        brief_email.send_brief("Daily brief", "text", "<p>html</p>", transport=transport)
    assert "super-secret-app-pw" not in str(excinfo.value)
    # Bounded retry: at most the configured max attempts.
    assert len(transport.calls) == brief_email.MAX_ATTEMPTS


def test_missing_recipient_raises(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_BRIEF_SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SCREENER_BRIEF_SMTP_PASSWORD", "pw")
    monkeypatch.delenv("SCREENER_BRIEF_RECIPIENT", raising=False)
    transport = _StubTransport()
    with pytest.raises(brief_email.BriefSendError):
        brief_email.send_brief("s", "t", "<p>h</p>", transport=transport)
    assert transport.calls == []
