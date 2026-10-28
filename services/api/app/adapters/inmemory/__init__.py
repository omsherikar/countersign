"""In-memory adapters for unit tests: registries are plain dicts and lists."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from rapidfuzz import fuzz

from app.adapters.base import (
    AbcResult,
    AdapterRequestError,
    ApaarResult,
    CounsellingResult,
    DigiLockerResult,
    Joining,
    JoiningList,
    JoiningResult,
    Semester,
    SiiResult,
    SourceUnavailable,
)
from app.core.crypto import normalise_name


class _Downable:
    """Mixin: flip `down` to make the fake source behave like an outage."""

    down: bool = False
    source: str = ""

    def _guard(self) -> None:
        if self.down:
            raise SourceUnavailable(self.source, "in-memory source marked down")

    async def ping(self) -> None:
        self._guard()


@dataclass
class InMemoryApaar(_Downable):
    """registry: {apaar_id: {"name": str, "dob": date}}"""

    registry: dict[str, dict] = field(default_factory=dict)
    source: str = "apaar"
    down: bool = False

    async def verify(self, apaar_id: str, name: str, dob: date) -> ApaarResult:
        self._guard()
        row = self.registry.get(apaar_id)
        if row is None:
            return ApaarResult(exists=False, name_score=0, dob_match=False)
        score = int(round(fuzz.token_set_ratio(normalise_name(name), normalise_name(row["name"]))))
        return ApaarResult(exists=True, name_score=score, dob_match=row["dob"] == dob)


@dataclass
class InMemoryCounselling(_Downable):
    """allotments: list of dicts shaped like datagen's counselling.jsonl rows."""

    allotments: list[dict] = field(default_factory=list)
    source: str = "counselling"
    down: bool = False

    async def verify(
        self,
        *,
        state: str,
        year: int,
        name: str,
        dob: date,
        programme: str,
        roll_no: str | None = None,
        institution_aicte_id: str | None = None,
    ) -> CounsellingResult:
        self._guard()
        for row in self.allotments:
            if roll_no is not None:
                if row.get("roll_no") == roll_no:
                    return self._found(row)
                continue
            if (
                row.get("state") == state
                and int(row.get("year", 0)) == year
                and row.get("programme") == programme
                and str(row.get("dob")) == dob.isoformat()
                and fuzz.token_set_ratio(normalise_name(name), normalise_name(row["name"])) >= 90
            ):
                return self._found(row)
        return CounsellingResult(found=False)

    @staticmethod
    def _found(row: dict) -> CounsellingResult:
        return CounsellingResult(
            found=True,
            round=row.get("round"),
            category=row.get("category"),
            allotment_ref=row.get("allotment_ref"),
        )


def _as_date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


@dataclass
class InMemoryAdmissionAuthority(_Downable):
    """joinings: {(state, academic_year): [dicts shaped like datagen's
    admission_joinings.jsonl rows]}. A (state, year) with no joining has published nothing."""

    joinings_by_year: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    source: str = "admission_authority"
    down: bool = False

    def add(self, row: dict) -> None:
        key = (str(row["state"]).upper(), str(row["academic_year"]))
        self.joinings_by_year.setdefault(key, []).append(row)

    async def joining(
        self,
        *,
        state: str,
        academic_year: str,
        name: str,
        dob: date,
        institution_code: str,
        programme: str,
        roll_no: str | None = None,
    ) -> JoiningResult:
        self._guard()
        rows = self.joinings_by_year.get((state.upper(), academic_year))
        if not rows:
            return JoiningResult(found=False, published=False)
        claimed = normalise_name(name)
        best: dict | None = None
        best_score = 89
        for row in rows:
            if row.get("institution_code") != institution_code or row.get("programme") != programme:
                continue
            if roll_no:
                if row.get("roll_no") == roll_no:
                    best = row
                    break
                continue
            if _as_date(row["dob"]) != dob:
                continue
            score = int(round(fuzz.token_set_ratio(claimed, normalise_name(row["name"]))))
            if score > best_score:
                best, best_score = row, score
        if best is None:
            return JoiningResult(found=False, published=True)
        return JoiningResult(
            found=True,
            joined_on=_as_date(best["joined_on"]),
            round=best.get("round"),
            route=best.get("route"),
            category=best.get("category"),
            published=True,
        )

    async def joinings(self, *, institution_code: str, academic_year: str) -> JoiningList:
        self._guard()
        states = {
            state
            for (state, _year), rows in self.joinings_by_year.items()
            if any(r.get("institution_code") == institution_code for r in rows)
        }
        rows = [
            r
            for state in states
            for r in self.joinings_by_year.get((state, academic_year), [])
            if r.get("institution_code") == institution_code
        ]
        rows.sort(key=lambda r: (r["programme"], str(r["joined_on"]), r.get("roll_no") or "~"))
        published = bool(rows) or any((s, academic_year) in self.joinings_by_year for s in states)
        return JoiningList(
            published=published,
            items=[
                Joining(
                    roll_no=r.get("roll_no"),
                    name=r["name"],
                    dob=_as_date(r["dob"]),
                    programme=r["programme"],
                    joined_on=_as_date(r["joined_on"]),
                    round=r.get("round"),
                    route=r["route"],
                    category=r["category"],
                    apaar_last4=(r.get("apaar_id") or "")[-4:] or None,
                )
                for r in rows
            ],
        )


@dataclass
class InMemoryAbc(_Downable):
    """credits: {apaar_id: {academic_year: [Semester-like dicts]}}"""

    credits_by_apaar: dict[str, dict[str, list[dict]]] = field(default_factory=dict)
    source: str = "abc"
    down: bool = False

    async def credits(self, apaar_id: str, academic_year: str) -> AbcResult:
        self._guard()
        years = self.credits_by_apaar.get(apaar_id)
        if years is None:
            return AbcResult(apaar_id_known=False)
        return AbcResult(
            apaar_id_known=True,
            semesters=[
                Semester(
                    sem=int(s["sem"]),
                    credits=int(s["credits"]),
                    uploaded_at=s.get("uploaded_at"),
                    result=s.get("result", "PENDING"),
                    issuer=s.get("issuer"),
                    issuer_name=s.get("issuer_name"),
                )
                for s in years.get(academic_year, [])
            ],
        )


@dataclass
class InMemoryDigiLocker(_Downable):
    """linked: set of APAAR ids that can receive notices; inbox collects deliveries.

    An APAAR with no DigiLocker account is a 404, as mockgov answers (API_CONTRACT §A3.28).
    """

    linked: set[str] = field(default_factory=set)
    inbox: list[dict] = field(default_factory=list)
    source: str = "digilocker"
    down: bool = False

    async def notify(self, apaar_id: str, message: str, callback_url: str) -> DigiLockerResult:
        self._guard()
        if apaar_id not in self.linked:
            raise AdapterRequestError(self.source, 404, '{"error": {"code": "APAAR_NOT_LINKED"}}')
        inbox_id = f"ib_mem_{len(self.inbox) + 1:06d}"
        self.inbox.append(
            {
                "inbox_id": inbox_id,
                "apaar_id": apaar_id,
                "message": message,
                "callback_url": callback_url,
            }
        )
        return DigiLockerResult(delivered=True, inbox_id=inbox_id)


@dataclass
class InMemorySii(_Downable):
    """admissions: {passport_no: {name, nationality, institution_aicte_id, programme,
    academic_year}}"""

    admissions: dict[str, dict] = field(default_factory=dict)
    source: str = "sii"
    down: bool = False

    async def verify(self, passport_no: str, name: str, nationality: str) -> SiiResult:
        self._guard()
        row = self.admissions.get(passport_no)
        if row is None or row.get("nationality") != nationality:
            return SiiResult(admitted=False)
        return SiiResult(
            admitted=True,
            institution_aicte_id=row.get("institution_aicte_id"),
            programme=row.get("programme"),
            academic_year=row.get("academic_year"),
        )
