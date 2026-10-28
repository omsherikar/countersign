"""Government source adapters: one Protocol per source, three implementations each (D5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Protocol, runtime_checkable

SourceName = Literal["apaar", "counselling", "abc", "digilocker", "sii"]
SOURCES: tuple[SourceName, ...] = ("apaar", "counselling", "abc", "digilocker", "sii")

PROBE_APAAR_ID = "000000000000"


class AdapterError(Exception):
    """Base for adapter failures."""


class SourceUnavailable(AdapterError):
    """Timeout, connection failure or 5xx: the caller stores PENDING and retries later."""

    def __init__(self, source: str, detail: str) -> None:
        super().__init__(f"{source}: {detail}")
        self.source = source
        self.detail = detail


class RealAdapterDisabled(AdapterError):
    """Real government APIs are never called unless ALLOW_REAL_GOV_APIS=true."""

    def __init__(self, source: str) -> None:
        super().__init__(f"{source}: real adapter disabled (ALLOW_REAL_GOV_APIS is not true)")
        self.source = source


class AdapterRequestError(AdapterError):
    """The source rejected the request (4xx): a bug on our side, not an outage."""

    def __init__(self, source: str, status_code: int, body: str) -> None:
        super().__init__(f"{source}: HTTP {status_code} {body[:200]}")
        self.source = source
        self.status_code = status_code


@dataclass(slots=True, frozen=True)
class ApaarResult:
    exists: bool
    name_score: int
    dob_match: bool


@dataclass(slots=True, frozen=True)
class CounsellingResult:
    found: bool
    round: int | None = None
    category: str | None = None
    allotment_ref: str | None = None


@dataclass(slots=True, frozen=True)
class Semester:
    sem: int
    credits: int
    uploaded_at: str | None
    result: str


@dataclass(slots=True, frozen=True)
class AbcResult:
    apaar_id_known: bool
    semesters: list[Semester] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class DigiLockerResult:
    delivered: bool
    inbox_id: str | None = None
    reason: str | None = None


@dataclass(slots=True, frozen=True)
class SiiResult:
    admitted: bool
    institution_aicte_id: str | None = None
    programme: str | None = None
    academic_year: str | None = None


@runtime_checkable
class ApaarAdapter(Protocol):
    async def verify(self, apaar_id: str, name: str, dob: date) -> ApaarResult: ...
    async def ping(self) -> None: ...


@runtime_checkable
class CounsellingAdapter(Protocol):
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
    ) -> CounsellingResult: ...
    async def ping(self) -> None: ...


@runtime_checkable
class AbcAdapter(Protocol):
    async def credits(self, apaar_id: str, academic_year: str) -> AbcResult: ...
    async def ping(self) -> None: ...


@runtime_checkable
class DigiLockerAdapter(Protocol):
    async def notify(self, apaar_id: str, message: str, callback_url: str) -> DigiLockerResult: ...
    async def ping(self) -> None: ...


@runtime_checkable
class SiiAdapter(Protocol):
    async def verify(self, passport_no: str, name: str, nationality: str) -> SiiResult: ...
    async def ping(self) -> None: ...


@dataclass(slots=True)
class AdapterSet:
    name: Literal["inmemory", "mockgov", "real"]
    apaar: ApaarAdapter
    counselling: CounsellingAdapter
    abc: AbcAdapter
    digilocker: DigiLockerAdapter
    sii: SiiAdapter
    client: Any = None  # shared transport to close on shutdown, when there is one

    def by_source(self, source: SourceName) -> object:
        return getattr(self, source)

    async def aclose(self) -> None:
        closer = getattr(self.client, "aclose", None)
        if closer is not None:
            await closer()
