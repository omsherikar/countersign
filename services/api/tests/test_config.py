import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.rules import Notices, get_rules
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
