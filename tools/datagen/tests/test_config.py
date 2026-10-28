import os

import pytest

from datagen import config


def test_small_and_full_sizes_load():
    small = config.Config.build("small")
    full = config.Config.build("full")
    assert small.size.institutions == 50
    assert full.size.institutions == 500
    assert small.academic_year == "2026-27"
    assert small.anomalies["EXCESS_ADMISSION"] >= 1
    assert full.anomalies["EXCESS_ADMISSION"] > small.anomalies["EXCESS_ADMISSION"]


def test_unknown_size_rejected():
    with pytest.raises(ValueError):
        config.Config.build("huge")


def test_rules_carry_seat_pool_shares():
    rules = config.Config.build("small").rules
    assert rules["seat_pools"]["NRI"]["share"] == 0.05
    assert rules["seat_pools"]["LATERAL"]["share"] == 0.10
    assert rules["apaar"]["format"] == "^[0-9]{12}$"


def test_rules_path_prefers_env(tmp_path, monkeypatch):
    custom = tmp_path / "rules.yaml"
    custom.write_text("seat_pools: {}\n", encoding="utf-8")
    monkeypatch.setenv("RULES_PATH", str(custom))
    assert config.rules_path() == custom
    monkeypatch.delenv("RULES_PATH")
    assert config.rules_path().is_file()
    assert "RULES_PATH" not in os.environ


def test_update_files_per_size():
    small = config.Config.build("small").updates
    full = config.Config.build("full").updates
    assert (small.colleges, full.colleges) == (3, 20)
    assert small.withdrawals == (2, 4) and small.transfers == (1, 2) and small.refills == (1, 2)
    assert small.status_dates == ("2026-09-16", "2026-10-20")
