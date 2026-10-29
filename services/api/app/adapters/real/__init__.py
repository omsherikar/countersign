"""Real government adapters: same interface, never callable unless ALLOW_REAL_GOV_APIS=true.

Even with the flag set these are stubs: there is no credential handling and no
endpoint map here, so the demo can never reach a real registry (DECISIONS D5).
"""

from __future__ import annotations

from datetime import date

from app.adapters.base import (
    AbcResult,
    ApaarResult,
    CounsellingResult,
    DigiLockerIdentity,
    DigiLockerResult,
    JoiningList,
    JoiningResult,
    RealAdapterDisabled,
    SiiResult,
)


class _RealBase:
    source: str = ""

    def __init__(self, base_url: str | None = None, enabled: bool = False) -> None:
        self.base_url = base_url
        self.enabled = enabled

    def _guard(self) -> None:
        if not self.enabled:
            raise RealAdapterDisabled(self.source)
        raise NotImplementedError(f"{self.source}: real adapter has no implementation yet")

    async def ping(self) -> None:
        self._guard()


class RealApaar(_RealBase):
    source = "apaar"

    async def verify(self, apaar_id: str, name: str, dob: date) -> ApaarResult:
        self._guard()
        raise AssertionError("unreachable")


class RealCounselling(_RealBase):
    source = "counselling"

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
        raise AssertionError("unreachable")


class RealAdmissionAuthority(_RealBase):
    source = "admission_authority"

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
        raise AssertionError("unreachable")

    async def joinings(self, *, institution_code: str, academic_year: str) -> JoiningList:
        self._guard()
        raise AssertionError("unreachable")


class RealAbc(_RealBase):
    source = "abc"

    async def credits(self, apaar_id: str, academic_year: str) -> AbcResult:
        self._guard()
        raise AssertionError("unreachable")


class RealDigiLocker(_RealBase):
    source = "digilocker"

    async def notify(self, apaar_id: str, message: str, callback_url: str) -> DigiLockerResult:
        self._guard()
        raise AssertionError("unreachable")

    def authorize_url(self, *, state: str, nonce: str, redirect_uri: str) -> str:
        self._guard()
        raise AssertionError("unreachable")

    async def exchange_code(
        self, *, code: str, redirect_uri: str, nonce: str
    ) -> DigiLockerIdentity:
        self._guard()
        raise AssertionError("unreachable")


class RealSii(_RealBase):
    source = "sii"

    async def verify(self, passport_no: str, name: str, nationality: str) -> SiiResult:
        self._guard()
        raise AssertionError("unreachable")
