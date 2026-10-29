"""Shared contact rings (D45, ENGINES §17.11).

One node per student, an edge between two students who share a mobile, an email or an
address (compared as the stored hashes, emails in lower case). A connected component of
`min_cross` or more students across `min_colleges` or more colleges, or of `min_single` or
more students in one college, is a ring. `find_rings` is pure; `load_members` reads the
ACTIVE enrolments of one academic year.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import networkx as nx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EnrolmentStatus
from app.models.student import Enrolment, Student

MOBILE, EMAIL, ADDRESS = "MOBILE", "EMAIL", "ADDRESS"
KIND_ORDER = {MOBILE: 0, EMAIL: 1, ADDRESS: 2}

# copy deck signal.rule.GHOST_RING, with the thresholds of rules.yaml
RULE = (
    "Rule: students linked by a shared mobile number, email or address form a group; a group "
    "of {min_cross} or more across {min_colleges} or more colleges, or of {min_single} or more "
    "in one college, is a signal."
)


@dataclass(frozen=True, slots=True)
class Member:
    enrolment_id: uuid.UUID
    student_id: uuid.UUID
    institution_id: uuid.UUID
    mobile_hmac: bytes | None
    email: str | None  # lower case
    address_hmac: bytes | None
    mobile_last4: str | None


@dataclass(frozen=True, slots=True)
class Ring:
    members: tuple[Member, ...]
    institution_ids: frozenset[uuid.UUID]
    shared: tuple[tuple[str, str, int], ...]  # (kind, masked value, students sharing it)

    @property
    def student_ids(self) -> tuple[uuid.UUID, ...]:
        return tuple(sorted({m.student_id for m in self.members}))

    @property
    def students(self) -> int:
        return len({m.student_id for m in self.members})

    def shared_count(self, kind: str) -> int:
        return sum(1 for k, _, _ in self.shared if k == kind)


def mask_email(email: str) -> str:
    """`ravi.k@example.com` -> `r***@example.com`."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else f"{email[:1]}***"


def _contacts(member: Member) -> Iterable[tuple[str, bytes | str]]:
    if member.mobile_hmac:
        yield MOBILE, member.mobile_hmac
    if member.email:
        yield EMAIL, member.email.strip().lower()
    if member.address_hmac:
        yield ADDRESS, member.address_hmac


def contact_holders(members: Sequence[Member]) -> dict[tuple[str, bytes | str], set[uuid.UUID]]:
    """Each contact value and the students who gave it."""
    holders: dict[tuple[str, bytes | str], set[uuid.UUID]] = defaultdict(set)
    for member in members:
        for contact in _contacts(member):
            holders[contact].add(member.student_id)
    return holders


def sharing_students(members: Sequence[Member]) -> set[uuid.UUID]:
    """Students who share a mobile, an email or an address with another student."""
    out: set[uuid.UUID] = set()
    for students in contact_holders(members).values():
        if len(students) > 1:
            out |= students
    return out


def _masked(kind: str, value: bytes | str, last4: Mapping[bytes, str]) -> str:
    if kind == MOBILE:
        tail = last4.get(value) if isinstance(value, bytes) else None
        return f"XXXXXX{tail}" if tail else "XXXXXXXXXX"
    if kind == EMAIL:
        return mask_email(str(value))
    return "Same address"


def find_rings(
    members: Sequence[Member], *, min_cross: int, min_colleges: int, min_single: int
) -> list[Ring]:
    """The rings among the members, largest first (ties by smallest student id)."""
    holders = contact_holders(members)
    graph = nx.Graph()
    graph.add_nodes_from({m.student_id for m in members})
    for students in holders.values():
        if len(students) < 2:
            continue
        first, *rest = sorted(students)
        graph.add_edges_from((first, other) for other in rest)

    by_student: dict[uuid.UUID, list[Member]] = defaultdict(list)
    for member in members:
        by_student[member.student_id].append(member)
    last4 = {m.mobile_hmac: m.mobile_last4 for m in members if m.mobile_hmac and m.mobile_last4}

    rings: list[Ring] = []
    for component in nx.connected_components(graph):
        size = len(component)
        if size < 2:
            continue
        ring_members = [m for s in component for m in by_student[s]]
        colleges = frozenset(m.institution_id for m in ring_members)
        across = len(colleges) >= min_colleges and size >= min_cross
        single = len(colleges) == 1 and size >= min_single
        if not (across or single):
            continue
        shared = sorted(
            (
                (kind, _masked(kind, value, last4), len(students & component))
                for (kind, value), students in holders.items()
                if len(students & component) > 1
            ),
            key=lambda item: (KIND_ORDER[item[0]], -item[2], item[1]),
        )
        rings.append(
            Ring(
                members=tuple(
                    sorted(ring_members, key=lambda m: (str(m.institution_id), str(m.enrolment_id)))
                ),
                institution_ids=colleges,
                shared=tuple(shared),
            )
        )
    rings.sort(key=lambda r: (-r.students, str(r.student_ids[0])))
    return rings


async def load_members(session: AsyncSession, academic_year: str) -> list[Member]:
    """Every ACTIVE enrolment of the year with its student's contact hashes."""
    rows = await session.execute(
        select(
            Enrolment.id,
            Enrolment.student_id,
            Enrolment.institution_id,
            Student.mobile_hmac,
            func.lower(Student.email),
            Student.address_hmac,
            Student.mobile_last4,
        )
        .join(Student, Student.id == Enrolment.student_id)
        .where(
            Enrolment.academic_year == academic_year,
            Enrolment.status == EnrolmentStatus.ACTIVE,
        )
        .order_by(Enrolment.id)
    )
    return [Member(*row) for row in rows.all()]


# ------------------------------------------------------------------- sentences


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _join(parts: Sequence[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def shared_clause(mobiles: int, emails: int, addresses: int) -> str:
    """`6 mobile numbers and 2 addresses`: a count of 0 drops its clause (copy deck §27)."""
    parts = []
    if mobiles:
        parts.append(_plural(mobiles, "mobile number", "mobile numbers"))
    if emails:
        parts.append(_plural(emails, "email address", "email addresses"))
    if addresses:
        parts.append(_plural(addresses, "address", "addresses"))
    return _join(parts)


def summary(ring: Ring, institution_names: Mapping[uuid.UUID, str]) -> str:
    """copy deck signal.summary.GHOST_RING and GHOST_RING_one."""
    clause = shared_clause(
        ring.shared_count(MOBILE), ring.shared_count(EMAIL), ring.shared_count(ADDRESS)
    )
    students = _plural(ring.students, "student", "students")
    if len(ring.institution_ids) == 1:
        [only] = ring.institution_ids
        return f"{students} at {institution_names.get(only, 'one college')} share {clause}."
    return f"{students} across {len(ring.institution_ids)} colleges share {clause}."


def rule(*, min_cross: int, min_colleges: int, min_single: int) -> str:
    return RULE.format(min_cross=min_cross, min_colleges=min_colleges, min_single=min_single)
