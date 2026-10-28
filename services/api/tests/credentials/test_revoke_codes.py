"""revoke_for_enrolment stores a reason code and refreshes the status list."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import credentials
from app.credentials import status_list
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.credential import Credential
from tests.credentials.conftest import ravi_enrolment


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        ("Enrolment withdrawn", "ENROLMENT_WITHDRAWN"),
        ("Enrolment transferred", "ENROLMENT_TRANSFERRED"),
        ("ENROLMENT_WITHDRAWN", "ENROLMENT_WITHDRAWN"),
        ("ENROLMENT_TRANSFERRED", "ENROLMENT_TRANSFERRED"),
        ("FLAG_CONFIRMED", "FLAG_CONFIRMED"),
    ],
)
def test_ledger_words_become_codes(given, stored):
    assert credentials.system_reason_code(given) == stored


@pytest.mark.parametrize("given", ["ADMIN", "withdrawn", "", "Revoked by AICTE"])
def test_anything_else_is_refused(given):
    with pytest.raises(ValueError):
        credentials.system_reason_code(given)


async def test_a_revocation_reaches_the_status_list_once_committed(world):
    factory = session_factory()
    async with factory() as session:
        enrolment = await ravi_enrolment(session)
        session.add(
            Credential(
                student_id=enrolment.student_id,
                enrolment_id=enrolment.id,
                kind="ENROLMENT",
                sd_jwt="eyJ.eyJ.sig~",
                status_list_index=48213,
                issuer_key_id="test-kid",
                vct="countersign:enrolment:v1",
                short_id="TESTAAAA",
            )
        )
        await status_list.current(session)  # creates the issuer key
        await session.commit()

        with pytest.raises(ValueError):
            await credentials.revoke_for_enrolment(session, enrolment.id, "because", None)
        revoked = await credentials.revoke_for_enrolment(
            session, enrolment.id, "Enrolment withdrawn", None
        )
        assert revoked == 1
        # another request rebuilds the token before this transaction commits...
        async with factory() as other:
            stale = await status_list.current(other)
        assert status_list.bit(stale.bits, 48213) == 0
        assert await status_list.current(session) is stale
        # ...and the commit drops it
        await session.commit()
        assert status_list.bit((await status_list.current(session)).bits, 48213) == 1

        credential = (await session.execute(select(Credential))).scalar_one()
        assert credential.revoked_reason == "ENROLMENT_WITHDRAWN"
        entry = (
            await session.execute(select(AuditLog).where(AuditLog.entity_type == "credential"))
        ).scalar_one()
        assert entry.actor_id is None
        assert entry.after["revoked_reason"] == entry.after["reason_code"] == "ENROLMENT_WITHDRAWN"
