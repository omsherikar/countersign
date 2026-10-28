from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy import select

from app.chaos import chaos_gate
from app.db import SessionDep
from app.ids import inbox_id
from app.models import ApaarRecord, DigiLockerMessage
from app.schemas import (
    DigiLockerInboxItem,
    DigiLockerInboxResponse,
    DigiLockerNotifyRequest,
    DigiLockerNotifyResponse,
)

router = APIRouter(
    prefix="/digilocker", tags=["digilocker"], dependencies=[Depends(chaos_gate("digilocker"))]
)


@router.post("/notify", response_model=DigiLockerNotifyResponse)
async def notify(
    body: DigiLockerNotifyRequest,
    response: Response,
    session: SessionDep,
) -> DigiLockerNotifyResponse:
    """Drops a notice into the student's DigiLocker inbox. 202 when delivered, 200 when the
    APAAR id is not linked to any DigiLocker account."""
    if await session.get(ApaarRecord, body.apaar_id) is None:
        return DigiLockerNotifyResponse(delivered=False, inbox_id=None, reason="APAAR_NOT_LINKED")

    message = DigiLockerMessage(
        inbox_id=inbox_id(),
        apaar_id=body.apaar_id,
        message=body.message,
        callback_url=body.callback_url,
        received_at=datetime.now(UTC),
        read=False,
    )
    session.add(message)
    await session.commit()
    response.status_code = 202
    return DigiLockerNotifyResponse(delivered=True, inbox_id=message.inbox_id)


@router.get("/inbox/{apaar_id}", response_model=DigiLockerInboxResponse)
async def inbox(
    apaar_id: Annotated[str, Path(pattern=r"^\d{12}$")],
    session: SessionDep,
) -> DigiLockerInboxResponse:
    """Everything delivered to one id, newest first. Used by the demo's student view."""
    rows = await session.scalars(
        select(DigiLockerMessage)
        .where(DigiLockerMessage.apaar_id == apaar_id)
        .order_by(DigiLockerMessage.received_at.desc(), DigiLockerMessage.inbox_id.desc())
    )
    return DigiLockerInboxResponse(
        items=[
            DigiLockerInboxItem(
                inbox_id=r.inbox_id,
                message=r.message,
                callback_url=r.callback_url,
                received_at=r.received_at,
                read=r.read,
            )
            for r in rows
        ]
    )
