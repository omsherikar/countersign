from app.core.rules import get_rules
from app.engine.seatpools import build_for_approval, pool_capacities, round_half_up
from app.models.enums import Discipline, ProgrammeLevel, SeatType, Shift
from app.models.institution import Approval, Programme


def _programme(code: str, level: ProgrammeLevel, discipline: Discipline) -> Programme:
    return Programme(
        code=code,
        name=code,
        level=level,
        discipline=discipline,
        shift=Shift.FIRST,
        duration_years=4,
    )


def test_rules_load_with_sources():
    rules = get_rules()
    assert rules.seat_pools.NRI.share == 0.05
    assert "2.8(b)" in rules.seat_pools.NRI.source
    assert rules.seat_pools.INTERNATIONAL.slab_for("ENGINEERING", "UG").share == 0.15
    assert rules.seat_pools.INTERNATIONAL.slab_for("ENGINEERING", "PG").share == 0.25
    assert rules.seat_pools.INTERNATIONAL.slab_for("MANAGEMENT", "PG").share == 0.25
    assert rules.seat_pools.INTERNATIONAL.slab_for("PHARMACY", "UG") is None
    assert rules.cutoff_dates["2026-27"] == "2026-09-15"
    assert rules.admission_routes["TFW"].pool == "TFW"


def test_round_half_up():
    assert round_half_up(120, 0.05) == 6
    assert round_half_up(30, 0.05) == 2  # 1.5 rounds up
    assert round_half_up(18, 0.3333) == 6
    assert round_half_up(0, 0.5) == 0


def test_engineering_ug_120():
    caps = pool_capacities(120, "ENGINEERING", "UG")
    assert {k: v[0] for k, v in caps.items()} == {
        SeatType.REGULAR: 114,
        SeatType.NRI: 6,
        SeatType.TFW: 6,
        SeatType.LATERAL: 12,
        SeatType.INTERNATIONAL: 18,
    }
    assert caps[SeatType.REGULAR][1] is False
    assert caps[SeatType.NRI][1] is False
    assert caps[SeatType.TFW][1] is True
    assert caps[SeatType.LATERAL][1] is True
    assert caps[SeatType.INTERNATIONAL][1] is True
    assert "6.42" in caps[SeatType.TFW][2]
    assert "6.13" in caps[SeatType.LATERAL][2]


def test_mba_60_gets_15_international():
    caps = pool_capacities(60, "MANAGEMENT", "PG")
    assert caps[SeatType.INTERNATIONAL][0] == 15
    assert caps[SeatType.REGULAR][0] == 57
    assert caps[SeatType.NRI][0] == 3


def test_build_for_approval_seats_and_ciwg():
    programme = _programme("CSE", ProgrammeLevel.UG, Discipline.ENGINEERING)
    approval = Approval(academic_year="2026-27", approved_intake=120, programme=programme)
    pools = build_for_approval(approval, programme)
    by_type = {p.seat_type: p for p in pools}
    assert [p.seat_type for p in pools] == list(SeatType)
    assert all(len(p.seats) == p.capacity for p in pools)
    assert by_type[SeatType.REGULAR].seats[86].seat_code == "CSE-R-087"
    assert by_type[SeatType.NRI].seats[0].seat_code == "CSE-N-001"
    assert by_type[SeatType.INTERNATIONAL].seats[-1].seat_code == "CSE-I-018"
    ciwg = [s for s in by_type[SeatType.INTERNATIONAL].seats if s.reserved_for == "CIWG"]
    assert len(ciwg) == 6
    assert all(
        s.reserved_for is None
        for p in pools
        if p.seat_type != SeatType.INTERNATIONAL
        for s in p.seats
    )
    assert all(p.approval is approval for p in pools)


def test_pharmacy_has_no_international_slab():
    programme = _programme("BPH", ProgrammeLevel.UG, Discipline.PHARMACY)
    approval = Approval(academic_year="2026-27", approved_intake=100, programme=programme)
    pools = {p.seat_type: p for p in build_for_approval(approval, programme)}
    assert pools[SeatType.INTERNATIONAL].capacity == 0
    assert pools[SeatType.INTERNATIONAL].seats == []
    assert pools[SeatType.REGULAR].capacity == 95
