"""Student-held credentials (SD-JWT VC, DECISIONS D26).

These two functions are what the rest of the api calls: the Seat Ledger revokes when an
enrolment is withdrawn or transferred, and the checks, the notice loop and case actions
ask for issuance once an enrolment may have become eligible. The ledger imports this
package on every batch, so the SD-JWT code is loaded only when something is issued.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit import AuditEntry
from app.credentials import status_list
from app.models.credential import Credential
from app.models.enums import AuditAction

# What the system revokes for, stored as is in `revoked_reason` (API_CONTRACT A3.18). An
# officer's revocation stores the officer's words instead, and reads back as ADMIN.
SYSTEM_REASON_CODES = ("ENROLMENT_WITHDRAWN", "ENROLMENT_TRANSFERRED", "FLAG_CONFIRMED")
# the Seat Ledger's words for the same causes
_LEDGER_REASONS = {
    "Enrolment withdrawn": "ENROLMENT_WITHDRAWN",
    "Enrolment transferred": "ENROLMENT_TRANSFERRED",
}


def system_reason_code(reason: str) -> str:
    """The stored code for a system revocation; ValueError for anything else."""
    if reason in SYSTEM_REASON_CODES:
        return reason
    if reason in _LEDGER_REASONS:
        return _LEDGER_REASONS[reason]
    raise ValueError(f"not a revocation reason: {reason!r}")


async def revoke_for_enrolment(
    session: AsyncSession,
    enrolment_id: uuid.UUID,
    reason: str,
    actor_id: uuid.UUID | None,
    *,
    audit_sink: list[AuditEntry] | None = None,
) -> int:
    """Revoke every unrevoked credential of the enrolment, in the caller's transaction.

    `reason` is a reason code (ENROLMENT_WITHDRAWN, ENROLMENT_TRANSFERRED, FLAG_CONFIRMED) or
    the ledger's words for the first two; the code is what is stored and audited. Sets
    `revoked`, `revoked_at`, `revoked_reason` and `revoked_by_id` (null when the system
    revokes) and writes one audit UPDATE per credential; returns how many it revoked.
    Revoked credentials are left as they are, so calling it again does nothing. With
    `audit_sink` the audit entries are appended there for the caller to write in one
    `record_many`; without it they are written at once.
    """
    code = system_reason_code(reason)
    credentials = (
        (
            await session.execute(
                select(Credential)
                .where(Credential.enrolment_id == enrolment_id, Credential.revoked == false())
                .order_by(Credential.issued_at, Credential.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if not credentials:
        return 0
    now = datetime.now(UTC)
    entries: list[AuditEntry] = []
    for credential in credentials:
        credential.revoked = True
        credential.revoked_at = now
        credential.revoked_reason = code
        credential.revoked_by_id = actor_id
        entries.append(
            AuditEntry(
                action=AuditAction.UPDATE,
                entity_type="credential",
                entity_id=credential.id,
                actor_id=actor_id,
                before={"revoked": False},
                after={
                    "revoked": True,
                    "revoked_at": now.isoformat(),
                    "revoked_reason": code,
                    "reason_code": code,
                    "kind": credential.kind.value,
                    "enrolment_id": str(enrolment_id),
                },
            )
        )
    await session.flush()
    if audit_sink is not None:
        audit_sink.extend(entries)
    else:
        await audit.record_many(session, entries)
    status_list.invalidate_after_commit(session)
    return len(credentials)


async def issue_if_eligible(session: AsyncSession, enrolment_id: uuid.UUID) -> Credential | None:
    """Issue the ENROLMENT credential if the enrolment is eligible and has none live.

    Eligible means the enrolment is ACTIVE, its STUDENT check is PASS, no check is FAIL and
    no unresolved HIGH flag names it (issuer.eligibility). Runs in the caller's transaction,
    never raises for an ineligible enrolment, and returns the credential issued or None.
    Callers: after a recheck, after a Yes reply to a notice and after a case is cleared.
    """
    from app.credentials import issuer

    return await issuer.issue_if_eligible(session, enrolment_id)
