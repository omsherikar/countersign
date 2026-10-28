from datetime import date

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.rules import Notices, Reporting, get_rules
from tests.conftest import REPO_ROOT

LOOP_KEYS = (
    "WEB_ORIGIN",
    "ISSUER_URL",
    "SMTP_ALLOWED_HOSTS",
    "ALLOW_REAL_SMTP",
    "CASE_FILES_DIR",
    "DEMO_MODE",
    "NOTICE_FROM",
)


def test_loop_settings_default_to_the_local_demo(monkeypatch):
    for key in LOOP_KEYS:
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.web_origin == "http://localhost:3000"
    assert settings.issuer_url == "http://localhost:8000"
    assert settings.smtp_allowed_hosts == ["mailpit", "localhost", "127.0.0.1"]
    assert settings.allow_real_smtp is False
    assert settings.case_files_dir == "/data/case-files"
    assert settings.demo_mode is False
    assert settings.notice_from == "Countersign <notices@countersign.invalid>"


def test_smtp_allowed_hosts_is_a_comma_separated_list(monkeypatch):
    monkeypatch.setenv("SMTP_ALLOWED_HOSTS", " mailpit , smtp.test ,")
    assert Settings().smtp_allowed_hosts == ["mailpit", "smtp.test"]


def test_every_setting_has_a_line_in_the_env_example():
    lines = (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    documented = {line.split("=", 1)[0] for line in lines if "=" in line and line[0] != "#"}
    assert {key.upper() for key in Settings.model_fields} <= documented


def test_notice_rules_load():
    notices = get_rules().notices
    assert (notices.expiry_days, notices.change_window_days, notices.resend_limit) == (30, 7, 3)
    with pytest.raises(ValidationError):
        Notices(expiry_days=0, change_window_days=7, resend_limit=3)


DIGILOCKER_KEYS = (
    "DIGILOCKER_CLIENT_ID",
    "DIGILOCKER_CLIENT_SECRET",
    "DIGILOCKER_AUTHORIZE_URL",
    "DIGILOCKER_ISSUER",
)


def test_digilocker_settings_default_to_the_demo_simulator(monkeypatch):
    for key in DIGILOCKER_KEYS:
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    # the same client and secret mockgov's simulator uses by default
    assert settings.digilocker_client_id == "countersign-demo"
    assert settings.digilocker_client_secret == "countersign-demo-digilocker-client-secret"
    assert settings.digilocker_authorize_url == "http://localhost:8001/digilocker/oauth/authorize"
    assert settings.digilocker_issuer == "http://localhost:8001/digilocker"


def test_reporting_deadlines_load_and_default_to_30_september():
    reporting = get_rules().reporting
    assert reporting.deadline_for("2026-27") == date(2026, 9, 30)
    assert reporting.deadline_for("2025-26") == date(2025, 9, 30)
    # a year rules.yaml does not list
    assert reporting.deadline_for("2027-28") == date(2027, 9, 30)
    assert reporting.source
    assert Reporting.model_validate({"deadlines": {"2026-27": "2026-10-15"}}).deadline_for(
        "2026-27"
    ) == date(2026, 10, 15)
