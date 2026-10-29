"""The state admission authority source in all three adapter sets (ENGINES §17.4, C.9, C.10)."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
import respx

from app.adapters.base import RealAdapterDisabled, SourceUnavailable
from app.adapters.factory import build_adapters, ping_all
from app.adapters.inmemory import InMemoryAbc, InMemoryAdmissionAuthority
from app.adapters.mockgov import MockGovAbc, MockGovAdmissionAuthority, MockGovClient
from app.core.config import Settings
from tests.evidence.conftest import joining_row

BASE = "http://mockgov.test"
RAVI = {"name": "Ravi Kumar Sharma", "dob": date(2007, 3, 21)}


def _authority() -> InMemoryAdmissionAuthority:
    authority = InMemoryAdmissionAuthority()
    authority.add(
        joining_row(
            **RAVI,
            institution_code="1-ABC-0001",
            roll_no="MHCET-2026-004512",
            apaar_id="123456784417",
        )
    )
    authority.add(
        joining_row(
            name="Asha Patil",
            dob=date(2007, 5, 2),
            institution_code="1-ABC-0001",
            programme="ECE",
            joined_on=date(2026, 8, 20),
            round=None,
            route="MANAGEMENT",
        )
    )
    return authority


async def test_a_joining_matches_by_name_and_date_of_birth() -> None:
    authority = _authority()
    found = await authority.joining(
        state="mh",
        academic_year="2026-27",
        name="Sharma Ravi Kumar",
        dob=RAVI["dob"],
        institution_code="1-ABC-0001",
        programme="CSE",
    )
    assert (found.found, found.joined_on, found.round, found.route, found.published) == (
        True,
        date(2026, 8, 2),
        1,
        "COUNSELLING",
        True,
    )


async def test_a_roll_number_matches_exactly_instead_of_the_name() -> None:
    authority = _authority()
    by_roll = await authority.joining(
        state="MH",
        academic_year="2026-27",
        name="Somebody Else",
        dob=date(2000, 1, 1),
        institution_code="1-ABC-0001",
        programme="CSE",
        roll_no="MHCET-2026-004512",
    )
    assert by_roll.found


@pytest.mark.parametrize(
    "change",
    [
        {"dob": date(2007, 3, 22)},
        {"programme": "ECE"},
        {"institution_code": "1-XYZ-0002"},
        {"name": "Priya Nair"},
    ],
)
async def test_anything_else_is_not_found_in_a_published_record(change) -> None:
    query = {
        "state": "MH",
        "academic_year": "2026-27",
        "institution_code": "1-ABC-0001",
        "programme": "CSE",
        **RAVI,
        **change,
    }
    result = await _authority().joining(**query)
    assert (result.found, result.published, result.joined_on) == (False, True, None)


async def test_a_state_and_year_with_no_joining_has_published_nothing() -> None:
    result = await _authority().joining(
        state="KA",
        academic_year="2026-27",
        institution_code="1-ABC-0001",
        programme="CSE",
        **RAVI,
    )
    assert (result.found, result.published) == (False, False)
    other_year = await _authority().joining(
        state="MH",
        academic_year="2025-26",
        institution_code="1-ABC-0001",
        programme="CSE",
        **RAVI,
    )
    assert other_year.published is False


async def test_the_joinings_list_of_a_college_is_ordered_and_masks_the_apaar() -> None:
    listed = await _authority().joinings(institution_code="1-ABC-0001", academic_year="2026-27")
    assert listed.published is True
    assert [(j.programme, j.name, j.apaar_last4) for j in listed.items] == [
        ("CSE", "Ravi Kumar Sharma", "4417"),
        ("ECE", "Asha Patil", None),
    ]
    empty = await _authority().joinings(institution_code="1-ABC-0001", academic_year="2025-26")
    assert (empty.published, empty.items) == (False, [])


async def test_a_down_authority_is_unavailable() -> None:
    authority = _authority()
    authority.down = True
    with pytest.raises(SourceUnavailable):
        await authority.joinings(institution_code="1-ABC-0001", academic_year="2026-27")
    with pytest.raises(SourceUnavailable):
        await authority.ping()


async def test_in_memory_credits_carry_their_issuer() -> None:
    abc = InMemoryAbc(
        {
            "1": {
                "2025-26": [
                    {"sem": 1, "credits": 22, "issuer": "MSTU", "issuer_name": "Maharashtra State"}
                ]
            }
        }
    )
    semester = (await abc.credits("1", "2025-26")).semesters[0]
    assert (semester.issuer, semester.issuer_name) == ("MSTU", "Maharashtra State")


@respx.mock(base_url=BASE)
async def test_mockgov_sends_the_contract_request_and_reads_the_answer(respx_mock) -> None:
    route = respx_mock.post("/admission-authority/joining").mock(
        return_value=httpx.Response(
            200,
            json={
                "found": True,
                "joined_on": "2026-08-02",
                "round": 1,
                "route": "COUNSELLING",
                "category": "GENERAL",
                "published": True,
            },
        )
    )
    client = MockGovClient(BASE)
    result = await MockGovAdmissionAuthority(client).joining(
        state="MH",
        academic_year="2026-27",
        institution_code="1-ABC-0001",
        programme="CSE",
        **RAVI,
    )
    assert result.found and result.joined_on == date(2026, 8, 2) and result.published
    assert json.loads(route.calls.last.request.content) == {
        "state": "MH",
        "academic_year": "2026-27",
        "name": "Ravi Kumar Sharma",
        "dob": "2007-03-21",
        "roll_no": None,
        "institution_code": "1-ABC-0001",
        "programme": "CSE",
    }
    await client.aclose()


@respx.mock(base_url=BASE)
async def test_mockgov_reads_an_unpublished_record_and_the_joinings_list(respx_mock) -> None:
    respx_mock.post("/admission-authority/joining").mock(
        return_value=httpx.Response(
            200,
            json={
                "found": False,
                "joined_on": None,
                "round": None,
                "route": None,
                "category": None,
                "published": False,
            },
        )
    )
    listing = respx_mock.get("/admission-authority/joinings").mock(
        return_value=httpx.Response(
            200,
            json={
                "institution_code": "1-ABC-0001",
                "academic_year": "2026-27",
                "published": True,
                "items": [
                    {
                        "roll_no": None,
                        "name": "Asha Patil",
                        "dob": "2007-05-02",
                        "programme": "ECE",
                        "joined_on": "2026-08-20",
                        "round": None,
                        "route": "MANAGEMENT",
                        "category": "GENERAL",
                        "apaar_last4": None,
                    }
                ],
            },
        )
    )
    client = MockGovClient(BASE)
    authority = MockGovAdmissionAuthority(client)
    result = await authority.joining(
        state="MH",
        academic_year="2026-27",
        institution_code="1-ABC-0001",
        programme="CSE",
        **RAVI,
    )
    assert (result.found, result.published) == (False, False)
    listed = await authority.joinings(institution_code="1-ABC-0001", academic_year="2026-27")
    assert listed.items[0].joined_on == date(2026, 8, 20) and listed.items[0].roll_no is None
    params = dict(listing.calls.last.request.url.params)
    assert params == {"institution_code": "1-ABC-0001", "academic_year": "2026-27"}
    await client.aclose()


@respx.mock(base_url=BASE)
async def test_mockgov_outage_and_credits_issuer(respx_mock) -> None:
    respx_mock.post("/admission-authority/joining").mock(return_value=httpx.Response(503))
    respx_mock.post("/abc/credits").mock(
        return_value=httpx.Response(
            200,
            json={
                "apaar_id_known": True,
                "semesters": [
                    {
                        "sem": 1,
                        "credits": 22,
                        "uploaded_at": "2026-01-20T00:00:00Z",
                        "result": "PASS",
                        "issuer": "1-PQR-0007",
                        "issuer_name": "PQR Institute of Technology",
                    }
                ],
            },
        )
    )
    client = MockGovClient(BASE)
    with pytest.raises(SourceUnavailable):
        await MockGovAdmissionAuthority(client).joining(
            state="MH",
            academic_year="2026-27",
            institution_code="1-ABC-0001",
            programme="CSE",
            **RAVI,
        )
    semester = (await MockGovAbc(client).credits("1", "2025-26")).semesters[0]
    assert (semester.issuer, semester.issuer_name) == ("1-PQR-0007", "PQR Institute of Technology")
    await client.aclose()


async def test_every_set_has_the_authority_and_the_real_one_is_disabled() -> None:
    inmemory = build_adapters(Settings(gov_adapter="inmemory"))
    assert (await ping_all(inmemory))["admission_authority"].status == "OK"
    real = build_adapters(Settings(gov_adapter="real", allow_real_gov_apis=False))
    with pytest.raises(RealAdapterDisabled):
        await real.admission_authority.joinings(
            institution_code="1-ABC-0001", academic_year="2026-27"
        )
    assert (await ping_all(real))["admission_authority"].status == "DISABLED"
