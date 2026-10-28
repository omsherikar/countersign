"""POST /flags/{id}/actions and POST /flags/{id}/response over HTTP: every cell of the
§A3.9 table for every role (403 against 404 against 409), the field rules, the effects of
each action and the document request email."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from app.core.audit import verify_chain
from app.db.session import session_factory
from app.engine.upload.types import INDIA
from app.models.audit import AuditLog
from app.models.enums import FlagStatus
from app.models.verification import CaseAction
from tests.cases.conftest import FailingMailer, load_flag, new_flag, set_status

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
OFFICER_ACTIONS = ["UPHOLD", "REQUEST_DOCS", "ESCALATE", "WITHDRAW", "NOTE", "ASSIGN", "REOPEN"]
# what the table allows each officer role from each status (None: nobody, 409)
ALLOWED = {
    "OPEN": {"A": {"UPHOLD", "REQUEST_DOCS", "ESCALATE", "WITHDRAW", "NOTE", "ASSIGN"}},
    "DOCS_REQUESTED": {"A": {"UPHOLD", "REQUEST_DOCS", "ESCALATE", "WITHDRAW", "NOTE", "ASSIGN"}},
    "ESCALATED": {"A": {"UPHOLD", "REQUEST_DOCS", "WITHDRAW", "NOTE", "ASSIGN"}, "R": {"NOTE"}},
    "UPHELD": {"A": {"NOTE", "REOPEN"}, "R": {"NOTE"}},
    "WITHDRAWN": {"A": {"NOTE", "REOPEN"}, "R": {"NOTE"}},
    # no officer action leads here yet
    "CORRECTED": {"A": set()},
}
for _row in ALLOWED.values():
    _row.setdefault("R", _row["A"])


def body(action: str) -> dict:
    out: dict = {"action": action, "note": "Checked against the admission register."}
    if action == "ASSIGN":
        out["assignee_id"] = None
    return out


def expected(role: str, status: str, action: str) -> int:
    allowed = ALLOWED[status]
    if action in allowed[role]:
        return 200
    if any(action in allowed[r] for r in ("A", "R")):
        return 403
    return 409


def today() -> date:
    return datetime.now(INDIA).date()


async def respond(client, flag_id, note: str = "Register extract attached.", files=None):
    """Always multipart, as a browser form is: an empty file input still sends one part."""
    parts = files if files is not None else [("files", ("", b"", "application/octet-stream"))]
    return await client.post(f"/flags/{flag_id}/response", data={"note": note}, files=parts)


async def test_every_cell_for_every_role(cw, logins, mailbox, case_files) -> None:
    flag_id = await new_flag(cw)
    admin = await logins("admin@aicte.demo")
    west = await logins("ro.west@aicte.demo")
    south = await logins("ro.south@aicte.demo")
    registrar = await logins("registrar@abc.edu.demo")
    other_college = await logins("registrar@xyz.edu.demo")
    university = await logins("coe@univ.demo")
    student = await logins("student@demo")
    seen = 0
    for status in FlagStatus:
        for action in OFFICER_ACTIONS:
            cases = [
                (admin, expected("A", status.value, action)),
                (west, expected("R", status.value, action)),
                (south, 404),  # ABC is outside the southern region
                (registrar, 403),
                (other_college, 403),
                (university, 403),
                (student, 403),
            ]
            for client, code in cases:
                await set_status(flag_id, status)
                response = await client.post(f"/flags/{flag_id}/actions", json=body(action))
                where = f"{action} from {status.value}: {response.text}"
                assert response.status_code == code, where
                if code == 409:
                    error = response.json()["error"]
                    assert error["code"] == "FLAG_TRANSITION_INVALID", where
                    assert error["details"]["status"] == status.value
                    assert error["details"]["action"] == action
                if code == 200:
                    assert response.json()["status"] != "" and response.json()["history"], where
                seen += 1
        responders = [
            (registrar, 201 if status is FlagStatus.DOCS_REQUESTED else 409),
            (other_college, 404),
            (admin, 403),
            (west, 403),
            (south, 403),
            (university, 403),
            (student, 403),
        ]
        for client, code in responders:
            await set_status(flag_id, status)
            response = await respond(client, flag_id)
            assert response.status_code == code, f"response from {status.value}: {response.text}"
            seen += 1
    assert seen == len(FlagStatus) * (7 * 7 + 7)
    async with session_factory()() as session:
        assert (await verify_chain(session))[0]


async def test_outcomes_of_each_action(cw, logins, mailbox) -> None:
    admin = await logins("admin@aicte.demo")
    flag_id = await new_flag(cw)
    due = today() + timedelta(days=14)

    docs = await admin.post(
        f"/flags/{flag_id}/actions",
        json={"action": "REQUEST_DOCS", "note": "Send the register.", "due_date": due.isoformat()},
    )
    assert docs.status_code == 200, docs.text
    detail = docs.json()
    assert detail["status"] == "DOCS_REQUESTED" and detail["docs_due_on"] == due.isoformat()
    assert detail["response_received"] is False and detail["last_action_at"]
    assert detail["history"][-1]["from_status"] == "OPEN"
    assert detail["history"][-1]["to_status"] == "DOCS_REQUESTED"
    assert detail["history"][-1]["due_date"] == due.isoformat()

    cleared = (
        await admin.post(f"/flags/{flag_id}/actions", json={"action": "UPHOLD", "note": "Fine."})
    ).json()
    assert cleared["status"] == "UPHELD" and cleared["allowed_actions"] == ["NOTE", "REOPEN"]
    assert (await load_flag(flag_id)).resolved_at is not None

    reopened = (
        await admin.post(f"/flags/{flag_id}/actions", json={"action": "REOPEN", "note": "Again."})
    ).json()
    assert reopened["status"] == "OPEN"
    assert reopened["docs_due_on"] is None and reopened["response_received"] is False
    flag = await load_flag(flag_id)
    assert flag.resolved_at is None and flag.docs_due_on is None

    noted = (
        await admin.post(f"/flags/{flag_id}/actions", json={"action": "NOTE", "note": "Hmm."})
    ).json()
    assert noted["status"] == "OPEN"
    assert [h["action"] for h in noted["history"]] == ["REQUEST_DOCS", "UPHOLD", "REOPEN", "NOTE"]

    async with session_factory()() as session:
        rows = (
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.entity_type == "flag", AuditLog.entity_id == flag_id)
                    .where(AuditLog.action == "UPDATE")
                    .order_by(AuditLog.seq)
                )
            )
            .scalars()
            .all()
        )
    assert [r.after["action"] for r in rows] == ["REQUEST_DOCS", "UPHOLD", "REOPEN", "NOTE"]
    assert rows[0].after["due_date"] == due.isoformat()
    assert all(r.actor_id == cw.users["admin@aicte.demo"] for r in rows)
    # the note text never reaches the audit log
    assert "Send the register" not in str([r.after for r in rows])


async def test_field_rules_come_after_scope_and_status(cw, logins, mailbox) -> None:
    admin = await logins("admin@aicte.demo")
    west = await logins("ro.west@aicte.demo")
    flag_id = await new_flag(cw)
    url = f"/flags/{flag_id}/actions"

    def field_of(response) -> tuple[int, str, str]:
        error = response.json()["error"]
        fields = error["details"].get("fields") or [{"field": "", "message": ""}]
        return response.status_code, fields[0]["field"], fields[0]["message"]

    assert field_of(await admin.post(url, json={"action": "UPHOLD"})) == (
        422,
        "note",
        "Add a note before you continue.",
    )
    assert field_of(await admin.post(url, json={"action": "UPHOLD", "note": "   "}))[1] == "note"
    shape = await admin.post(url, json={"action": "SYSTEM_NOTE", "note": "x"})
    assert shape.status_code == 422 and field_of(shape)[1] == "action"
    long = await admin.post(url, json={"action": "NOTE", "note": "x" * 2001})
    assert field_of(long) == (422, "note", "Write at most 2,000 characters.")
    assert (await admin.post(url, json={"action": "NOTE", "note": "x" * 2000})).status_code == 200

    # 404 before anything else, and 409 before the missing note
    assert (
        await admin.post("/flags/00000000-0000-4000-8000-000000000000/actions", json={})
    ).status_code == 422
    missing = await admin.post(
        "/flags/00000000-0000-4000-8000-000000000000/actions", json={"action": "NOTE"}
    )
    assert missing.status_code == 404 and missing.json()["error"]["message"] == "Flag not found."
    await set_status(flag_id, FlagStatus.UPHELD)
    assert (await admin.post(url, json={"action": "UPHOLD"})).status_code == 409
    assert (await west.post(url, json={"action": "REOPEN"})).status_code == 403
    await set_status(flag_id, FlagStatus.OPEN)

    now = today()
    for bad in (now - timedelta(days=1), now + timedelta(days=91)):
        response = await admin.post(
            url, json={"action": "REQUEST_DOCS", "note": "Send it.", "due_date": bad.isoformat()}
        )
        assert field_of(response) == (
            422,
            "due_date",
            "Choose a date from today up to 90 days ahead.",
        )
    edge = (now + timedelta(days=90)).isoformat()
    ok = await admin.post(url, json={"action": "REQUEST_DOCS", "note": "Send.", "due_date": edge})
    assert ok.status_code == 200 and ok.json()["docs_due_on"] == edge
    # a date sent with another action is ignored
    noted = await admin.post(
        url, json={"action": "NOTE", "note": "Seen.", "due_date": "2001-01-01"}
    )
    assert noted.status_code == 200 and noted.json()["history"][-1]["due_date"] is None

    # ASSIGN: the key is required (null unassigns) and the note is ignored
    assert field_of(await admin.post(url, json={"action": "ASSIGN"}))[1] == "assignee_id"
    south = cw.users["ro.south@aicte.demo"]
    unseen = await admin.post(url, json={"action": "ASSIGN", "assignee_id": str(south)})
    assert field_of(unseen) == (422, "assignee_id", "Choose an officer who can see this flag.")
    retired = cw.users["retired@aicte.demo"]
    gone = await admin.post(url, json={"action": "ASSIGN", "assignee_id": str(retired)})
    assert field_of(gone)[2] == "Choose an officer who can see this flag."
    registrar = cw.users["registrar@abc.edu.demo"]
    college = await admin.post(url, json={"action": "ASSIGN", "assignee_id": str(registrar)})
    assert field_of(college)[2] == "Choose an officer who can see this flag."
    deputy = cw.users["deputy.west@aicte.demo"]
    assigned = await admin.post(
        url, json={"action": "ASSIGN", "assignee_id": str(deputy), "note": "ignored"}
    )
    assert assigned.status_code == 200
    assert assigned.json()["assignee"] == {"id": str(deputy), "name": "Deputy Officer, Western"}
    assert assigned.json()["history"][-1]["note"] is None
    escalate_to_ro = await admin.post(
        url, json={"action": "ESCALATE", "note": "Senior view.", "assignee_id": str(deputy)}
    )
    assert field_of(escalate_to_ro) == (422, "assignee_id", "Escalate to an AICTE officer.")
    senior = cw.users["senior@aicte.demo"]
    escalated = await west.post(
        url, json={"action": "ESCALATE", "note": "Senior view.", "assignee_id": str(senior)}
    )
    assert escalated.status_code == 200
    assert escalated.json()["assignee"]["id"] == str(senior)
    assert escalated.json()["allowed_actions"] == ["NOTE"]
    unassigned = await admin.post(url, json={"action": "ASSIGN", "assignee_id": None})
    assert unassigned.status_code == 200 and unassigned.json()["assignee"] is None


async def test_request_docs_emails_every_active_registrar(cw, logins, mailbox) -> None:
    west = await logins("ro.west@aicte.demo")
    flag_id = await new_flag(cw)
    due = today() + timedelta(days=10)
    response = await west.post(
        f"/flags/{flag_id}/actions",
        json={
            "action": "REQUEST_DOCS",
            "note": "Send the admission register extract for CSE, 2026-27.",
            "due_date": due.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert sorted(m.to for m in mailbox.sent) == ["office@abc.edu.demo", "registrar@abc.edu.demo"]
    message = mailbox.sent[0]
    assert message.subject == (
        "Documents requested by AICTE: Name or date of birth mismatch, CSE, 2026-27"
    )
    due_word = f"{due.day} {due.strftime('%b')} {due.year}"
    assert message.body.startswith(
        "The Western regional office has asked ABC College of Engineering for documents "
        "about a flag. Flag: Name or date of birth mismatch, CSE, 2026-27. Evidence: The name "
        "you uploaded differs from APAAR"
    )
    assert (
        'Request: "Send the admission register extract for CSE, 2026-27." '
        f"Please reply by {due_word}. Sign in to Countersign"
    ) in message.body
    assert f"http://localhost:3000/college/flags/{flag_id}." in message.body
    for name in ("Ravi", "Sharma", "Regional Officer", "Western,", "admin@"):
        assert name not in message.body and name not in message.subject

    # without a date the due sentence is left out
    mailbox.sent.clear()
    await west.post(f"/flags/{flag_id}/actions", json={"action": "REQUEST_DOCS", "note": "Again."})
    assert 'Request: "Again." Sign in to Countersign' in mailbox.sent[0].body


async def test_a_mail_failure_never_undoes_the_request(cw, logins, monkeypatch) -> None:
    monkeypatch.setattr("app.routers.cases.build_mailer", lambda: FailingMailer())
    admin = await logins("admin@aicte.demo")
    flag_id = await new_flag(cw)
    response = await admin.post(
        f"/flags/{flag_id}/actions", json={"action": "REQUEST_DOCS", "note": "Send it."}
    )
    assert response.status_code == 200
    assert (await load_flag(flag_id)).status is FlagStatus.DOCS_REQUESTED


async def test_detail_tells_each_role_what_it_can_do(cw, logins) -> None:
    flag_id = await new_flag(cw, status=FlagStatus.DOCS_REQUESTED)
    registrar = (await (await logins("registrar@abc.edu.demo")).get(f"/flags/{flag_id}")).json()
    assert registrar["allowed_actions"] == [] and registrar["can_respond"] is True
    west = (await (await logins("ro.west@aicte.demo")).get(f"/flags/{flag_id}")).json()
    assert west["can_respond"] is False
    assert west["allowed_actions"] == [
        "UPHOLD",
        "REQUEST_DOCS",
        "ESCALATE",
        "WITHDRAW",
        "NOTE",
        "ASSIGN",
    ]
    await set_status(flag_id, FlagStatus.OPEN)
    registrar = (await (await logins("registrar@abc.edu.demo")).get(f"/flags/{flag_id}")).json()
    assert registrar["can_respond"] is False


async def test_list_filters_by_assignee_and_response(cw, logins, mailbox) -> None:
    admin = await logins("admin@aicte.demo")
    deputy_client = await logins("deputy.west@aicte.demo")
    deputy = cw.users["deputy.west@aicte.demo"]
    mine = await new_flag(cw)
    answered = await new_flag(cw, status=FlagStatus.DOCS_REQUESTED)
    await admin.post(
        f"/flags/{mine}/actions", json={"action": "ASSIGN", "assignee_id": str(deputy)}
    )
    await set_status(answered, FlagStatus.DOCS_REQUESTED, response_received=True)

    ids = lambda page: {i["id"] for i in page["items"]}  # noqa: E731
    by_me = (await deputy_client.get("/flags", params={"assignee": "me"})).json()
    assert str(mine) in ids(by_me) and str(answered) not in ids(by_me)
    by_id = (await admin.get("/flags", params={"assignee": str(deputy)})).json()
    assert ids(by_id) == ids(by_me)
    row = next(i for i in by_id["items"] if i["id"] == str(mine))
    assert row["assignee"] == {"id": str(deputy), "name": "Deputy Officer, Western"}
    nobody = (await admin.get("/flags", params={"assignee": "none"})).json()
    assert str(mine) not in ids(nobody) and str(answered) in ids(nobody)
    bad = await admin.get("/flags", params={"assignee": "someone"})
    assert bad.status_code == 422

    to_read = (
        await admin.get("/flags", params={"status": "DOCS_REQUESTED", "response_received": "true"})
    ).json()
    assert str(answered) in ids(to_read) and str(mine) not in ids(to_read)
    assert all(i["response_received"] for i in to_read["items"])
    not_yet = (await admin.get("/flags", params={"response_received": "false"})).json()
    assert str(answered) not in ids(not_yet)

    # a college never sees the assignee, and the assignee filter is ignored for it
    registrar = await logins("registrar@abc.edu.demo")
    college = (await registrar.get("/flags", params={"assignee": str(deputy)})).json()
    assert str(answered) in ids(college)
    assert all(i["assignee"] is None for i in college["items"])
    detail = (await registrar.get(f"/flags/{mine}")).json()
    assert detail["assignee"] is None


async def test_status_filter_takes_docs_requested(cw, logins) -> None:
    admin = await logins("admin@aicte.demo")
    flag_id = await new_flag(cw, status=FlagStatus.DOCS_REQUESTED)
    page = (await admin.get("/flags", params={"status": "DOCS_REQUESTED"})).json()
    assert str(flag_id) in {i["id"] for i in page["items"]}
    assert {i["status"] for i in page["items"]} == {"DOCS_REQUESTED"}


async def test_actions_write_one_row_each(cw, logins, mailbox) -> None:
    admin = await logins("admin@aicte.demo")
    flag_id = await new_flag(cw)
    for action in ("NOTE", "ESCALATE", "NOTE", "WITHDRAW", "REOPEN"):
        response = await admin.post(f"/flags/{flag_id}/actions", json=body(action))
        assert response.status_code == 200, response.text
    async with session_factory()() as session:
        count = (
            await session.execute(
                select(func.count()).select_from(CaseAction).where(CaseAction.flag_id == flag_id)
            )
        ).scalar_one()
    assert count == 5
