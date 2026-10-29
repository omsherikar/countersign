"""Category eligibility (D41, API_CONTRACT §A4.4): the pure rule and the CIWG seats."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.rules import get_rules
from app.engine import eligibility
from app.engine.eligibility import EligibilityVerdict, check, is_ciwg
from app.engine.ledger import assign_seats
from app.models.enums import AdmissionRoute, SeatType
from app.models.seat import Seat

RULES = get_rules()


@pytest.mark.parametrize(
    ("seat_type", "nationality", "reported", "expected"),
    [
        (SeatType.INTERNATIONAL, "BD", {}, "FITS"),
        (SeatType.INTERNATIONAL, "IN", {"ciwg": True}, "FITS"),
        (SeatType.INTERNATIONAL, "IN", {}, "BREACH"),
        (SeatType.INTERNATIONAL, "IN", {"ciwg": False}, "BREACH"),
        (SeatType.NRI, "IN", {"nri_sponsored": True}, "FITS"),
        (SeatType.NRI, "IN", {}, "BREACH"),
        (SeatType.NRI, "IN", {"nri_sponsored": False}, "BREACH"),
        (SeatType.TFW, "IN", {"tfw_income_certified": True}, "FITS"),
        (SeatType.TFW, "IN", {"tfw_income_certified": False}, "BREACH"),
        (SeatType.TFW, "IN", {}, "NOT_REPORTED"),
        (SeatType.REGULAR, "IN", {"nri_sponsored": False, "ciwg": False}, "FITS"),
        (SeatType.LATERAL, "IN", {}, "FITS"),
    ],
)
def test_each_seat_type_checks_what_the_college_reported(
    seat_type, nationality, reported, expected
) -> None:
    assert check(seat_type, nationality, reported, RULES).state == expected


def test_a_breach_names_its_rule_words_and_clause() -> None:
    assert check(SeatType.NRI, "IN", {"nri_sponsored": None}, RULES) == EligibilityVerdict(
        "BREACH",
        "NRI_STATUS",
        "not marked for this category",
        "APH 2024-27 cl. 2.8(b)",
        "NRI or NRI-sponsored students",
    )
    international = check(SeatType.INTERNATIONAL, "IN", {}, RULES)
    assert (international.rule, international.clause) == (
        "INTERNATIONAL_CIWG",
        "APH 2024-27 cl. 2.9",
    )
    tfw = check(SeatType.TFW, "IN", {"tfw_income_certified": False}, RULES)
    assert (tfw.rule, tfw.reported_word, tfw.clause) == (
        "TFW_INCOME",
        "without a family income certificate",
        "APH 2024-27 cl. 6.42(d)",
    )


def test_only_true_and_false_are_markers() -> None:
    assert eligibility.markers({"ciwg": "yes", "nri_sponsored": True, "extra": 1}) == {
        "tfw_income_certified": None,
        "nri_sponsored": True,
        "ciwg": None,
    }


def test_ciwg_needs_the_international_route_an_indian_national_and_the_marker() -> None:
    marked = {"ciwg": True}
    assert is_ciwg(AdmissionRoute.INTERNATIONAL, "IN", marked)
    assert not is_ciwg(AdmissionRoute.INTERNATIONAL, "IN", {})
    assert not is_ciwg(AdmissionRoute.INTERNATIONAL, "AE", marked)
    assert not is_ciwg(AdmissionRoute.COUNSELLING, "IN", marked)


async def test_a_marked_ciwg_student_takes_a_reserved_seat_and_an_unmarked_one_does_not(
    world, session
) -> None:
    inst = await world.institution()
    cse = await world.programme(inst, "CSE", intakes={"2026-27": 20})  # 3 international, 1 CIWG
    unmarked = await world.enrol(
        await world.student("Unmarked Gulf Child", passport="Z9000002"),
        cse,
        route=AdmissionRoute.INTERNATIONAL,
        row_no=2,
    )
    marked = await world.enrol(
        await world.student("Marked Gulf Child", passport="Z9000003"),
        cse,
        route=AdmissionRoute.INTERNATIONAL,
        row_no=3,
        eligibility={"ciwg": True},
    )
    await assign_seats(session, [unmarked.id, marked.id], actor_id=None)
    seats = {
        s.enrolment_id: s.reserved_for
        for s in (await session.execute(select(Seat).where(Seat.enrolment_id.is_not(None))))
        .scalars()
        .all()
    }
    assert seats == {unmarked.id: None, marked.id: "CIWG"}
