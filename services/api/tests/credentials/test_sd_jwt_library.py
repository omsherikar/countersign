"""The SD-JWT stack the credentials module builds on, pinned to the installed versions.

sd-jwt 0.10.4 (PyPI `sd-jwt`, import `sd_jwt`) with jwcrypto 1.6.1. What these tests verify:

Keys, `jwcrypto.jwk.JWK`
- `JWK.generate(kty="EC", crv="P-256")` makes an ES256 key with NO kid. Give it one with
  `JWK(**key.export_private(as_dict=True), kid=key.thumbprint())`; `thumbprint()` is the
  RFC 7638 SHA-256 thumbprint, base64url.
- `export_public(as_dict=True)` and `export_private(as_dict=True)` return dicts (with the
  kid once set); `export_private()` without `as_dict` returns a JSON string, the thing to
  Fernet-encrypt. `JWK(**d)` imports a dict back.

Issuing, `sd_jwt.issuer.SDJWTIssuer(user_claims, issuer_key, holder_key=None,
sign_alg=None, add_decoy_claims=False, serialization_format="compact",
extra_header_parameters={})`
- A claim is selectively disclosable when its KEY is wrapped in `sd_jwt.common.SDObj`:
  `{SDObj("name"): "..."}`. Plain keys are always visible. An object under an SDObj key is
  disclosed whole.
- `holder_key` (a JWK) puts `cnf = {"jwk": <holder public JWK>}` in the payload.
- The header is `{"alg": "ES256", "typ": "example+sd-jwt"}` unless overridden; pass
  `extra_header_parameters={"typ": "vc+sd-jwt", "kid": kid}`. `sign_alg` defaults to
  "ES256"; the payload gets `_sd_alg: "sha-256"`.
- Results: `.sd_jwt_issuance` ("<jwt>~<disclosure>~...~", always ends with "~"),
  `.sd_jwt_payload` (the signed dict), `.serialized_sd_jwt` (the issuer JWT alone),
  `.ii_disclosures` (SDJWTDisclosure: `.key`, `.value`, `.b64`, `.hash`, `.json`).

Presenting, `sd_jwt.holder.SDJWTHolder(sd_jwt_issuance, serialization_format="compact")`
then `.create_presentation(claims_to_disclose, nonce=None, aud=None, holder_key=None,
sign_alg=None)`
- `claims_to_disclose` is a dict `{claim_name: True}`; every other SD claim stays hidden.
- The key binding JWT (header typ "kb+jwt"; payload nonce, aud, iat, sd_hash) is added only
  when nonce, aud AND holder_key are all given.
- Result: `.sd_jwt_presentation` ("<jwt>~<chosen disclosures>~<kb-jwt>"), plus
  `.key_binding_jwt_payload`. The holder never checks the issuer signature.

Verifying, `sd_jwt.verifier.SDJWTVerifier(sd_jwt_presentation, cb_get_issuer_key,
expected_aud=None, expected_nonce=None, serialization_format="compact")`
- Verification runs in the constructor, which raises on failure:
  `jwcrypto.jws.InvalidJWSSignature` for a bad issuer or holder signature; `ValueError`
  "Invalid nonce in KB-JWT", "Invalid audience in KB-JWT" or "Invalid digest in KB-JWT"
  (a disclosure added or removed after signing); `jwcrypto.jws.InvalidJWSObject` when a
  key binding JWT is expected but missing.
- `cb_get_issuer_key(iss, header)` receives the unverified `iss` claim and the protected
  header dict (`alg`, `typ`, `kid`) and must return a public jwcrypto JWK: look the kid up
  in the same JWKS document a third party fetches.
- `expected_aud` and `expected_nonce` go together. Only then is the key binding JWT
  checked (signature against `cnf.jwk`, typ, aud, nonce, sd_hash); with neither it is
  ignored entirely. To check the holder binding without enforcing a nonce, read the KB-JWT
  nonce and aud unverified and pass them back as the expected values.
- `.get_verified_payload()` returns the visible claims plus the disclosed ones (`_sd` and
  `_sd_alg` removed, `cnf` kept). exp, nbf and iat are NOT checked: check exp yourself.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import pytest
from jwcrypto.jwk import JWK
from jwcrypto.jws import InvalidJWSObject, InvalidJWSSignature
from sd_jwt.common import SDObj
from sd_jwt.holder import SDJWTHolder
from sd_jwt.issuer import SDJWTIssuer
from sd_jwt.verifier import SDJWTVerifier

ISSUER_URL = "http://localhost:8000"
AUD = f"{ISSUER_URL}/verify"
NONCE = "7K3M-Q9TX-2HDP-8VNC-4WRA-6JYB"


def es256_key() -> JWK:
    key = JWK.generate(kty="EC", crv="P-256")
    assert key.get("kid") is None
    return JWK(**key.export_private(as_dict=True), kid=key.thumbprint())


@pytest.fixture(scope="module")
def keys() -> dict[str, JWK]:
    return {"issuer": es256_key(), "holder": es256_key()}


@pytest.fixture(scope="module")
def jwks(keys) -> dict[str, Any]:
    """What GET /.well-known/jwks.json would serve."""
    public = keys["issuer"].export_public(as_dict=True)
    return {"keys": [{**public, "alg": "ES256", "use": "sig"}]}


def key_from(jwks: dict[str, Any], seen: list[tuple[str, dict[str, Any]]] | None = None):
    def callback(iss: str, header: dict[str, Any]) -> JWK:
        if seen is not None:
            seen.append((iss, header))
        match = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
        return JWK(**match)

    return callback


def issue(keys, **overrides: Any) -> SDJWTIssuer:
    claims: dict[Any, Any] = {
        "iss": ISSUER_URL,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "vct": "countersign:enrolment:v1",
        "status": {"status_list": {"idx": 41, "uri": f"{ISSUER_URL}/status-lists/1"}},
        SDObj("name"): "Asha Verma",
        SDObj("dob"): "2007-03-21",
        SDObj("institution"): {"name": "ABC College of Engineering", "aicte_id": "1-ABC-0001"},
        SDObj("countersigned"): [{"check": "IDENTITY", "on": "2026-10-28"}],
        **overrides,
    }
    return SDJWTIssuer(
        claims,
        keys["issuer"],
        holder_key=keys["holder"],
        extra_header_parameters={"typ": "vc+sd-jwt", "kid": keys["issuer"]["kid"]},
    )


def present(keys, issuance: str, fields: dict[str, bool], nonce: str | None = NONCE) -> str:
    holder = SDJWTHolder(issuance)
    holder.create_presentation(fields, nonce=nonce, aud=AUD, holder_key=keys["holder"])
    return holder.sd_jwt_presentation


def unverified_kb_payload(presentation: str) -> dict[str, Any]:
    body = presentation.split("~")[-1].split(".")[1]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


def test_issue_present_verify_with_key_binding(keys, jwks):
    issuer = issue(keys)
    assert issuer.sd_jwt_issuance.endswith("~")
    assert {d.key for d in issuer.ii_disclosures} == {"name", "dob", "institution", "countersigned"}
    assert issuer.sd_jwt_payload["cnf"] == {"jwk": keys["holder"].export_public(as_dict=True)}

    presentation = present(keys, issuer.sd_jwt_issuance, {"name": True, "institution": True})
    assert presentation.count("~") == 3  # jwt, two disclosures, key binding JWT

    seen: list[tuple[str, dict[str, Any]]] = []
    verifier = SDJWTVerifier(
        presentation, key_from(jwks, seen), expected_aud=AUD, expected_nonce=NONCE
    )
    header = {"alg": "ES256", "typ": "vc+sd-jwt", "kid": keys["issuer"]["kid"]}
    assert seen == [(ISSUER_URL, header)]
    payload = verifier.get_verified_payload()
    assert payload["name"] == "Asha Verma"
    assert payload["institution"]["aicte_id"] == "1-ABC-0001"
    assert "dob" not in payload and "countersigned" not in payload
    assert payload["vct"] == "countersign:enrolment:v1"
    assert payload["status"]["status_list"]["idx"] == 41
    assert payload["cnf"]["jwk"] == keys["holder"].export_public(as_dict=True)
    assert "_sd" not in payload and "_sd_alg" not in payload


def test_the_verifier_rejects_tampering(keys, jwks):
    issuance = issue(keys).sd_jwt_issuance
    presentation = present(keys, issuance, {"name": True, "dob": True})
    with pytest.raises(ValueError, match="Invalid nonce"):
        SDJWTVerifier(presentation, key_from(jwks), expected_aud=AUD, expected_nonce="OTHER")
    with pytest.raises(ValueError, match="Invalid audience"):
        SDJWTVerifier(presentation, key_from(jwks), expected_aud="http://x", expected_nonce=NONCE)

    stranger = es256_key()
    with pytest.raises(InvalidJWSSignature):
        SDJWTVerifier(
            presentation, lambda iss, header: stranger, expected_aud=AUD, expected_nonce=NONCE
        )

    jwt, _dropped, *rest = presentation.split("~")
    shortened = "~".join([jwt, *rest])
    with pytest.raises(ValueError, match="Invalid digest"):
        SDJWTVerifier(shortened, key_from(jwks), expected_aud=AUD, expected_nonce=NONCE)

    without_binding = present(keys, issuance, {"name": True}, nonce=None)
    assert without_binding.endswith("~")
    with pytest.raises(InvalidJWSObject):
        SDJWTVerifier(without_binding, key_from(jwks), expected_aud=AUD, expected_nonce=NONCE)


def test_key_binding_is_only_checked_when_aud_and_nonce_are_expected(keys, jwks):
    presentation = present(keys, issue(keys).sd_jwt_issuance, {"name": True})
    forged = presentation.rsplit("~", 1)[0] + "~" + "e30.e30.c2ln"
    # ignored without expected values
    SDJWTVerifier(forged, key_from(jwks))
    # reading the nonce and aud first still checks the holder signature
    claimed = unverified_kb_payload(presentation)
    assert (claimed["nonce"], claimed["aud"]) == (NONCE, AUD)
    SDJWTVerifier(
        presentation, key_from(jwks), expected_aud=claimed["aud"], expected_nonce=claimed["nonce"]
    )


def test_expiry_is_left_to_the_caller(keys, jwks):
    expired = issue(keys, exp=int(time.time()) - 60)
    presentation = present(keys, expired.sd_jwt_issuance, {"name": True})
    payload = SDJWTVerifier(
        presentation, key_from(jwks), expected_aud=AUD, expected_nonce=NONCE
    ).get_verified_payload()
    assert payload["exp"] < time.time()
