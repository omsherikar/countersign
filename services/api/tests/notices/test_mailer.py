"""The mailer: the SMTP allow list, one connection per 500 messages, plain failure sentences."""

from __future__ import annotations

import smtplib
import socket

import pytest

from app.core.config import get_settings
from app.notices import mailer as mail
from app.notices.mailer import (
    MAIL_BATCH,
    MailMessage,
    RefusingMailer,
    SmtpMailer,
    SmtpRefused,
    build_mailer,
)


class FakeSmtp:
    """Stands in for smtplib.SMTP: counts connections and records what was sent."""

    connections: list[FakeSmtp] = []
    refuse: set[str] = set()
    drop_after: int | None = None
    temporary_for: set[str] = set()

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port = host, port
        self.sent: list[str] = []
        self.closed = False
        FakeSmtp.connections.append(self)

    def send_message(self, message) -> None:
        to = message["To"]
        if FakeSmtp.drop_after is not None and len(self.sent) >= FakeSmtp.drop_after:
            raise smtplib.SMTPServerDisconnected("gone")
        if to in FakeSmtp.refuse:
            raise smtplib.SMTPRecipientsRefused({to: (550, b"no such user")})
        if to in FakeSmtp.temporary_for:
            raise smtplib.SMTPDataError(451, b"try later")
        self.sent.append(to)

    def quit(self) -> None:
        self.closed = True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_smtp(monkeypatch) -> type[FakeSmtp]:
    FakeSmtp.connections = []
    FakeSmtp.refuse = set()
    FakeSmtp.drop_after = None
    FakeSmtp.temporary_for = set()
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSmtp)
    return FakeSmtp


def messages(n: int) -> list[MailMessage]:
    return [MailMessage(to=f"s{i}@example.demo", subject="s", body="b") for i in range(n)]


def allowed_settings():
    return get_settings().model_copy(update={"smtp_host": "localhost", "smtp_port": 1025})


def test_a_host_outside_the_allow_list_is_refused_without_a_connection(fake_smtp):
    outside = get_settings().model_copy(update={"smtp_host": "smtp.gmail.com"})
    with pytest.raises(SmtpRefused):
        SmtpMailer(outside)
    refusing = build_mailer(outside)
    assert isinstance(refusing, RefusingMailer)
    results = refusing.send_many(messages(3))
    assert [(r.ok, r.error, r.transient) for r in results] == [
        (False, "Mail server not allowed.", False)
    ] * 3
    # a mailer whose settings changed after it was built checks again on every call
    smtp = SmtpMailer(allowed_settings())
    smtp.settings = outside
    assert smtp.send_many(messages(2))[0].error == "Mail server not allowed."
    assert fake_smtp.connections == []
    # ALLOW_REAL_SMTP is the only way past the list, and the project never sets it
    real = outside.model_copy(update={"allow_real_smtp": True})
    assert mail.smtp_host_allowed("smtp.gmail.com", real)


def test_one_connection_per_500_messages(fake_smtp):
    results = SmtpMailer(allowed_settings()).send_many(messages(2 * MAIL_BATCH + 1))
    assert all(r.ok for r in results) and len(results) == 1001
    assert [len(c.sent) for c in fake_smtp.connections] == [500, 500, 1]
    assert all(c.closed and (c.host, c.port) == ("localhost", 1025) for c in fake_smtp.connections)


def test_failures_are_plain_sentences_and_only_outages_are_retried(fake_smtp):
    fake_smtp.refuse = {"s1@example.demo"}
    results = SmtpMailer(allowed_settings()).send_many(messages(3))
    assert [(r.ok, r.error, r.transient) for r in results] == [
        (True, None, False),
        (False, "Email address was refused.", False),
        (True, None, False),
    ]
    # a temporary answer ends the connection: the rest of it is worth another try
    fake_smtp.connections = []
    fake_smtp.refuse = set()
    fake_smtp.temporary_for = {"s1@example.demo"}
    results = SmtpMailer(allowed_settings()).send_many(messages(3))
    assert [(r.ok, r.transient) for r in results] == [(True, False), (False, True), (False, True)]
    assert results[1].error == "Mail server did not respond."
    # a dropped connection fails what it had not sent yet
    fake_smtp.temporary_for = set()
    fake_smtp.drop_after = 1
    results = SmtpMailer(allowed_settings()).send_many(messages(3))
    assert [r.ok for r in results] == [True, False, False]


def test_a_server_that_does_not_answer_fails_every_message_as_transient(monkeypatch):
    def unreachable(*args, **kwargs):
        raise socket.gaierror(8, "nodename nor servname provided")

    monkeypatch.setattr(mail.smtplib, "SMTP", unreachable)
    results = SmtpMailer(allowed_settings()).send_many(messages(2))
    assert [(r.ok, r.error, r.transient) for r in results] == [
        (False, "Mail server did not respond.", True)
    ] * 2


def test_the_message_carries_the_sender_and_headers(fake_smtp, monkeypatch):
    seen = []
    monkeypatch.setattr(FakeSmtp, "send_message", lambda self, m: seen.append(m))
    SmtpMailer(allowed_settings()).send_many(
        [MailMessage(to="a@example.demo", subject="Hi", body="Body", headers={"X-Test": "1"})]
    )
    [email] = seen
    assert email["From"] == get_settings().notice_from
    assert (email["To"], email["Subject"], email["X-Test"]) == ("a@example.demo", "Hi", "1")
    assert email.get_content().strip() == "Body"


def test_ping_says_whether_the_server_answers(fake_smtp, monkeypatch):
    assert SmtpMailer(allowed_settings()).ping() is None
    assert fake_smtp.connections[0].closed

    def unreachable(*args, **kwargs):
        raise ConnectionRefusedError(61, "refused")

    monkeypatch.setattr(mail.smtplib, "SMTP", unreachable)
    assert SmtpMailer(allowed_settings()).ping() == "Mail server did not respond."
