"""Duplicates (ENGINES.md section 9, D19): within an institution, same student elsewhere,
and the same person without an APAAR at two institutions."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.engine.duplicates import detect_duplicates
from app.models.enums import EnrolmentStatus, FlagType, ProgrammeMode, Severity
from app.models.verification import Flag

DOB = date(2007, 3, 21)
MOBILE = "9876504521"


async def _flags(session) -> list[Flag]:
    return list((await session.execute(select(Flag).order_by(Flag.dedupe_key))).scalars().all())


async def test_r_k_sharma_is_a_duplicate_of_ravi_kumar_sharma(world, session) -> None:
    abc = await world.institution("ABC College of Engineering", "1-ABC-0001")
    cse = await world.programme(abc, "CSE")
    batch = await world.batch(abc, "1-ABC-0001_2026-27.csv")
    ravi = await world.enrol(
        await world.student("Ravi Kumar Sharma", DOB, apaar="123456784417", mobile=MOBILE),
        cse,
        batch=batch,
        row_no=2,
    )
    rk = await world.enrol(
        await world.student("R. K. Sharma", DOB, mobile=MOBILE), cse, batch=batch, row_no=133
    )
    result = await detect_duplicates(session, abc.id, "2026-27", [ravi.id, rk.id])
    assert (result.within, result.cross, result.dual) == (1, 0, 0)
    assert result.flags.created == 1
    [flag] = await _flags(session)
    assert flag.type is FlagType.DUPLICATE_WITHIN_UPLOAD
    assert flag.severity is Severity.MEDIUM
    assert flag.enrolment_id == rk.id  # the record without an APAAR is the suspected copy
    assert flag.programme_id == cse.id
    assert set(flag.related_enrolment_ids) == {ravi.id, rk.id}
    low, high = sorted([str(ravi.id), str(rk.id)])
    assert flag.dedupe_key == f"DUPLICATE_WITHIN_UPLOAD:{low}:{high}"
    assert flag.evidence["summary"] == (
        "Rows 2 and 133 of 1-ABC-0001_2026-27.csv describe the same student."
    )
    facts = {f["label"]: f["value"] for f in flag.evidence["facts"]}
    assert facts["Match on"].startswith("Name (") and facts["Match on"].endswith(
        "date of birth and mobile"
    )
    assert facts["Row A"] == "1-ABC-0001_2026-27.csv, row 2"
    assert facts["Row B"] == "1-ABC-0001_2026-27.csv, row 133"
    assert facts["Names as uploaded"] == "Ravi Kumar Sharma / R. K. Sharma"

    again = await detect_duplicates(session, abc.id, "2026-27", [rk.id])
    assert again.within == 1
    assert (again.flags.created, again.flags.updated, again.flags.unchanged) == (0, 0, 1)
    assert len(await _flags(session)) == 1


async def test_mobile_alone_links_two_records_in_one_block(world, session) -> None:
    abc = await world.institution()
    cse = await world.programme(abc)
    a = await world.enrol(await world.student("Rahul Sharma", DOB, mobile=MOBILE), cse)
    b = await world.enrol(await world.student("Rohan Sharma", DOB, mobile=MOBILE), cse)
    await detect_duplicates(session, abc.id, "2026-27", [a.id, b.id])
    [flag] = await _flags(session)
    facts = {f["label"]: f["value"] for f in flag.evidence["facts"]}
    assert facts["Match on"] == "Date of birth and mobile"


async def test_two_different_apaars_are_two_people(world, session) -> None:
    abc = await world.institution()
    cse = await world.programme(abc)
    a = await world.enrol(
        await world.student("Ravi Kumar Sharma", DOB, apaar="123456780001", mobile=MOBILE), cse
    )
    b = await world.enrol(
        await world.student("Ravi Kumar Sharma", DOB, apaar="123456780002", mobile=MOBILE), cse
    )
    result = await detect_duplicates(session, abc.id, "2026-27", [a.id, b.id])
    assert result.within == 0
    assert await _flags(session) == []


async def test_married_name_change_is_not_blocked_together(world, session) -> None:
    abc = await world.institution()
    cse = await world.programme(abc)
    a = await world.enrol(await world.student("Priya Sharma", DOB, mobile=MOBILE), cse)
    b = await world.enrol(await world.student("Priya Verma", DOB, mobile=MOBILE), cse)
    result = await detect_duplicates(session, abc.id, "2026-27", [a.id, b.id])
    assert result.within == 0


async def _two_colleges(world, mode_b: ProgrammeMode):
    abc = await world.institution("ABC College of Engineering", "1-ABC-0001")
    xyz = await world.institution(
        "XYZ Institute of Technology",
        "1-XYZ-0002",
        state="TN",
        state_name="Tamil Nadu",
        region="SOUTH",
    )
    cse = await world.programme(abc, "CSE")
    bca = await world.programme(xyz, "BCA", name="Bachelor of Computer Applications", mode=mode_b)
    return abc, xyz, cse, bca


async def test_same_apaar_physical_and_odl_is_allowed_dual_enrolment(world, session) -> None:
    abc, xyz, cse, bca = await _two_colleges(world, ProgrammeMode.ODL)
    stu = await world.student("Ravi Kumar Sharma", DOB, apaar="123456784417")
    a = await world.enrol(stu, cse)
    b = await world.enrol(stu, bca)
    result = await detect_duplicates(session, xyz.id, "2026-27", [b.id])
    assert (result.dual, result.cross) == (1, 0)
    flags = await _flags(session)
    assert len(flags) == 2
    assert {f.type for f in flags} == {FlagType.DUAL_ENROLMENT_ALLOWED}
    assert {f.severity for f in flags} == {Severity.LOW}
    assert {(f.institution_id, f.enrolment_id) for f in flags} == {(abc.id, a.id), (xyz.id, b.id)}
    own = next(f for f in flags if f.institution_id == abc.id)
    facts = {(f["label"], f.get("audience")): f["value"] for f in own.evidence["facts"]}
    assert facts[("Enrolment B mode", "INSTITUTION")] == (
        "Another institution in Tamil Nadu: Bachelor of Computer Applications, "
        "open and distance learning"
    )
    assert facts[("Enrolment A mode", None)].endswith(", physical")


async def test_same_apaar_at_two_physical_programmes_is_high(world, session) -> None:
    abc, xyz, cse, it = await _two_colleges(world, ProgrammeMode.PHYSICAL)
    stu = await world.student("Ravi Kumar Sharma", DOB, apaar="123456784417")
    a = await world.enrol(stu, cse)
    b = await world.enrol(stu, it)
    result = await detect_duplicates(session, abc.id, "2026-27", [a.id])
    assert (result.dual, result.cross) == (0, 1)
    flags = await _flags(session)
    assert {f.type for f in flags} == {FlagType.DUPLICATE_CROSS_INSTITUTION}
    assert {f.severity for f in flags} == {Severity.HIGH}
    mine = next(f for f in flags if f.institution_id == abc.id)
    assert mine.evidence["summary"] == (
        "The same student appears as active at ABC College of Engineering and "
        "XYZ Institute of Technology (2026-27)."
    )
    assert mine.evidence["summary_for_institution"] == (
        "The same student appears as active here and at another institution in Tamil Nadu "
        "(2026-27)."
    )
    match = next(f for f in mine.evidence["facts"] if f["label"] == "Match on")
    assert match["value"] == "Same APAAR"
    low, high = sorted([str(a.id), str(b.id)])
    assert {f.dedupe_key for f in flags} == {
        f"DUPLICATE_CROSS_INSTITUTION:{low}:{high}:{abc.id}",
        f"DUPLICATE_CROSS_INSTITUTION:{low}:{high}:{xyz.id}",
    }


async def test_no_apaar_across_institutions_needs_name_and_mobile(world, session) -> None:
    abc, xyz, cse, it = await _two_colleges(world, ProgrammeMode.PHYSICAL)
    a = await world.enrol(await world.student("Anil Kumar", DOB, mobile=MOBILE), cse)
    b = await world.enrol(await world.student("Anil Kumar", DOB, mobile=MOBILE), it)
    c = await world.enrol(await world.student("Anil Kumar", DOB, mobile="9000000001"), it)
    result = await detect_duplicates(session, abc.id, "2026-27", [a.id])
    assert result.cross == 1  # c shares the name but not the mobile
    flags = await _flags(session)
    assert {f.severity for f in flags} == {Severity.MEDIUM}
    assert {f.enrolment_id for f in flags} == {a.id, b.id}
    assert c.id not in {i for f in flags for i in f.related_enrolment_ids}
    match = next(f for f in flags[0].evidence["facts"] if f["label"] == "Match on")
    assert match["value"] == "Name (100 of 100), date of birth and mobile"


async def test_only_active_enrolments_of_the_year_take_part(world, session) -> None:
    abc, xyz, cse, it = await _two_colleges(world, ProgrammeMode.PHYSICAL)
    stu = await world.student("Ravi Kumar Sharma", DOB, apaar="123456784417")
    a = await world.enrol(stu, cse)
    await world.enrol(stu, it, status=EnrolmentStatus.TRANSFERRED)
    result = await detect_duplicates(session, abc.id, "2026-27", [a.id])
    assert (result.cross, result.dual) == (0, 0)
