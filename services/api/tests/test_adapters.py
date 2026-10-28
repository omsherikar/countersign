from datetime import date

import httpx
import pytest
import respx

from app.adapters.base import AdapterRequestError, RealAdapterDisabled, SourceUnavailable
from app.adapters.factory import build_adapters, ping_all
from app.adapters.inmemory import (
    InMemoryAbc,
    InMemoryApaar,
    InMemoryCounselling,
    InMemoryDigiLocker,
    InMemorySii,
)
from app.adapters.mockgov import MockGovAbc, MockGovApaar, MockGovClient, MockGovDigiLocker
from app.core.config import Settings

BASE = "http://mockgov.test"


# ------------------------------------------------------------------- in-memory


async def test_inmemory_apaar_scores_names_and_never_returns_them():
    apaar = InMemoryApaar({"123456784417": {"name": "Ravi Kumar Sharma", "dob": date(2007, 3, 21)}})
    exact = await apaar.verify("123456784417", "Ravi Kumar Sharma", date(2007, 3, 21))
    assert (exact.exists, exact.name_score, exact.dob_match) == (True, 100, True)
    fuzzy = await apaar.verify("123456784417", "Ravi Kumer Sharna", date(2007, 3, 22))
    assert fuzzy.exists and 60 <= fuzzy.name_score < 100 and fuzzy.dob_match is False
    missing = await apaar.verify("000000000000", "Nobody", date(2000, 1, 1))
    assert (missing.exists, missing.name_score, missing.dob_match) == (False, 0, False)
    assert not hasattr(exact, "name")


async def test_inmemory_counselling_roll_no_then_fuzzy():
    row = {
        "state": "MH",
        "year": 2026,
        "name": "Ravi Kumar Sharma",
        "dob": "2007-03-21",
        "roll_no": "MHCET-2026-004512",
        "programme": "CSE",
        "round": 1,
        "category": "GENERAL",
        "allotment_ref": "MHCET-2026-R1-004512",
    }
    adapter = InMemoryCounselling([row])
    by_roll = await adapter.verify(
        state="MH",
        year=2026,
        name="x",
        dob=date(2000, 1, 1),
        programme="ECE",
        roll_no="MHCET-2026-004512",
    )
    assert by_roll.found and by_roll.allotment_ref == "MHCET-2026-R1-004512"
    fuzzy = await adapter.verify(
        state="MH", year=2026, name="Sharma Ravi Kumar", dob=date(2007, 3, 21), programme="CSE"
    )
    assert fuzzy.found and fuzzy.round == 1
    none = await adapter.verify(
        state="TN", year=2026, name="Ravi Kumar Sharma", dob=date(2007, 3, 21), programme="CSE"
    )
    assert none.found is False and none.allotment_ref is None


async def test_inmemory_abc_digilocker_sii():
    abc = InMemoryAbc({"1": {"2025-26": [{"sem": 1, "credits": 22, "result": "PASS"}]}})
    known = await abc.credits("1", "2025-26")
    assert known.apaar_id_known and known.semesters[0].credits == 22
    assert (await abc.credits("1", "2026-27")).semesters == []
    assert (await abc.credits("2", "2025-26")).apaar_id_known is False

    dl = InMemoryDigiLocker(linked={"1"})
    ok = await dl.notify("1", "hi", "http://cb")
    assert ok.delivered and ok.inbox_id and dl.inbox[0]["message"] == "hi"
    with pytest.raises(AdapterRequestError) as nope:
        await dl.notify("2", "hi", "http://cb")
    assert nope.value.status_code == 404 and len(dl.inbox) == 1

    sii = InMemorySii(
        {
            "N1234567": {
                "nationality": "BD",
                "institution_aicte_id": "1-ABC-0001",
                "programme": "CSE",
                "academic_year": "2026-27",
            }
        }
    )
    assert (await sii.verify("N1234567", "Aisha Rahman", "BD")).admitted is True
    assert (await sii.verify("N1234567", "Aisha Rahman", "NP")).admitted is False


async def test_inmemory_down_flag_raises_source_unavailable():
    apaar = InMemoryApaar(down=True)
    with pytest.raises(SourceUnavailable):
        await apaar.verify("1", "a", date(2000, 1, 1))
    with pytest.raises(SourceUnavailable):
        await apaar.ping()


# --------------------------------------------------------------------- mockgov


@respx.mock(base_url=BASE)
async def test_mockgov_apaar_happy_path(respx_mock):
    route = respx_mock.post("/apaar/verify").mock(
        return_value=httpx.Response(
            200, json={"exists": True, "name_score": 71, "dob_match": False}
        )
    )
    client = MockGovClient(BASE)
    result = await MockGovApaar(client).verify("123456784417", "R K Sharma", date(2007, 3, 21))
    assert (result.exists, result.name_score, result.dob_match) == (True, 71, False)
    sent = route.calls[0].request
    assert sent.read() == b'{"apaar_id":"123456784417","name":"R K Sharma","dob":"2007-03-21"}'
    await client.aclose()


@respx.mock(base_url=BASE)
async def test_mockgov_503_retries_once_then_unavailable(respx_mock):
    route = respx_mock.post("/abc/credits").mock(
        return_value=httpx.Response(503, json={"error": {"code": "SOURCE_DOWN"}})
    )
    client = MockGovClient(BASE)
    with pytest.raises(SourceUnavailable) as exc:
        await MockGovAbc(client).credits("1", "2026-27")
    assert exc.value.source == "abc" and "503" in exc.value.detail
    assert route.call_count == 2
    await client.aclose()


@respx.mock(base_url=BASE)
async def test_mockgov_timeout_and_connect_error_are_unavailable(respx_mock):
    respx_mock.post("/apaar/verify").mock(side_effect=httpx.ReadTimeout("slow"))
    respx_mock.get("/digilocker/inbox/000000000000").mock(side_effect=httpx.ConnectError("refused"))
    client = MockGovClient(BASE, timeout=3.0)
    with pytest.raises(SourceUnavailable) as timed_out:
        await MockGovApaar(client).ping()
    assert timed_out.value.detail == "timeout after 3000 ms"
    with pytest.raises(SourceUnavailable) as refused:
        await MockGovDigiLocker(client).ping()
    assert "connection error" in refused.value.detail
    await client.aclose()


@respx.mock(base_url=BASE)
async def test_mockgov_4xx_is_a_request_error_not_an_outage(respx_mock):
    route = respx_mock.post("/apaar/verify").mock(
        return_value=httpx.Response(422, json={"error": {}})
    )
    client = MockGovClient(BASE)
    with pytest.raises(AdapterRequestError):
        await MockGovApaar(client).verify("12", "x", date(2000, 1, 1))
    assert route.call_count == 1
    await client.aclose()


@respx.mock(base_url=BASE)
async def test_mockgov_retry_recovers_after_one_failure(respx_mock):
    route = respx_mock.post("/apaar/verify").mock(
        side_effect=[
            httpx.Response(502),
            httpx.Response(200, json={"exists": False, "name_score": 0, "dob_match": False}),
        ]
    )
    client = MockGovClient(BASE)
    result = await MockGovApaar(client).verify("1", "x", date(2000, 1, 1))
    assert result.exists is False and route.call_count == 2
    await client.aclose()


# --------------------------------------------------------------------- factory


async def test_factory_inmemory_and_real_and_ping():
    inmem = build_adapters(Settings(gov_adapter="inmemory"))
    assert inmem.name == "inmemory"
    results = await ping_all(inmem)
    assert {k: v.status for k, v in results.items()} == dict.fromkeys(
        ["apaar", "counselling", "abc", "digilocker", "sii"], "OK"
    )

    real = build_adapters(Settings(gov_adapter="real", allow_real_gov_apis=False))
    assert real.name == "real"
    with pytest.raises(RealAdapterDisabled):
        await real.apaar.verify("1", "x", date(2000, 1, 1))
    results = await ping_all(real)
    assert all(v.status == "DISABLED" for v in results.values())


@respx.mock(base_url=BASE)
async def test_factory_mockgov_ping_reports_each_source(respx_mock):
    respx_mock.post("/apaar/verify").mock(
        return_value=httpx.Response(
            200, json={"exists": False, "name_score": 0, "dob_match": False}
        )
    )
    respx_mock.post("/counselling/verify").mock(
        return_value=httpx.Response(200, json={"found": False})
    )
    respx_mock.post("/abc/credits").mock(
        return_value=httpx.Response(200, json={"apaar_id_known": False, "semesters": []})
    )
    respx_mock.get("/digilocker/inbox/000000000000").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    respx_mock.post("/sii/verify").mock(
        return_value=httpx.Response(503, json={"error": {"code": "SOURCE_DOWN"}})
    )
    adapters = build_adapters(Settings(gov_adapter="mockgov", mockgov_base_url=BASE))
    results = await ping_all(adapters)
    assert {k: v.status for k, v in results.items()} == {
        "apaar": "OK",
        "counselling": "OK",
        "abc": "OK",
        "digilocker": "OK",
        "sii": "UNAVAILABLE",
    }
    assert results["sii"].detail == "HTTP 503"
    await adapters.aclose()
