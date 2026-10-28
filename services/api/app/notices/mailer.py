"""Outgoing email for student notices and document requests (D23).

Only hosts in SMTP_ALLOWED_HOSTS are ever contacted (Mailpit in the demo); ALLOW_REAL_SMTP
is never set. Messages go out over one SMTP connection per MAIL_BATCH.
"""

from __future__ import annotations

import smtplib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings, get_settings

MAIL_BATCH = 500


@dataclass(frozen=True, slots=True)
class MailMessage:
    to: str
    subject: str
    body: str
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MailResult:
    ok: bool
    # a PII-free sentence for notifications.last_error
    error: str | None = None
    transient: bool = False


class Mailer(Protocol):
    def send_many(self, messages: Sequence[MailMessage]) -> list[MailResult]: ...


class SmtpRefused(RuntimeError):
    """The configured SMTP host is not on the allow list."""


def smtp_host_allowed(host: str, settings: Settings) -> bool:
    return settings.allow_real_smtp or host in settings.smtp_allowed_hosts


def _email(message: MailMessage, sender: str) -> EmailMessage:
    email = EmailMessage()
    email["From"] = sender
    email["To"] = message.to
    email["Subject"] = message.subject
    for name, value in message.headers.items():
        email[name] = value
    email.set_content(message.body)
    return email


class SmtpMailer:
    """Stdlib smtplib, synchronous; async callers use asyncio.to_thread."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not smtp_host_allowed(self.settings.smtp_host, self.settings):
            raise SmtpRefused(f"SMTP host {self.settings.smtp_host!r} is not allowed")

    def send_many(self, messages: Sequence[MailMessage]) -> list[MailResult]:
        results: list[MailResult] = []
        for start in range(0, len(messages), MAIL_BATCH):
            results.extend(self._send_batch(messages[start : start + MAIL_BATCH]))
        return results

    def _send_batch(self, batch: Sequence[MailMessage]) -> list[MailResult]:
        try:
            smtp = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10)
        except OSError:
            return [MailResult(ok=False, error="Mail server unreachable.", transient=True)] * len(
                batch
            )
        results: list[MailResult] = []
        with smtp:
            for message in batch:
                try:
                    smtp.send_message(_email(message, self.settings.notice_from))
                    results.append(MailResult(ok=True))
                except smtplib.SMTPRecipientsRefused:
                    results.append(MailResult(ok=False, error="Address refused."))
                except (smtplib.SMTPException, OSError):
                    results.append(MailResult(ok=False, error="Mail server error.", transient=True))
        return results


class MemoryMailer:
    """For tests: keeps every message in `sent`."""

    def __init__(self) -> None:
        self.sent: list[MailMessage] = []

    def send_many(self, messages: Sequence[MailMessage]) -> list[MailResult]:
        self.sent.extend(messages)
        return [MailResult(ok=True) for _ in messages]


def build_mailer(settings: Settings | None = None) -> Mailer:
    return SmtpMailer(settings)
