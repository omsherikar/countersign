"""Verify a Countersign proof with nothing but its published documents.

    python -m app.credentials.verify_cli <presentation> --jwks-url URL --status-url URL

This is what any employer or admissions office can do without an account and without
asking Countersign about the student: fetch the issuer's JWKS and the status list over
HTTP, check the issuer signature, the holder's key binding against the key in the proof,
that every disclosure was signed, the expiry and the revocation bit. It deliberately uses
no Countersign code, only the public SD-JWT and JOSE libraries, and prints the result as
JSON. Exit status 0 means VALID.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import sys
import time
import zlib
from typing import Any

import httpx
from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS
from sd_jwt.verifier import SDJWTVerifier

SHARE_SECONDS = 600  # a key binding older than a share's 10 minutes has expired
KINDS = {"countersign:enrolment:v1": "ENROLMENT", "countersign:degree:v1": "DEGREE"}


class NotValid(Exception):
    pass


def _b64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _json(text: str) -> Any:
    return json.loads(_b64(text))


def _key(jwks: dict[str, Any], kid: Any) -> JWK:
    for entry in jwks.get("keys", []):
        if isinstance(entry, dict) and entry.get("kid") == kid:
            return JWK(**entry)
    raise NotValid(f"no key {kid!r} in the issuer's JWKS")


def check_presentation(
    presentation: str, jwks: dict[str, Any], issuer: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """(verified claims, signed payload, key-binding claims) or NotValid."""

    def issuer_key(iss: str, header: dict[str, Any]) -> JWK:
        if iss != issuer:
            raise NotValid(f"issued by {iss!r}, not {issuer!r}")
        return _key(jwks, header.get("kid"))

    parts = presentation.strip().split("~")
    if len(parts) < 2:
        raise NotValid("not an SD-JWT presentation")
    try:
        signed = _json(parts[0].split(".")[1])
        binding = _json(parts[-1].split(".")[1]) if parts[-1] else None
        if ("cnf" in signed) != (binding is not None):
            raise NotValid("the holder's key binding is missing or unexpected")
        verifier = SDJWTVerifier(
            presentation.strip(),
            issuer_key,
            expected_aud=binding.get("aud") if binding else None,
            expected_nonce=binding.get("nonce") if binding else None,
        )
        claims = verifier.get_verified_payload()
    except NotValid:
        raise
    except Exception as exc:
        raise NotValid(f"signature or key binding does not verify ({exc})") from None
    signed_digests = set(signed.get("_sd", []))
    for disclosure in parts[1:-1]:
        digest = base64.urlsafe_b64encode(hashlib.sha256(disclosure.encode()).digest())
        if digest.decode().rstrip("=") not in signed_digests:
            raise NotValid("a disclosure was changed after signing")
    return claims, signed, binding


def status_bit(token: str, jwks: dict[str, Any], uri: str, index: int) -> int:
    """The bit for `index` in a status-list token signed by a key in the same JWKS."""
    header = _json(token.split(".")[0])
    if header.get("typ") != "statuslist+jwt":
        raise NotValid("the status list is not a statuslist+jwt")
    jws = JWS()
    jws.deserialize(token)
    jws.verify(_key(jwks, header.get("kid")))
    payload = json.loads(jws.payload)
    if payload.get("sub") != uri:
        raise NotValid(f"the status list is {payload.get('sub')!r}, the proof names {uri!r}")
    bits = zlib.decompress(_b64(payload["status_list"]["lst"]))
    return (bits[index // 8] >> (index % 8)) & 1


async def verify(
    presentation: str,
    *,
    jwks_url: str,
    status_url: str,
    client: httpx.AsyncClient,
    issuer: str | None = None,
) -> dict[str, Any]:
    """The result of checking one pasted presentation against the published documents."""
    issuer = issuer or jwks_url.removesuffix("/.well-known/jwks.json")
    jwks = (await client.get(jwks_url)).raise_for_status().json()
    try:
        claims, signed, binding = check_presentation(presentation, jwks, issuer)
    except NotValid as exc:
        return {"result": "INVALID", "reason": str(exc), "disclosed": {}}
    status = signed["status"]["status_list"]
    token = (await client.get(status_url)).raise_for_status().text
    try:
        revoked = status_bit(token, jwks, status["uri"], int(status["idx"]))
    except NotValid as exc:
        return {"result": "INVALID", "reason": str(exc), "disclosed": {}}
    now = time.time()
    expired = (signed.get("exp") is not None and signed["exp"] <= now) or (
        binding is not None and now - binding.get("iat", 0) > SHARE_SECONDS
    )
    result = "REVOKED" if revoked else "EXPIRED" if expired else "VALID"
    visible = {"iss", "iat", "exp", "vct", "status", "cnf"}
    return {
        "result": result,
        "issuer": signed.get("iss"),
        "kind": KINDS.get(signed.get("vct")),
        "issued_at": signed.get("iat"),
        "holder_bound": binding is not None,
        "nonce": binding.get("nonce") if binding else None,
        "audience": binding.get("aud") if binding else None,
        "disclosed": (
            {k: v for k, v in claims.items() if k not in visible} if result == "VALID" else {}
        ),
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        return await verify(
            args.presentation,
            jwks_url=args.jwks_url,
            status_url=args.status_url,
            client=client,
            issuer=args.issuer,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.credentials.verify_cli",
        description="Verify a Countersign proof using only its published keys and status list.",
    )
    parser.add_argument("presentation", help="the SD-JWT presentation, or - to read stdin")
    parser.add_argument("--jwks-url", required=True, help="the issuer's /.well-known/jwks.json")
    parser.add_argument("--status-url", required=True, help="the issuer's /status-lists/1")
    parser.add_argument("--issuer", help="the expected iss (default: the JWKS URL's origin)")
    args = parser.parse_args(argv)
    if args.presentation == "-":
        args.presentation = sys.stdin.read()
    try:
        result = asyncio.run(_run(args))
    except httpx.HTTPError as exc:
        print(f"could not fetch the issuer's documents: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["result"] == "VALID" else 1


if __name__ == "__main__":
    sys.exit(main())
