"""Outgoing email for student notices and document requests (D23).

Only hosts in SMTP_ALLOWED_HOSTS are ever contacted (Mailpit in the demo); ALLOW_REAL_SMTP
is never set. Messages go out over one SMTP connection per MAIL_BATCH. Every failure is
reported per message as one PII-free sentence (API_CONTRACT §A3.2), never raised.
"""

from __future__ import annotations

import smtplib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings, get_settings

MAIL_BATCH = 500

NOT_ALLOWED = "Mail server not allowed."
REFUSED = "Email address was refused."
NO_ANSWER = "Mail server did not respond."


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
    """Stdlib smtplib, synchronous; async callers use asyncio.to_thread.

    Built for a host that is not allowed it raises SmtpRefused; the host is checked again
    on every call, so nothing is ever sent to it.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not smtp_host_allowed(self.settings.smtp_host, self.settings):
            raise SmtpRefused(f"SMTP host {self.settings.smtp_host!r} is not allowed")

    def send_many(self, messages: Sequence[MailMessage]) -> list[MailResult]:
        if not smtp_host_allowed(self.settings.smtp_host, self.settings):
            return [MailResult(ok=False, error=NOT_ALLOWED)] * len(messages)
        results: list[MailResult] = []
        for start in range(0, len(messages), MAIL_BATCH):
            results.extend(self._send_batch(messages[start : start + MAIL_BATCH]))
        return results

    def ping(self) -> str | None:
        """None when the server answers; otherwise the sentence a send would record."""
        if not smtp_host_allowed(self.settings.smtp_host, self.settings):
            return NOT_ALLOWED
        try:
            smtp = self._connect()
        except (smtplib.SMTPException, OSError):
            return NO_ANSWER
        _close(smtp)
        return None

    def _connect(self) -> smtplib.SMTP:
        return smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10)

    def _send_batch(self, batch: Sequence[MailMessage]) -> list[MailResult]:
        """One connection for the batch; a dropped or failing connection fails the rest of
        the batch as worth another try."""
        try:
            smtp = self._connect()
        except (smtplib.SMTPException, OSError):
            return [MailResult(ok=False, error=NO_ANSWER, transient=True)] * len(batch)
        results: list[MailResult] = []
        try:
            for message in batch:
                try:
                    smtp.send_message(_email(message, self.settings.notice_from))
                except smtplib.SMTPRecipientsRefused:
                    results.append(MailResult(ok=False, error=REFUSED))
                    continue
                except smtplib.SMTPResponseException as exc:
                    if 500 <= exc.smtp_code < 600:
                        # a permanent answer about this message (smtplib has reset the
                        # session), so the connection carries on
                        results.append(MailResult(ok=False, error=REFUSED))
                        continue
                    break
                except (smtplib.SMTPException, OSError):
                    break
                results.append(MailResult(ok=True))
        finally:
            _close(smtp)
        missing = len(batch) - len(results)
        return results + [MailResult(ok=False, error=NO_ANSWER, transient=True)] * missing


def _close(smtp: smtplib.SMTP) -> None:
    try:
        smtp.quit()
    except (smtplib.SMTPException, OSError):
        smtp.close()


class RefusingMailer:
    """What build_mailer gives for a host that is not allowed: every message fails at once."""

    def send_many(self, messages: Sequence[MailMessage]) -> list[MailResult]:
        return [MailResult(ok=False, error=NOT_ALLOWED)] * len(messages)


class MemoryMailer:
    """For tests: keeps every message in `sent`. `refuse` holds addresses to refuse and
    `down` makes every message fail as if the server did not answer."""

    def __init__(self, *, refuse: set[str] | None = None, down: bool = False) -> None:
        self.sent: list[MailMessage] = []
        self.calls = 0
        self.refuse = refuse or set()
        self.down = down

    def send_many(self, messages: Sequence[MailMessage]) -> list[MailResult]:
        self.calls += 1
        results: list[MailResult] = []
        for message in messages:
            if self.down:
                results.append(MailResult(ok=False, error=NO_ANSWER, transient=True))
            elif message.to in self.refuse:
                results.append(MailResult(ok=False, error=REFUSED))
            else:
                self.sent.append(message)
                results.append(MailResult(ok=True))
        return results


def build_mailer(settings: Settings | None = None) -> Mailer:
    """The SMTP mailer; for a host outside SMTP_ALLOWED_HOSTS one that refuses every message."""
    try:
        return SmtpMailer(settings)
    except SmtpRefused:
        return RefusingMailer()
