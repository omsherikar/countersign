"""Case history: what the college may read of it, the reason codes and document kinds it
carries, and what a withdrawal leaves in it."""

from __future__ import annotations

from app.cases.decisions import withdraw_code
from app.db.session import session_factory
from app.models.credential import Credential
from app.models.enums import EnrolmentStatus
from app.models.student import Enrolment
from tests.cases.conftest import add_credential, new_flag

PDF = b"%PDF-1.4\n%%EOF\n"


async def test_the_college_never_sees_assignments_or_internal_notes(cw, logins, mailbox) -> None:
    admin = await logins("admin@aicte.demo")
    west = await logins("ro.west@aicte.demo")
    registrar = await logins("registrar@abc.edu.demo")
    flag_id = await new_flag(cw)
    url = f"/flags/{flag_id}/actions"
    senior = cw.users["senior@aicte.demo"]
    steps = [
        (west, {"action": "ASSIGN", "assignee_id": str(cw.users["ro.west@aicte.demo"])}),
        (west, {"action": "NOTE", "note": "Looks like a typing slip."}),
        (
            west,
            {
                "action": "REQUEST_DOCS",
                "docs_kind": "ADMISSION",
                "note": "Send the admission form.",
            },
        ),
    ]
    for client, payload in steps:
        assert (await client.post(url, json=payload)).status_code == 200
    response = await registrar.post(
        f"/flags/{flag_id}/response",
        data={"note": "Form attached."},
        files=[("files", ("form.pdf", PDF, "application/pdf"))],
    )
    assert response.status_code == 201
    escalate = {
        "action": "ESCALATE",
        "reason_code": "NEEDS_AICTE_DECISION",
        "note": "Same name twice.",
        "assignee_id": str(senior),
    }
    uphold = {"action": "UPHOLD", "reason_code": "NAME_VARIANT", "note": "The form settles it."}
    later = [
        (west, escalate),
        (admin, uphold),
        (admin, {"action": "REOPEN", "note": "New information from the region."}),
    ]
    for client, payload in later:
        assert (await client.post(url, json=payload)).status_code == 200

    officer = (await west.get(f"/flags/{flag_id}")).json()["history"]
    assert [h["action"] for h in officer] == [
        "ASSIGN",
        "NOTE",
        "REQUEST_DOCS",
        "COLLEGE_RESPONSE",
        "ESCALATE",
        "UPHOLD",
        "REOPEN",
    ]
    assert officer[0]["assignee"]["id"] == str(cw.users["ro.west@aicte.demo"])
    assert officer[0]["note"] is None
    assert officer[4]["assignee"] == {"id": str(senior), "name": "Senior AICTE Officer"}
    assert officer[1]["note"] == "Looks like a typing slip."
    assert officer[1]["actor"] == {
        "id": str(cw.users["ro.west@aicte.demo"]),
        "name": "Regional Officer, Western",
        "role": "RO_OFFICER",
    }

    college = (await registrar.get(f"/flags/{flag_id}")).json()["history"]
    assert [h["action"] for h in college] == [
        "NOTE",
        "REQUEST_DOCS",
        "COLLEGE_RESPONSE",
        "ESCALATE",
        "UPHOLD",
        "REOPEN",
    ]
    notes = {h["action"]: h["note"] for h in college}
    assert notes == {
        "NOTE": None,
        "REQUEST_DOCS": "Send the admission form.",
        "COLLEGE_RESPONSE": "Form attached.",
        "ESCALATE": None,
        "UPHOLD": "The form settles it.",
        "REOPEN": None,
    }
    assert all(h["assignee"] is None for h in college)
    assert "Senior AICTE Officer" not in str(college)
    assert college[2]["attachments"][0]["filename"] == "form.pdf"
    # status changes stay visible even where the words are kept back
    assert (college[3]["from_status"], college[3]["to_status"]) == ("DOCS_REQUESTED", "ESCALATED")
    # reason codes and document kinds are shown to everyone who can open the case
    words = {h["action"]: (h["reason_code"], h["docs_kind"]) for h in college}
    assert words["REQUEST_DOCS"] == (None, "ADMISSION")
    assert words["ESCALATE"] == ("NEEDS_AICTE_DECISION", None)
    assert words["UPHOLD"] == ("NAME_VARIANT", None)
    assert all(h["correction"] is None and h["withdrawn_enrolment_ids"] == [] for h in college)


async def test_a_withdrawal_takes_the_record_out_and_stays_in_the_history(cw, logins) -> None:
    """D43: the record leaves the active counts and its attestation is revoked; the history
    names the records withdrawn. (Seat, backlog and dry run: tests/decisions.)"""
    admin = await logins("admin@aicte.demo")
    registrar = await logins("registrar@abc.edu.demo")
    flag_id = await new_flag(cw)
    credential_id = await add_credential(cw.ravi_student, cw.ravi)
    response = await admin.post(
        f"/flags/{flag_id}/actions",
        json={
            "action": "WITHDRAW",
            "reason_code": "STUDENT_NEVER_JOINED",
            "note": "The college could not produce an admission record.",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "WITHDRAWN"
    async with session_factory()() as session:
        enrolment = await session.get(Enrolment, cw.ravi)
        credential = await session.get(Credential, credential_id)
    assert enrolment.status is EnrolmentStatus.WITHDRAWN and enrolment.seat_id is None
    assert credential.revoked is True and credential.revoked_reason == withdraw_code()
    assert credential.revoked_by_id == cw.users["admin@aicte.demo"]
    history = (await registrar.get(f"/flags/{flag_id}")).json()["history"]
    assert history[-1]["action"] == "WITHDRAW"
    assert history[-1]["withdrawn_enrolment_ids"] == [str(cw.ravi)]
    assert history[-1]["reason_code"] == "STUDENT_NEVER_JOINED"

    # a case that names no record has nothing to withdraw
    unnamed = await new_flag(cw, institution="xyz")
    none = await admin.post(
        f"/flags/{unnamed}/actions",
        json={"action": "WITHDRAW", "reason_code": "OTHER", "note": "Nothing named."},
    )
    assert none.status_code == 422
    assert none.json()["error"]["code"] == "WITHDRAW_NONE_SELECTED"
