"""Pick the adapter set from GOV_ADAPTER, and probe it for /admin/adapters/ping."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.adapters.base import SOURCES, AdapterSet, RealAdapterDisabled, SourceName
from app.adapters.inmemory import (
    InMemoryAbc,
    InMemoryAdmissionAuthority,
    InMemoryApaar,
    InMemoryCounselling,
    InMemoryDigiLocker,
    InMemorySii,
)
from app.adapters.mockgov import (
    MockGovAbc,
    MockGovAdmissionAuthority,
    MockGovApaar,
    MockGovClient,
    MockGovCounselling,
    MockGovDigiLocker,
    MockGovSii,
)
from app.adapters.real import (
    RealAbc,
    RealAdmissionAuthority,
    RealApaar,
    RealCounselling,
    RealDigiLocker,
    RealSii,
)
from app.core.config import Settings, get_settings


def build_adapters(settings: Settings | None = None) -> AdapterSet:
    settings = settings or get_settings()
    kind = settings.gov_adapter
    if kind == "inmemory":
        return AdapterSet(
            name="inmemory",
            apaar=InMemoryApaar(),
            counselling=InMemoryCounselling(),
            abc=InMemoryAbc(),
            digilocker=InMemoryDigiLocker(),
            sii=InMemorySii(),
            admission_authority=InMemoryAdmissionAuthority(),
        )
    if kind == "mockgov":
        client = MockGovClient(settings.mockgov_base_url, timeout=settings.gov_timeout_seconds)
        return AdapterSet(
            name="mockgov",
            apaar=MockGovApaar(client),
            counselling=MockGovCounselling(client),
            abc=MockGovAbc(client),
            digilocker=MockGovDigiLocker(client),
            sii=MockGovSii(client),
            admission_authority=MockGovAdmissionAuthority(client),
            client=client,
        )
    enabled = settings.allow_real_gov_apis
    return AdapterSet(
        name="real",
        apaar=RealApaar(enabled=enabled),
        counselling=RealCounselling(enabled=enabled),
        abc=RealAbc(enabled=enabled),
        digilocker=RealDigiLocker(enabled=enabled),
        sii=RealSii(enabled=enabled),
        admission_authority=RealAdmissionAuthority(enabled=enabled),
    )


@dataclass(slots=True)
class PingResult:
    status: str  # OK | UNAVAILABLE | DISABLED
    latency_ms: int
    detail: str | None


async def ping_all(adapters: AdapterSet) -> dict[SourceName, PingResult]:
    results: dict[SourceName, PingResult] = {}
    for source in SOURCES:
        adapter = adapters.by_source(source)
        started = time.perf_counter()
        try:
            await adapter.ping()  # type: ignore[attr-defined]
            results[source] = PingResult("OK", _ms(started), None)
        except RealAdapterDisabled as exc:
            results[source] = PingResult("DISABLED", _ms(started), str(exc))
        except Exception as exc:  # SourceUnavailable, AdapterRequestError, anything else
            detail = getattr(exc, "detail", None) or str(exc)
            results[source] = PingResult("UNAVAILABLE", _ms(started), detail)
    return results


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
