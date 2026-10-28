"""In-memory adapters for unit tests: registries are plain dicts and lists."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from rapidfuzz import fuzz

from app.adapters.base import (
    AbcResult,
    AdapterRequestError,
    ApaarResult,
    CounsellingResult,
    DigiLockerResult,
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
