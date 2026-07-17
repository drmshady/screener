"""Owner-only email transport for the daily brief (feature 018).

Sends the rendered brief to the single allowlisted owner via Gmail SMTP with an
app password, using only the Python stdlib (`smtplib` + `email.message`) — no new
dependency (research Decision 5). The transport is injectable so tests exercise
send/retry/failure against a stub with no live network.

Non-negotiables:
- Recipient guard (FR-009): the `To:` address is forced to
  `SCREENER_BRIEF_RECIPIENT`; any caller-supplied address is overridden.
- Bounded retry (research Decision 6): up to `MAX_ATTEMPTS` on transient SMTP
  errors, then raise `BriefSendError` so the router records `failed` / returns 502.
- Secrets (FR-015): host/port/user/password/recipient come from process env via
  `lib/flags.py` accessors; the app password is NEVER placed in an exception
  message or log.
"""
from __future__ import annotations

import smtplib
import time
from email.message import EmailMessage
from typing import Callable

from ..lib import flags

MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 0.05

# Transport signature: keyword-only host/port/user/password/message.
Transport = Callable[..., None]


class BriefSendError(RuntimeError):
    """Raised when the brief cannot be delivered (config error or retries exhausted).

    The message is deliberately redacted — it never contains the app password.
    """


def _default_transport(*, host: str, port: int, user: str, password: str,
                       message: EmailMessage) -> None:
    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(message)


def _build_message(subject: str, text_body: str, html_body: str,
                   sender: str, recipient: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def send_brief(
    subject: str,
    text_body: str,
    html_body: str,
    *,
    recipient: str | None = None,
    transport: Transport | None = None,
) -> int:
    """Send the brief to the owner. Returns the number of attempts made.

    `recipient` is IGNORED for addressing — the brief can only go to
    `SCREENER_BRIEF_RECIPIENT` (FR-009); the parameter exists so callers may pass
    a value for symmetry, but it is overridden. Raises `BriefSendError` on a
    configuration problem or after `MAX_ATTEMPTS` transient failures.
    """
    owner = flags.brief_recipient()
    if not owner:
        raise BriefSendError("SCREENER_BRIEF_RECIPIENT is not configured.")
    user = flags.brief_smtp_user()
    password = flags.brief_smtp_password()
    if not user or not password:
        raise BriefSendError("SMTP credentials are not configured.")

    host = flags.brief_smtp_host()
    port = flags.brief_smtp_port()
    send = transport or _default_transport
    message = _build_message(subject, text_body, html_body, user, owner)

    last_error_class = "unknown"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            send(host=host, port=port, user=user, password=password, message=message)
            return attempt
        except Exception as exc:  # transient/permanent SMTP or network error
            last_error_class = type(exc).__name__
            if attempt < MAX_ATTEMPTS:
                time.sleep(_BACKOFF_SECONDS)

    # Redacted: only the error class, never the password or its value.
    raise BriefSendError(
        f"Brief send failed after {MAX_ATTEMPTS} attempts ({last_error_class})."
    )
