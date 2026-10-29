"""Seat pools and seats for one approval, straight from rules.yaml (DECISIONS D10, D41).

REGULAR = approved intake minus the NRI carve-out (NRI sits within intake).
TFW, LATERAL and INTERNATIONAL are supernumerary; INTERNATIONAL takes the slab that
matches the programme's discipline and level, and one third of its seats carry
reserved_for = CIWG. Percentages round half up to whole seats.

A new approval version resizes the pools (`pool_changes`, `apply_resize`): a raised pool
gains FREE seats with the next numbers; a lowered one loses FREE seats, highest numbers
first, and a seat that ever had a holder stays as RELEASED (retired) so its history keeps
its code. The CIWG reservation is recomputed either way.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rules import Rules, get_rules
from app.models.enums import SeatStatus, SeatType
from app.models.institution import Approval, Programme
from app.models.seat import Seat, SeatEvent, SeatPool

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


# ------------------------------------------------------------ approval versions


@dataclass(frozen=True, slots=True)
class PoolResize:
    seat_type: SeatType
    old_capacity: int
    new_capacity: int
    assigned: int

    @property
    def below_assigned(self) -> bool:
        return self.new_capacity < self.assigned


def pool_changes(
    approval: Approval,
    new_intake: int,
    assigned: Mapping[SeatType, int],
    rules: Rules | None = None,
    *,
    programme: Programme | None = None,
    pools: Sequence[SeatPool] = (),
) -> list[PoolResize]:
    """Every pool whose capacity the new intake changes, with its assigned seats."""
    rules = rules or get_rules()
    programme = programme or approval.programme
    capacities = pool_capacities(
        new_intake, programme.discipline.value, programme.level.value, rules
    )
    current = {p.seat_type: p.capacity for p in pools}
    out = []
    for seat_type in SeatType:
        old = current.get(seat_type, 0)
        new = capacities[seat_type][0]
        if new != old:
            out.append(PoolResize(seat_type, old, new, assigned.get(seat_type, 0)))
    return out


_NUMBER = re.compile(r"-(\d+)$")


def _number(seat: Seat) -> int:
    match = _NUMBER.search(seat.seat_code)
    return int(match.group(1)) if match else 0


async def apply_resize(
    session: AsyncSession,
    approval: Approval,
    changes: Sequence[PoolResize],
    *,
    programme: Programme | None = None,
    rules: Rules | None = None,
) -> tuple[int, int]:
    """(seats added, seats removed) for the changed pools of one approval. Refuses nothing:
    the caller has checked that no pool falls below its assigned seats."""
    rules = rules or get_rules()
    programme = programme or await session.get(Programme, approval.programme_id)
    assert programme is not None
    ciwg_fraction = rules.seat_pools.INTERNATIONAL.ciwg_reserved_fraction
    by_type = {
        p.seat_type: p
        for p in (
            await session.execute(select(SeatPool).where(SeatPool.approval_id == approval.id))
        ).scalars()
    }
    added = removed = 0
    for change in changes:
        pool = by_type.get(change.seat_type)
        if pool is None:
            continue
        seats = list(
            (
                await session.execute(select(Seat).where(Seat.pool_id == pool.id).with_for_update())
            ).scalars()
        )
        live = [s for s in seats if s.status is not SeatStatus.RELEASED]
        if change.new_capacity > len(live):
            next_number = max((_number(s) for s in seats), default=0) + 1
            for n in range(change.new_capacity - len(live)):
                seat = Seat(
                    pool_id=pool.id,
                    seat_code=seat_code(programme.code, change.seat_type, next_number + n),
                    status=SeatStatus.FREE,
                )
                session.add(seat)
                live.append(seat)
                added += 1
        elif change.new_capacity < len(live):
            free = sorted(
                (s for s in live if s.status is SeatStatus.FREE), key=_number, reverse=True
            )
            for seat in free[: len(live) - change.new_capacity]:
                used = await session.scalar(select(exists().where(SeatEvent.seat_id == seat.id)))
                if used:
                    seat.status = SeatStatus.RELEASED  # retired: its history keeps the code
                    seat.reserved_for = None
                else:
                    await session.delete(seat)
                live.remove(seat)
                removed += 1
        pool.capacity = change.new_capacity
        if change.seat_type is SeatType.INTERNATIONAL:
            _reserve_ciwg(live, round_half_up(change.new_capacity, ciwg_fraction))
    await session.flush()
    return added, removed


def _reserve_ciwg(live: list[Seat], wanted: int) -> None:
    """One third of the live international seats stay reserved for CIWG students; only FREE
    seats change their reservation, lowest numbers reserved first."""
    reserved = [s for s in live if s.reserved_for == CIWG]
    free = sorted((s for s in live if s.status is SeatStatus.FREE), key=_number)
    if len(reserved) < wanted:
        for seat in [s for s in free if s.reserved_for is None][: wanted - len(reserved)]:
            seat.reserved_for = CIWG
    elif len(reserved) > wanted:
        spare = [s for s in reversed(free) if s.reserved_for == CIWG]
        for seat in spare[: len(reserved) - wanted]:
            seat.reserved_for = None
