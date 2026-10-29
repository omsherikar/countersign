"""The partner's set: the same every time, a share of the registry plus extras."""

from __future__ import annotations

from pathlib import Path

from app.registry import apaar_hmac, partner_apaars, read_registry
from tests.conftest import KEY


def test_apaar_hmac_matches_the_api_digest():
    # services/api app.core.crypto.hmac_id("1234 5678 4417", "apaar") under the all-zero key
    expected = "9abb1acc7dd80bf0b86c740b976fafb84ee9301059343d1c5b887317667f6187"
    assert apaar_hmac(KEY, "1234 5678 4417") == apaar_hmac(KEY, "123456784417")
    assert len(apaar_hmac(KEY, "123456784417")) == 64
    assert apaar_hmac(KEY, "123456784417") == expected


def test_a_key_that_is_not_hex_is_used_as_text():
    assert apaar_hmac("not-hex", "123456784417") != apaar_hmac(KEY, "123456784417")


def test_the_partner_set_is_a_seeded_share_of_the_registry_plus_extras(registry: Path):
    apaars = read_registry(registry)
    first = partner_apaars(apaars, "seed", 0.25, 50)
    assert first == partner_apaars(apaars, "seed", 0.25, 50)
    from_registry = [a for a in first if a in set(apaars)]
    extras = [a for a in first if a not in set(apaars)]
    assert len(extras) == 50
    assert 20 <= len(from_registry) <= 80  # about a quarter of 200
    assert all(len(a) == 12 and a.isdigit() for a in first)
    assert len(set(first)) == len(first)
    assert partner_apaars(apaars, "other seed", 0.25, 50) != first


def test_share_zero_and_one(registry: Path):
    apaars = read_registry(registry)
    assert partner_apaars(apaars, "seed", 0.0, 0) == []
    assert sorted(partner_apaars(apaars, "seed", 1.0, 0)) == sorted(apaars)
