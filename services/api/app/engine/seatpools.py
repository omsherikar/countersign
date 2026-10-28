"""Seat pools and seats for one approval, straight from rules.yaml (DECISIONS D10).

REGULAR = approved intake minus the NRI carve-out (NRI sits within intake).
TFW, LATERAL and INTERNATIONAL are supernumerary; INTERNATIONAL takes the slab that
matches the programme's discipline and level, and one third of its seats carry
reserved_for = CIWG. Percentages round half up to whole seats.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.core.rules import Rules, get_rules
from app.models.enums import SeatStatus, SeatType
from app.models.institution import Approval, Programme
from app.models.seat import Seat, SeatPool

SEAT_LETTER = {
    SeatType.REGULAR: "R",
    SeatType.NRI: "N",
    SeatType.TFW: "T",
    SeatType.LATERAL: "L",
    SeatType.INTERNATIONAL: "I",
}

CIWG = "CIWG"
INTERNATIONAL_RESERVED_LABEL = "FN_OCI_PIO_CIWG"


def round_half_up(value: Decimal | float, share: float | Decimal) -> int:
    seats = Decimal(str(value)) * Decimal(str(share))
    return max(0, int(seats.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def pool_capacities(
    approved_intake: int, discipline: str, level: str, rules: Rules | None = None
) -> dict[SeatType, tuple[int, bool, str]]:
    """{seat_type: (capacity, is_supernumerary, rule_source)} for an approval."""
    rules = rules or get_rules()
    sp = rules.seat_pools
    nri = round_half_up(approved_intake, sp.NRI.share)
    regular = max(0, round_half_up(approved_intake, sp.REGULAR.share) - nri)
    out: dict[SeatType, tuple[int, bool, str]] = {
        SeatType.REGULAR: (
            regular,
            sp.REGULAR.supernumerary,
            f"{sp.REGULAR.source}; minus NRI carve-out ({sp.NRI.source})",
        ),
        SeatType.NRI: (nri, sp.NRI.supernumerary, sp.NRI.source),
        SeatType.TFW: (
            round_half_up(approved_intake, sp.TFW.share),
            sp.TFW.supernumerary,
            sp.TFW.source,
        ),
        SeatType.LATERAL: (
            round_half_up(approved_intake, sp.LATERAL.share),
            sp.LATERAL.supernumerary,
            sp.LATERAL.source,
        ),
    }
    slab = sp.INTERNATIONAL.slab_for(discipline, level)
    if slab is None:
        out[SeatType.INTERNATIONAL] = (
            0,
            sp.INTERNATIONAL.supernumerary,
            f"no international slab for {discipline}/{level}",
        )
    else:
        out[SeatType.INTERNATIONAL] = (
            round_half_up(approved_intake, slab.share),
            sp.INTERNATIONAL.supernumerary,
            slab.source,
        )
    return out


def seat_code(programme_code: str, seat_type: SeatType, number: int) -> str:
    return f"{programme_code}-{SEAT_LETTER[seat_type]}-{number:03d}"


def build_for_approval(
    approval: Approval, programme: Programme | None = None, rules: Rules | None = None
) -> list[SeatPool]:
    """Pools (with their seats attached) for one approval. Nothing is flushed here."""
    rules = rules or get_rules()
    programme = programme or approval.programme
    capacities = pool_capacities(
        approval.approved_intake, programme.discipline.value, programme.level.value, rules
    )
    ciwg_fraction = rules.seat_pools.INTERNATIONAL.ciwg_reserved_fraction
    pools: list[SeatPool] = []
    for seat_type in SeatType:
        capacity, supernumerary, source = capacities[seat_type]
        pool = SeatPool(
            approval=approval,
            seat_type=seat_type,
            capacity=capacity,
            is_supernumerary=supernumerary,
            rule_source=source,
        )
        ciwg_count = (
            round_half_up(capacity, ciwg_fraction) if seat_type is SeatType.INTERNATIONAL else 0
        )
        for number in range(1, capacity + 1):
            pool.seats.append(
                Seat(
                    seat_code=seat_code(programme.code, seat_type, number),
                    status=SeatStatus.FREE,
                    reserved_for=CIWG if number <= ciwg_count else None,
                )
            )
        pools.append(pool)
    return pools
