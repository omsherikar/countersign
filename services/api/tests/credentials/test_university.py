"""Degree print over HTTP: graduates, issue, print data, the insert, and the two ways a
printed proof is checked, which must agree."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import EnrolmentStatus
from app.models.student import Enrolment, Student
from tests.credentials.conftest import ravi_enrolment
from tests.credentials.helpers import b64json, public, signed_in
from tests.credentials.test_degree import _pdf_text


async def _graduate(name: str) -> uuid.UUID:
    async with session_factory()() as session:
        return (
            await session.execute(
                select(Enrolment.id)
                .join(Student, Student.id == Enrolment.student_id)
                .where(Student.name == name, Enrolment.status == EnrolmentStatus.GRADUATED)
            )
        ).scalar_one()


async def test_graduates_by_scope_and_search(world):
    async with (
        signed_in("coe@univ.demo") as university,
        signed_in("admin@aicte.demo") as admin,
        signed_in("ro.west@aicte.demo") as ro,
        signed_in("registrar@abc.edu.demo") as registrar,
        signed_in("student@demo") as student,
    ):
        for client in (ro, registrar, student):
            assert (await client.get("/university/graduates")).status_code == 403

        own = (await university.get("/university/graduates")).json()
        assert [row["student"]["name"] for row in own["items"]] == [
            "Aditya Phadke",
            "Gauri Sathe",
            "Meera Kulkarni",
        ]
        meera = own["items"][2]
        assert meera["student"]["apaar_masked"] == "XXXX XXXX 0401"
        assert meera["student"]["provisional_id"] is None
        assert meera["institution"]["aicte_permanent_id"] == "1-ABC-0001"
        assert meera["programme"]["code"] == "CSE" and meera["programme"]["level"] == "UG"
        assert meera["academic_year"] == "2025-26" and meera["year_of_award"] == 2026
        assert meera["degree"] is None
        gauri = own["items"][1]
        assert gauri["student"] == {
            "id": gauri["student"]["id"],
            "name": "Gauri Sathe",
            "apaar_masked": None,
            "provisional_id": "PRV-GQ4DKN7A",
        }
        assert "202500000401" not in str(own)

        everyone = (await admin.get("/university/graduates")).json()
        assert everyone["total"] == 4
        for q, names in (
            ("meera", ["Meera Kulkarni"]),
            ("0402", ["Aditya Phadke"]),
            ("PRV-GQ4D", ["Gauri Sathe"]),
            ("%", []),
        ):
            found = (await university.get("/university/graduates", params={"q": q})).json()
            assert [row["student"]["name"] for row in found["items"]] == names

        xyz = (await admin.get("/meta/regions")).status_code  # any signed-in read works
        assert xyz == 200
        async with session_factory()() as session:
            sowmya = await session.get(Enrolment, await _graduate("Sowmya Ramesh"))
        outside = await university.get(
            "/university/graduates", params={"institution_id": str(sowmya.institution_id)}
        )
        assert outside.status_code == 404

    async with session_factory()() as session:
        reads = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "student", AuditLog.action == "READ"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(reads) >= 3


async def test_issue_print_and_verify_a_degree(world):
    meera = await _graduate("Meera Kulkarni")
    sowmya = await _graduate("Sowmya Ramesh")
    async with session_factory()() as session:
        ravi = (await ravi_enrolment(session)).id
    async with (
        signed_in("coe@univ.demo") as university,
        signed_in("admin@aicte.demo") as admin,
        signed_in("student@demo") as student,
        public() as anyone,
    ):
        assert (await university.post(f"/university/degrees/{sowmya}/issue")).status_code == 404
        not_graduated = await university.post(f"/university/degrees/{ravi}/issue")
        assert not_graduated.status_code == 409
        assert not_graduated.json()["error"] == {
            "code": "CREDENTIAL_NOT_ELIGIBLE",
            "message": "Degree proofs are issued only for graduated students.",
            "details": {"reason": "NOT_GRADUATED"},
        }
        before = (await university.get(f"/university/degrees/{meera}")).json()
        assert before["degree"] is None
        not_issued = await university.get(f"/university/degrees/{meera}/insert.pdf")
        assert not_issued.status_code == 409
        assert not_issued.json()["error"]["details"] == {"reason": "NOT_ISSUED"}

        issued = await university.post(f"/university/degrees/{meera}/issue", json={})
        assert issued.status_code == 201
        body = issued.json()
        assert body["student"] == {
            "name": "Meera Kulkarni",
            "id_kind": "APAAR",
            "id_masked": "XXXX XXXX 0401",
        }
        assert body["programme"] == {
            "code": "CSE",
            "name": "B.Tech Computer Science and Engineering",
            "short_name": "B.Tech CS & Engg.",
        }
        assert body["institution"]["short_name"] == "ABC College of Engg."
        assert body["university"] == {
            "code": "MSTU",
            "name": "Maharashtra State Technical University",
        }
        proof = body["degree"]
        assert proof["status"] == "ACTIVE" and len(proof["short_id"]) == 8
        assert proof["verify_url"] == f"http://localhost:3000/verify/d/{proof['jws']}"
        assert proof["lookup_url"] == f"http://localhost:3000/verify/degree/{proof['short_id']}"
        assert proof["qr_svg"].startswith("<svg") and len(proof["verify_url"]) < 400
        assert b64json(proof["jws"].split(".")[1]) == {
            "v": 1,
            "cid": proof["short_id"],
            "n": "Meera Kulkarni",
            "p": "B.Tech CS & Engg.",
            "i": "ABC College of Engg.",
            "u": "MSTU",
            "y": 2026,
            "a": "0401",
        }
        again = await university.post(f"/university/degrees/{meera}/issue")
        assert again.status_code == 200
        assert again.json()["degree"]["short_id"] == proof["short_id"]

        # it is in the graduate's wallet, without a holder binding
        async with session_factory()() as session:
            student_id = (await session.get(Enrolment, meera)).student_id
        wallet = (await admin.get("/credentials", params={"student_id": str(student_id)})).json()
        [card] = wallet["items"]
        assert card["kind"] == "DEGREE" and card["holder_bound"] is False
        assert card["university_name"] == "Maharashtra State Technical University"
        assert (await student.get(f"/credentials/{card['id']}")).status_code == 404

        by_qr = (await anyone.get(f"/verify/d/{proof['jws']}")).json()
        by_id = (await anyone.get(f"/verify/degree/{proof['short_id'].lower()}")).json()
        assert by_qr["result"] == by_id["result"] == "VALID"
        assert (by_qr["method"], by_id["method"]) == ("signature", "register_lookup")
        assert by_qr["kind"] == by_id["kind"] == "DEGREE"
        assert by_qr["holder_bound"] is by_id["holder_bound"] is False
        assert by_qr["expires_at"] is None and by_id["expires_at"] is None
        assert by_qr["university_name"] == by_id["university_name"]
        assert by_qr["issued_at"] == by_id["issued_at"] == card["issued_at"]
        qr_fields = {d["key"]: d["value"] for d in by_qr["disclosed"]}
        id_fields = {d["key"]: d["value"] for d in by_id["disclosed"]}
        assert (
            list(qr_fields)
            == list(id_fields)
            == [
                "proof_id",
                "name",
                "programme",
                "institution",
                "university",
                "year_of_award",
                "apaar_masked",
            ]
        )
        for same in ("proof_id", "name", "university", "year_of_award", "apaar_masked"):
            assert qr_fields[same] == id_fields[same]
        assert qr_fields["apaar_masked"] == "XXXX XXXX 0401"
        assert qr_fields["university"] == "Maharashtra State Technical University (MSTU)"
        assert (qr_fields["programme"], id_fields["programme"]) == (
            "B.Tech CS & Engg.",
            "B.Tech Computer Science and Engineering",
        )
        assert by_qr["institution_name"] == "ABC College of Engg."
        assert by_id["institution_name"] == "ABC College of Engineering"

        pdf = await university.get(f"/university/degrees/{meera}/insert.pdf")
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.headers["content-disposition"] == (
            f'attachment; filename="degree-insert-{proof["short_id"]}.pdf"'
        )
        text = _pdf_text(pdf.content)
        assert "(APAAR XXXX XXXX 0401)" in text and f"(Proof id {proof['short_id']})" in text
        assert "202500000401" not in text

        # a changed QR does not verify; an unknown id is not found
        header, payload, signature = proof["jws"].split(".")
        forged = ".".join([header, payload[:-2] + "AA", signature])
        assert (await anyone.get(f"/verify/d/{forged}")).json()["result"] == "INVALID"
        assert (await anyone.get("/verify/d/not-a-jws")).json()["result"] == "INVALID"
        for unknown in ("ZZZZZZZZ", "short"):
            missing = await anyone.get(f"/verify/degree/{unknown}")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "PRESENTATION_NOT_FOUND"

        revoked = await admin.post(
            f"/credentials/{card['id']}/revoke", json={"reason": "Degree withdrawn by MSTU."}
        )
        assert revoked.status_code == 200
        after_qr = (await anyone.get(f"/verify/d/{proof['jws']}")).json()
        after_id = (await anyone.get(f"/verify/degree/{proof['short_id']}")).json()
        assert after_qr["result"] == after_id["result"] == "REVOKED"
        assert after_qr["disclosed"] == after_id["disclosed"] == []
        assert after_qr["revoked_at"] == after_id["revoked_at"] is not None
        blocked = await university.get(f"/university/degrees/{meera}/insert.pdf")
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "CREDENTIAL_REVOKED"
        listed = (await university.get("/university/graduates", params={"q": "Meera"})).json()
        assert listed["items"][0]["degree"]["status"] == "REVOKED"
        reissued = await university.post(f"/university/degrees/{meera}/issue")
        assert reissued.status_code == 201
        assert reissued.json()["degree"]["short_id"] != proof["short_id"]
        assert (await university.get(f"/university/degrees/{meera}/insert.pdf")).status_code == 200

    async with session_factory()() as session:
        entries = (await session.execute(select(AuditLog).order_by(AuditLog.seq))).scalars().all()
    vias = [(e.entity_type, (e.after or {}).get("via")) for e in entries if e.after]
    assert ("student", "degree-print") in vias
    assert ("credential", "degree-qr") in vias and ("credential", "degree-lookup") in vias
    creates = [e for e in entries if e.entity_type == "credential" and e.action == "CREATE"]
    assert len(creates) == 2 and all(e.actor_id is not None for e in creates)


async def test_a_provisional_graduate_and_a_shared_degree(world):
    gauri = await _graduate("Gauri Sathe")
    async with signed_in("admin@aicte.demo") as admin, public() as anyone:
        body = (await admin.post(f"/university/degrees/{gauri}/issue")).json()
        assert body["student"]["id_kind"] == "PROVISIONAL"
        assert body["student"]["id_masked"] == "PRV-XXXXKN7A"
        proof = body["degree"]
        assert b64json(proof["jws"].split(".")[1])["a"] == "PRV-XXXXKN7A"
        by_qr = (await anyone.get(f"/verify/d/{proof['jws']}")).json()
        by_id = (await anyone.get(f"/verify/degree/{proof['short_id']}")).json()
        for result in (by_qr, by_id):
            fields = {d["key"]: d["value"] for d in result["disclosed"]}
            assert fields["provisional_id"] == "PRV-XXXXKN7A" and "apaar_masked" not in fields
        pdf = await admin.get(f"/university/degrees/{gauri}/insert.pdf")
        assert "(Provisional id PRV-XXXXKN7A)" in _pdf_text(pdf.content)
        assert "GQ4DKN7A" not in _pdf_text(pdf.content)
