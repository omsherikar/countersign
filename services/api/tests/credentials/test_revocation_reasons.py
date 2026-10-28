"""Every cause of revocation reaches the wire as its code: the Seat Ledger's withdrawal and
transfer, a confirmed flag and an officer's revocation."""

from __future__ import annotations

from sqlalchemy import select

from app import credentials
from app.credentials import holder, status_list
from app.db.session import session_factory
from app.engine.ledger import assign_seats
from app.models.audit import AuditLog
from app.models.enums import AuditAction, EnrolmentStatus
from app.models.student import Enrolment
from app.models.user import User
from tests.credentials.conftest import active_enrolments
from tests.credentials.helpers import b64json, issue_for, public, signed_in


async def test_revocation_codes_on_the_wire(world):
    async with session_factory()() as session:
        withdrawn, transferred, confirmed, by_admin = await active_enrolments(
            session, "1-ABC-0001", 4
        )
        assert all(e.seat_id is not None for e in (withdrawn, transferred))
    proofs = {}
    for name, enrolment in (
        ("withdrawn", withdrawn),
        ("transferred", transferred),
        ("confirmed", confirmed),
        ("admin", by_admin),
    ):
        proofs[name] = await issue_for(enrolment.id)

    async with session_factory()() as session:
        registrar = (
            await session.execute(select(User).where(User.email == "registrar@abc.edu.demo"))
        ).scalar_one()
        officer = (
            await session.execute(select(User).where(User.email == "ro.west@aicte.demo"))
        ).scalar_one()
        for enrolment, status in (
            (withdrawn, EnrolmentStatus.WITHDRAWN),
            (transferred, EnrolmentStatus.TRANSFERRED),
        ):
            row = await session.get(Enrolment, enrolment.id)
            row.status = status
        await session.flush()
        # the ledger releases the seats and revokes, as an update upload would
        result = await assign_seats(session, [withdrawn.id, transferred.id], actor_id=registrar.id)
        assert result.released == [withdrawn.id, transferred.id]
        # what the cases area does on CONFIRM
        assert (
            await credentials.revoke_for_enrolment(
                session, confirmed.id, "FLAG_CONFIRMED", officer.id
            )
            == 1
        )
        await session.commit()

    async with signed_in("admin@aicte.demo") as admin, public() as anyone:
        response = await admin.post(
            f"/credentials/{proofs['admin'].id}/revoke",
            json={"reason": "Admission found to be fraudulent after inquiry."},
        )
        assert response.json()["revoked_reason_code"] == "ADMIN"

        cards = {c["id"]: c for c in (await admin.get("/credentials")).json()["items"]}
        expected = {
            "withdrawn": ("ENROLMENT_WITHDRAWN", "ENROLMENT_WITHDRAWN"),
            "transferred": ("ENROLMENT_TRANSFERRED", "ENROLMENT_TRANSFERRED"),
            "confirmed": ("FLAG_CONFIRMED", "FLAG_CONFIRMED"),
            "admin": ("ADMIN", "Admission found to be fraudulent after inquiry."),
        }
        for name, (code, stored) in expected.items():
            card = cards[str(proofs[name].id)]
            assert card["status"] == "REVOKED"
            assert (card["revoked_reason_code"], card["revoked_reason"]) == (code, stored)
            detail = (await admin.get(f"/credentials/{proofs[name].id}")).json()
            assert detail["revoked_reason_code"] == code
        # every cause sets the bit a verifier reads, and none of them says why
        token = (await anyone.get("/status-lists/1")).text
        bits = status_list.decode(b64json(token.split(".")[1])["status_list"]["lst"])
        assert all(status_list.bit(bits, p.status_list_index) == 1 for p in proofs.values())

    async with session_factory()() as session:
        refs = await holder.credential_refs(session, withdrawn.id)
        assert refs[0]["revoked_reason_code"] == "ENROLMENT_WITHDRAWN"
        ledger_entry = (
            (
                await session.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.entity_id == proofs["withdrawn"].id,
                        AuditLog.action == AuditAction.UPDATE,
                    )
                    .order_by(AuditLog.seq.desc())
                )
            )
            .scalars()
            .first()
        )
        assert ledger_entry.actor_id == registrar.id
        assert ledger_entry.after["reason_code"] == "ENROLMENT_WITHDRAWN"
        revoked_by = {
            name: (await session.get(type(proofs[name]), proofs[name].id)).revoked_by_id
            for name in expected
        }
    assert revoked_by["withdrawn"] == registrar.id and revoked_by["confirmed"] == officer.id
