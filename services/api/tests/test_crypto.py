import hashlib
import hmac

import pytest

from app.core import crypto


def test_hmac_matches_known_vector():
    # PII_HMAC_KEY in tests is 32 zero bytes; compare against a direct computation.
    expected = hmac.new(b"\x00" * 32, b"123456784417", hashlib.sha256).hexdigest()
    assert crypto.hmac_id("123456784417", "apaar") == expected
    assert crypto.hmac_bytes("123456784417", "apaar") == bytes.fromhex(expected)


def test_hmac_normalises_before_hashing():
    assert crypto.hmac_id(" 1234 5678 4417 ", "apaar") == crypto.hmac_id("123456784417", "apaar")
    assert crypto.hmac_id("+91 98765-04521", "mobile") == crypto.hmac_id("919876504521", "mobile")
    assert crypto.hmac_id("12  Shivaji   Nagar, PUNE", "address") == crypto.hmac_id(
        "12 shivaji nagar, pune", "address"
    )
    assert crypto.hmac_id("abc", "generic") != crypto.hmac_id("abd", "generic")


def test_fernet_roundtrip_and_tamper():
    token = crypto.encrypt("123456784417")
    assert token != b"123456784417"
    assert crypto.decrypt(token) == "123456784417"
    with pytest.raises(ValueError):
        crypto.decrypt(token[:-2] + b"xx")


def test_masks():
    assert crypto.mask_apaar("123456784417") == "XXXX XXXX 4417"
    assert crypto.mask_apaar("4417") == "XXXX XXXX 4417"
    assert crypto.mask_apaar(None) is None
    assert crypto.mask_apaar("") is None
    assert crypto.mask_mobile("9876504521") == "XXXXXX4521"
    assert crypto.mask_mobile("4521") == "XXXXXX4521"
    assert crypto.mask_mobile(None) is None
    assert crypto.mask_passport("N1234567") == "X1234567"


def test_last4_and_name_normalisation():
    assert crypto.last4("123456784417") == "4417"
    assert crypto.last4("12") == "12"
    assert crypto.normalise_name("  R. K.  Sharma ") == "r k sharma"
    assert crypto.normalise_name("Mohd. Irfan-Shaikh") == "mohd irfan shaikh"
