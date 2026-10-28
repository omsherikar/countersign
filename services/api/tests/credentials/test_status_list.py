"""The token status list: bit order, signed token, cache and index allocation."""

from __future__ import annotations

import json

from jwcrypto.jws import JWS
from sqlalchemy import update

from app.credentials import keys, status_list
from app.models.credential import Credential
from tests.credentials.conftest import ravi_enrolment


def test_bits_are_least_significant_first():
    bits = status_list.decode(status_list.encode([48213, 0, 131_071]))
    assert len(bits) == 16_384
    assert bits[6026] == 1 << 5
    assert status_list.bit(bits, 48213) == 1
    assert status_list.bit(bits, 48212) == status_list.bit(bits, 48214) == 0
    assert bits[0] == 0b0000_0001 and bits[16_383] == 0b1000_0000
    assert sum(bin(b).count("1") for b in bits) == 3


def test_an_index_outside_the_list_is_refused():
    for index in (-1, 131_072):
        try:
            status_list.encode([index])
        except ValueError:
            continue
        raise AssertionError(f"{index} was accepted")


def _credential(enrolment, index: int, short_id: str, **extra) -> Credential:
    return Credential(
        student_id=enrolment.student_id,
        enrolment_id=enrolment.id,
        kind="ENROLMENT",
        sd_jwt="eyJ.eyJ.sig~",
        status_list_index=index,
        issuer_key_id="test-kid",
        vct="countersign:enrolment:v1",
        short_id=short_id,
        **extra,
    )


async def test_the_token_is_signed_by_a_key_in_the_jwks(world, session):
    enrolment = await ravi_enrolment(session)
    session.add(_credential(enrolment, 48213, "TESTAAAA", revoked=True))
    await session.flush()

    token = await status_list.current(session)
    header = json.loads(status_list.b64url_decode(token.jwt.split(".")[0]))
    assert header["typ"] == "statuslist+jwt" and header["alg"] == "ES256"
    jws = JWS()
    jws.deserialize(token.jwt)
    jws.verify(keys.key_in(await keys.jwks(session), header["kid"]))
    payload = json.loads(jws.payload)
    assert payload["iss"] == "http://localhost:8000"
    assert payload["sub"] == "http://localhost:8000/status-lists/1"
    assert payload["exp"] - payload["iat"] == 86_400 and payload["ttl"] == 60
    assert payload["status_list"]["bits"] == 1
    bits = status_list.decode(payload["status_list"]["lst"])
    assert bits == token.bits
    assert status_list.bit(bits, 48213) == 1
    assert int(token.iat.timestamp()) == payload["iat"]
    await session.rollback()


async def test_the_token_is_cached_until_invalidated(world, session):
    enrolment = await ravi_enrolment(session)
    credential = _credential(enrolment, 7, "TESTAAAB")
    session.add(credential)
    await session.flush()
    first = await status_list.current(session)
    assert status_list.bit(first.bits, 7) == 0

    await session.execute(update(Credential).values(revoked=True))
    assert await status_list.current(session) is first
    status_list.invalidate()
    assert status_list.bit((await status_list.current(session)).bits, 7) == 1
    await session.rollback()


async def test_allocation_skips_taken_indexes(world, session, monkeypatch):
    enrolment = await ravi_enrolment(session)
    session.add(_credential(enrolment, 41, "TESTAAAC"))
    await session.flush()
    draws = iter([41, 41, 99])
    monkeypatch.setattr(status_list.secrets, "randbelow", lambda n: next(draws))
    assert await status_list.allocate_index(session) == 99
    await session.rollback()
