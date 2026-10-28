"""Issuer and holder keys: created once, encrypted at rest, published as a JWKS."""

from __future__ import annotations

import asyncio
import json

from jwcrypto.jwk import JWK
from sqlalchemy import func, select, update

from app.credentials import keys
from app.db.session import session_factory
from app.models.credential import HolderKey, SigningKey
from tests.credentials.conftest import ravi_enrolment


async def test_the_issuer_key_is_made_once_and_kept_encrypted(empty, session):
    first = await keys.active_issuer_key(session)
    again = await keys.active_issuer_key(session)
    assert first.kid == again.kid == keys.thumbprint(first.jwk)
    assert first.jwk.has_private
    await session.commit()

    row = (await session.execute(select(SigningKey))).scalar_one()
    private = first.jwk.export_private(as_dict=True)
    assert row.alg == "ES256" and row.purpose == "ISSUER" and row.active is True
    assert private["d"] not in row.private_jwk_encrypted
    assert set(row.public_jwk) == {"kty", "crv", "x", "y", "kid", "use", "alg"}
    assert row.public_jwk["use"] == "sig" and row.public_jwk["alg"] == "ES256"


async def test_a_racing_first_use_still_leaves_one_key(empty):
    factory = session_factory()
    async with factory() as a, factory() as b:
        winner = await keys.active_issuer_key(a)
        rival = asyncio.create_task(keys.active_issuer_key(b))
        await asyncio.sleep(0.2)
        assert not rival.done()  # waiting on the unique index until a commits
        await a.commit()
        assert (await rival).kid == winner.kid
        await b.commit()
    async with factory() as s:
        assert (await s.execute(select(func.count()).select_from(SigningKey))).scalar_one() == 1


async def test_the_jwks_keeps_retired_keys_and_answers_by_kid(empty, session):
    old = await keys.active_issuer_key(session)
    await session.execute(update(SigningKey).values(active=False))
    new = await keys.active_issuer_key(session)
    assert new.kid != old.kid

    document = await keys.jwks(session)
    assert [k["kid"] for k in document["keys"]] == [new.kid, old.kid]
    assert all("d" not in k for k in document["keys"])
    # what a third party does with the document it fetched
    fetched = json.loads(json.dumps(document))
    for issuer_key in (old, new):
        public = await keys.public_key(session, issuer_key.kid)
        assert public.thumbprint() == issuer_key.kid
        assert keys.key_in(fetched, issuer_key.kid).export_public() == public.export_public()
    assert await keys.public_key(session, "no-such-kid") is None
    await session.rollback()


async def test_holder_keys_are_made_on_request(world, session):
    student_id = (await ravi_enrolment(session)).student_id
    assert await keys.holder_key(session, student_id, create=False) is None
    made = await keys.holder_key(session, student_id, create=True)
    assert isinstance(made, JWK) and made.has_private
    again = await keys.holder_key(session, student_id, create=True)
    assert again.thumbprint() == made.thumbprint()
    row = await session.get(HolderKey, student_id)
    assert row.public_jwk == made.export_public(as_dict=True)
    assert made.export_private(as_dict=True)["d"] not in row.private_jwk_encrypted
    await session.rollback()
