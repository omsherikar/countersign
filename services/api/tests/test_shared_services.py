"""The mailer, consent record and system note that the notices loop, cases and wallet share."""

import uuid

import pytest
from sqlalchemy import select

from app.cases.service import add_system_note
from app.core.config import get_settings
from app.db.session import session_factory
from app.models.enums import CaseActionKind, ConsentPurpose, ConsentState, FlagType, Severity
from app.models.institution import Institution
from app.models.student import Student
from app.models.verification import Flag
from app.notices.mailer import MailMessage, MemoryMailer, SmtpMailer, SmtpRefused, smtp_host_allowed
from app.privacy.service import notice_consent_withdrawn, record_consent


async def test_shared_entry_points(seeded):
    async with session_factory()() as s:
        st = (await s.execute(select(Student).limit(1))).scalar_one()
        inst = (await s.execute(select(Institution).limit(1))).scalar_one()
        await record_consent(
            s,
            student_id=st.id,
            purpose=ConsentPurpose.NOTICE,
            status=ConsentState.GIVEN,
            channel="NOTICE_EMAIL",
            notice_text="t",
        )
        assert await notice_consent_withdrawn(s, [st.id]) == set()
        await record_consent(
            s,
            student_id=st.id,
            purpose=ConsentPurpose.NOTICE,
            status=ConsentState.WITHDRAWN,
            channel="PORTAL",
            notice_text="t",
        )
        assert await notice_consent_withdrawn(s, [st.id]) == {st.id}
        f = Flag(
            type=FlagType.STUDENT_DENIED,
            severity=Severity.HIGH,
            institution_id=inst.id,
            evidence={},
            dedupe_key=f"x-{uuid.uuid4()}",
            related_enrolment_ids=[],
        )
        s.add(f)
        await s.flush()
        row = await add_system_note(s, f, "Evidence updated after the decision")
        assert (
            row.action == CaseActionKind.SYSTEM_NOTE and row.actor_id is None and f.last_action_at
        )
        await s.rollback()
    m = MemoryMailer()
    m.send_many([MailMessage(to="a@b.invalid", subject="s", body="b")])
    assert len(m.sent) == 1
    st_ = get_settings().model_copy(update={"smtp_host": "smtp.gmail.com"})
    assert not smtp_host_allowed("smtp.gmail.com", st_)
    with pytest.raises(SmtpRefused):
        SmtpMailer(st_)
