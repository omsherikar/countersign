"""Signals end to end: a run finds the planted ring and colleges, changes nothing about any
record, case or row, and only officers see the result; an officer's case is what moves a
record to Under review (D45, R5, API_CONTRACT §A4.19)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.core.errors import ApiError
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import AuditAction, RecordStatus, SignalStatus, SignalType
from app.models.signal import Signal
from app.models.student import Enrolment
from app.models.verification import CaseAction, Check, Flag
from app.signals import service
from tests.signals.conftest import RING_COLLEGES, SHARE_COLLEGE, SPIKE_COLLEGE, YEAR

RING_SUMMARY = "40 students across 3 colleges share 4 mobile numbers and 4 addresses."


async def _snapshot() -> tuple:
    async with session_factory()() as session:
        statuses = sorted(
            (str(i), s.value, r)
            for i, s, r in (
                await session.execute(
                    select(Enrolment.id, Enrolment.record_status, Enrolment.status_reason)
                )
            ).all()
        )
        counts = [
            (await session.execute(select(func.count()).select_from(t))).scalar_one()
            for t in (Flag, Check, CaseAction)
        ]
    return statuses, counts


async def _ring(session) -> Signal:
    return (
        await session.execute(select(Signal).where(Signal.type == SignalType.GHOST_RING))
    ).scalar_one()


async def _run(client) -> dict:
    response = await client.post("/signals/run", json={"academic_year": YEAR})
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_run_finds_the_ring_and_changes_no_record_case_or_row(ring_world, clients):
    before = await _snapshot()
    result = await _run(clients["admin"])
    assert result["rings"] == 1 and result["created"] == result["rings"] + result["anomalies"]
    assert result["model"]["name"] == "IsolationForest"
    assert result["model"]["institutions"] == 40 and result["model"]["contamination"] == 0.05
    assert await _snapshot() == before  # R5: nothing but the signals table moved

    page = (await clients["admin"].get("/signals", params={"type": "GHOST_RING"})).json()
    [row] = page["items"]
    assert row["summary"] == RING_SUMMARY
    assert (row["member_count"], row["members_hidden"], row["institutions_hidden"]) == (40, 0, 0)
    assert [i["name"] for i in row["institutions"]] == [
        "Signal College 01",
        "Signal College 02",
        "Signal College 21",
    ]
    assert row["status"] == "NEW" and row["score"] is None and row["cases"] == []
    assert row["rule"].startswith("Rule: students linked by a shared mobile number")

    detail = (await clients["admin"].get(f"/signals/{row['id']}")).json()
    assert {e.id for e in ring_world.ring} == {
        uuid.UUID(m["enrolment_id"]) for m in detail["members"]
    }
    assert detail["shared"][0] == {"kind": "MOBILE", "masked": "XXXXXX0000", "students": 10}
    assert [s["kind"] for s in detail["shared"]] == ["MOBILE"] * 4 + ["ADDRESS"] * 4
    labels = [f["label"] for f in detail["facts"]]
    assert labels == [
        "Students",
        "Colleges",
        "Shared mobile numbers",
        "Shared addresses",
        "Members",
    ]
    assert all(m["record_status"] == "AWAITING_EVIDENCE" for m in detail["members"])
    assert detail["features"] == [] and detail["dismissal"] is None
    # no student name and no full id in what the signal stores
    async with session_factory()() as session:
        signal = await _ring(session)
        stored = f"{signal.summary} {signal.facts}"
        reads = (
            await session.execute(
                select(func.count()).where(
                    AuditLog.action == AuditAction.READ, AuditLog.entity_type == "student"
                )
            )
        ).scalar_one()
    assert "Signal Student" not in stored and reads >= 40

    again = await _run(clients["admin"])
    assert (again["created"], again["updated"]) == (0, 0)


async def test_planted_colleges_are_anomaly_signals_with_their_features(anomaly_world):
    async with session_factory()() as session:
        result = await service.run(session, YEAR)
        await session.commit()
        signals = (
            (await session.execute(select(Signal).where(Signal.type == SignalType.ANOMALY)))
            .scalars()
            .all()
        )
    spike = anomaly_world.college(SPIKE_COLLEGE)
    share = anomaly_world.college(SHARE_COLLEGE)
    assert result["rings"] == 0
    assert {s.institution_ids[0] for s in signals} == {spike.id, share.id}
    by_college = {s.institution_ids[0]: s for s in signals}
    growth = by_college[spike.id]
    standing = {f["name"] for f in growth.facts["features"] if f["stands_out"]}
    assert "admission_growth" in standing
    assert growth.summary.startswith(f"{spike.name} stands out from 39 similar colleges in {YEAR}")
    assert "admission growth on last year" in growth.summary
    assert growth.rule == (
        "Model: Isolation Forest, contamination 5%, trained on this year's 40 colleges."
    )
    assert growth.score is not None and growth.enrolment_ids == []
    shares = {f["name"] for f in by_college[share.id].facts["features"] if f["stands_out"]}
    assert shares >= {"nri_share", "management_share"}
    assert [f["label"] for f in growth.facts["items"]][0] == "Admission growth on last year"


async def test_only_officers_see_signals_and_regions_see_the_rest_counted(ring_world, clients):
    await _run(clients["admin"])
    async with session_factory()() as session:
        ring_id = (await _ring(session)).id
    for key in ("registrar", "university"):
        c = clients[key]
        assert (await c.get("/signals")).status_code == 403
        assert (await c.get(f"/signals/{ring_id}")).status_code == 403
        assert (await c.post("/signals/run", json={"academic_year": YEAR})).status_code == 403
        body = {"note": "Look at this."}
        assert (await c.post(f"/signals/{ring_id}/open-case", json=body)).status_code == 403
        assert (await c.post(f"/signals/{ring_id}/dismiss", json=body)).status_code == 403
    assert (
        await clients["ro.west"].post("/signals/run", json={"academic_year": YEAR})
    ).status_code == 403

    west = (await clients["ro.west"].get(f"/signals/{ring_id}")).json()
    assert (west["members_hidden"], west["institutions_hidden"]) == (13, 1)
    assert len(west["members"]) == 27
    assert {m["institution"]["name"] for m in west["members"]} == {
        "Signal College 01",
        "Signal College 02",
    }
    facts = {f["label"]: f["value"] for f in west["facts"]}
    assert facts["Colleges"] == "Signal College 01; Signal College 02; 1 college in other regions"
    assert facts["Members"].endswith("; 13 records in other regions")
    assert "Signal College 21" not in str(west)

    south = (await clients["ro.south"].get(f"/signals/{ring_id}")).json()
    assert (south["members_hidden"], south["institutions_hidden"]) == (27, 2)
    listed = (await clients["ro.south"].get("/signals", params={"type": "GHOST_RING"})).json()
    assert listed["total"] == 1 and listed["items"][0]["members_hidden"] == 27

    # a signal only about a western college is not there for the southern office
    async with session_factory()() as session:
        only_west = Signal(
            type=SignalType.ANOMALY,
            academic_year=YEAR,
            institution_ids=[ring_world.college(5).id],
            enrolment_ids=[],
            summary="Signal College 06 stands out.",
            facts={"items": [], "features": [], "cases": []},
            rule="Model: Isolation Forest.",
            dedupe_key=f"ANOMALY:{YEAR}:test-west",
        )
        session.add(only_west)
        await session.commit()
    missing = await clients["ro.south"].get(f"/signals/{only_west.id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "Signal not found."
    assert (await clients["ro.west"].get(f"/signals/{only_west.id}")).status_code == 200
    by_state = (await clients["admin"].get("/signals", params={"state": "KA"})).json()
    assert [i["type"] for i in by_state["items"]].count("GHOST_RING") == 1
    assert only_west.id not in {uuid.UUID(i["id"]) for i in by_state["items"]}


async def test_open_case_puts_the_named_records_under_review(ring_world, clients):
    await _run(clients["admin"])
    async with session_factory()() as session:
        ring_id = (await _ring(session)).id
    first, second, _ = (ring_world.college(i) for i in RING_COLLEGES)

    missing_college = await clients["admin"].post(
        f"/signals/{ring_id}/open-case", json={"note": "Ask for admission records."}
    )
    assert missing_college.status_code == 422
    response = await clients["ro.west"].post(
        f"/signals/{ring_id}/open-case",
        json={"institution_ids": [str(ring_world.college(20).id)], "note": "Out of region."},
    )
    assert response.status_code == 422  # the South college is not the western office's

    response = await clients["ro.west"].post(
        f"/signals/{ring_id}/open-case",
        json={"institution_ids": [str(first.id)], "note": "Shared mobiles; ask for records."},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    [case] = body["cases"]
    assert (case["type"], case["severity"], case["status"]) == ("GHOST_RING", "HIGH", "OPEN")
    assert case["institution"]["id"] == str(first.id) and case["related_count"] == 14
    assert case["signal_id"] == str(ring_id)  # the case list reads it from the dedupe key
    assert body["signal"]["status"] == "CASE_OPENED"
    assert body["signal"]["cases"] == [
        {"id": case["id"], "institution_id": str(first.id), "status": "OPEN"}
    ]
    statuses = {
        m["enrolment_id"]: (m["institution"]["id"], m["record_status"])
        for m in body["signal"]["members"]
    }
    assert {s for i, s in statuses.values() if i == str(first.id)} == {"UNDER_REVIEW"}
    assert {s for i, s in statuses.values() if i == str(second.id)} == {"AWAITING_EVIDENCE"}

    async with session_factory()() as session:
        flag = await session.get(Flag, uuid.UUID(case["id"]))
        assert flag.dedupe_key == f"GHOST_RING:{ring_id}:{first.id}"
        assert flag.evidence["signal_id"] == str(ring_id)
        assert flag.evidence["summary"] == (
            "40 students across 3 institutions share 8 contact details."
        )
        assert flag.evidence["rule_source"].startswith("Rule: students linked")
        officer_only = [
            f["label"] for f in flag.evidence["facts"] if f.get("audience") == "OFFICER"
        ]
        assert officer_only == ["Colleges", "Signal"]
        [note] = (
            (await session.execute(select(CaseAction).where(CaseAction.flag_id == flag.id)))
            .scalars()
            .all()
        )
        assert note.action.value == "NOTE" and note.note == "Shared mobiles; ask for records."
        signal = await session.get(Signal, ring_id)
        assert signal.note == "Shared mobiles; ask for records." and signal.case_flag_id == flag.id
        ring_ids = {e.id for e in ring_world.ring}
        moved = (
            await session.execute(
                select(func.count()).where(
                    Enrolment.record_status == RecordStatus.UNDER_REVIEW,
                    Enrolment.id.not_in(ring_ids),
                )
            )
        ).scalar_one()
        assert moved == 0

    # the registrar reads its own case without the other colleges or the signal line
    registrar_case = (await clients["registrar"].get(f"/flags/{case['id']}")).json()
    labels = [f["label"] for f in registrar_case["evidence"]["facts"]]
    assert "Colleges" not in labels and "Signal" not in labels

    # asking again for the same college returns the same case; a second college gets its own
    again = await clients["admin"].post(
        f"/signals/{ring_id}/open-case",
        json={"institution_ids": [str(first.id), str(second.id)], "note": "Both colleges."},
    )
    assert again.status_code == 201
    ids = [c["id"] for c in again.json()["cases"]]
    assert ids[0] == case["id"] and len(set(ids)) == 2
    assert len(again.json()["signal"]["cases"]) == 2
    dismissed = await clients["admin"].post(f"/signals/{ring_id}/dismiss", json={"note": "No."})
    assert dismissed.status_code == 409
    assert dismissed.json()["error"] == {
        "code": "SIGNAL_ALREADY_HANDLED",
        "message": "This signal already has a case or was dismissed.",
        "details": {"status": "CASE_OPENED"},
    }


async def test_dismiss_keeps_the_signal_with_its_note_and_changes_nothing(ring_world, clients):
    await _run(clients["admin"])
    async with session_factory()() as session:
        ring_id = (await _ring(session)).id
    before = await _snapshot()
    blank = await clients["admin"].post(f"/signals/{ring_id}/dismiss", json={"note": "  "})
    assert blank.status_code == 422
    response = await clients["admin"].post(
        f"/signals/{ring_id}/dismiss", json={"note": "Family members at one address."}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "DISMISSED"
    assert body["dismissal"]["note"] == "Family members at one address."
    assert body["dismissal"]["by"]["id"] == str(ring_world.users["admin"].id)
    assert await _snapshot() == before

    async with session_factory()() as session:
        entries = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "signal", AuditLog.entity_id == ring_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert any(e.after == {"status": "DISMISSED"} for e in entries)
    assert "Family members" not in str([(e.before, e.after) for e in entries])

    for path, body in (("dismiss", {"note": "Again."}), ("open-case", {"note": "Now a case."})):
        response = await clients["admin"].post(f"/signals/{ring_id}/{path}", json=body)
        assert response.status_code == 409
    rerun = await _run(clients["admin"])
    assert rerun["created"] == 0
    async with session_factory()() as session:
        assert (await session.get(Signal, ring_id)).status is SignalStatus.DISMISSED
    missing = await clients["admin"].get(f"/signals/{uuid.uuid4()}")
    assert missing.status_code == 404


async def test_list_filters_and_sorts(ring_world, clients):
    await _run(clients["admin"])
    admin = clients["admin"]
    everything = (await admin.get("/signals")).json()
    by_score = (await admin.get("/signals", params={"sort": "score"})).json()
    assert everything["total"] == by_score["total"] >= 1
    types = [i["type"] for i in by_score["items"]]
    assert types == sorted(types, key=lambda t: t != "ANOMALY")
    scores = [i["score"] for i in by_score["items"] if i["type"] == "ANOMALY"]
    assert scores == sorted(scores)
    first = ring_world.college(RING_COLLEGES[0])
    touching = (await admin.get("/signals", params={"institution_id": str(first.id)})).json()
    assert "GHOST_RING" in [i["type"] for i in touching["items"]]
    assert (await admin.get("/signals", params={"status": "DISMISSED"})).json()["total"] == 0
    assert (await admin.get("/signals", params={"academic_year": "2025-26"})).json()["total"] == 0


async def test_another_officer_acting_at_the_same_moment_gets_409(ring_world, clients):
    await _run(clients["admin"])
    other = ring_world.users["admin.two"]
    async with session_factory()() as holder, session_factory()() as session:
        ring_id = (await _ring(holder)).id
        await holder.execute(select(Signal).where(Signal.id == ring_id).with_for_update())
        try:
            await service.dismiss(
                session, await session.get(type(other), other.id), ring_id, note="Mine."
            )
        except ApiError as exc:
            assert (exc.status_code, exc.code) == (409, "SIGNAL_ALREADY_HANDLED")
        else:
            raise AssertionError("expected 409")
        await holder.rollback()
