"""POST /psi/compute (D48, API_CONTRACT §A4.26): AICTE_ADMIN only, counts only, one audit row.

The PSI client is replaced by an httpx MockTransport that answers like the psi-client
service, so these tests need neither the amd64 image nor openmined.psi. The protocol itself
is tested in services/psi.
"""

from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import func, select

from app.core.crypto import hmac_id
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import ConsentStatus
from app.models.student import Student
from app.psi import service
from tests.conftest import login_as

pytestmark = pytest.mark.usefixtures("seeded")


@pytest.fixture
def psi_client(monkeypatch):
    """Answers POST /psi/compute like services/psi in the client role, and records the call."""
    calls: list[dict] = []
    answer = {"status": 200, "partner_count": 500, "overlap": 7}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append({"url": str(request.url), "body": body})
        if answer["status"] != 200:
            return httpx.Response(
                answer["status"], json={"error": {"code": "PARTNER_UNAVAILABLE", "message": ""}}
            )
        return httpx.Response(
            200,
            json={
                "countersign_count": len(set(body["items"])),
                "partner_count": answer["partner_count"],
                "overlap": answer["overlap"],
            },
        )

    def http_client() -> httpx.AsyncClient:
        settings = service.get_settings()
        return httpx.AsyncClient(
            base_url=settings.psi_client_url, transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(service, "_http_client", http_client)
    return calls, answer


async def _psi_audit_rows() -> list[AuditLog]:
    async with session_factory()() as session:
        rows = await session.execute(
            select(AuditLog).where(AuditLog.entity_type == "psi_run").order_by(AuditLog.seq)
        )
        return list(rows.scalars())


async def _linked_count() -> int:
    async with session_factory()() as session:
        stmt = select(func.count()).where(
            Student.consent_status == ConsentStatus.LINKED, Student.apaar_hmac.is_not(None)
        )
        return (await session.execute(stmt)).scalar_one()


async def test_the_officer_learns_three_counts_and_the_run_is_audited(admin, psi_client):
    calls, _ = psi_client
    before = len(await _psi_audit_rows())

    response = await admin.post("/psi/compute")

    assert response.status_code == 200, response.text
    body = response.json()
    linked = await _linked_count()
    assert linked > 0
    assert body["countersign_count"] == linked
    assert (body["partner_count"], body["overlap"]) == (500, 7)
    assert body["method"] == "ECDH PSI cardinality (OpenMined)"
    assert body["computed_at"].endswith("Z")
    assert set(body) == {"countersign_count", "partner_count", "overlap", "computed_at", "method"}

    # the set goes only to Countersign's own PSI client, as APAAR HMACs of linked students
    assert len(calls) == 1
    assert calls[0]["url"] == "http://psi-client:8002/psi/compute"
    items = calls[0]["body"]["items"]
    assert len(items) == linked == len(set(items))
    async with session_factory()() as session:
        digests = (
            await session.execute(
                select(Student.apaar_hmac).where(
                    Student.consent_status == ConsentStatus.LINKED,
                    Student.apaar_hmac.is_not(None),
                )
            )
        ).scalars()
        assert set(items) == {d.hex() for d in digests}
    assert all(len(i) == 64 for i in items)

    rows = await _psi_audit_rows()
    assert len(rows) == before + 1
    row = rows[-1]
    assert row.action.value == "CREATE"
    assert row.actor_id is not None
    assert row.after == {**body, "partner": "UGC (mock)"}
    assert not set(items) & set(map(str, row.after.values()))


async def test_the_items_are_the_digests_the_partner_computes(admin, psi_client):
    calls, _ = psi_client
    async with session_factory()() as session:
        student = (
            await session.execute(
                select(Student).where(Student.consent_status == ConsentStatus.LINKED).limit(1)
            )
        ).scalar_one()
    from app.core.crypto import decrypt

    apaar = decrypt(student.apaar_encrypted)
    assert (await admin.post("/psi/compute")).status_code == 200
    assert hmac_id(apaar, "apaar") in calls[0]["body"]["items"]


@pytest.mark.parametrize(
    "email",
    ["ro.west@aicte.demo", "registrar@abc.edu.demo", "student@demo", "coe@univ.demo"],
)
async def test_only_the_aicte_officer_may_compute(email, psi_client):
    calls, _ = psi_client
    c = await login_as(email)
    try:
        response = await c.post("/psi/compute")
    finally:
        await c.aclose()
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert response.json()["error"]["details"]["required_roles"] == ["AICTE_ADMIN"]
    assert calls == []


async def test_signed_out_is_a_401(client, psi_client):
    calls, _ = psi_client
    assert (await client.post("/psi/compute")).status_code == 401
    assert calls == []


async def test_a_partner_that_does_not_answer_is_a_503_and_nothing_is_audited(admin, psi_client):
    _, answer = psi_client
    answer["status"] = 502
    before = len(await _psi_audit_rows())
    response = await admin.post("/psi/compute")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "PSI_UNAVAILABLE"
    assert error["details"] == {"source": "psi", "detail": "PARTNER_UNAVAILABLE"}
    assert len(await _psi_audit_rows()) == before


async def test_an_answer_that_does_not_add_up_is_refused(admin, psi_client):
    _, answer = psi_client
    answer["overlap"] = 10**9
    response = await admin.post("/psi/compute")
    assert response.status_code == 503
    assert response.json()["error"]["details"]["detail"] == "BAD_ANSWER"


async def test_an_unreachable_psi_client_is_a_503(admin, monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: _Unreachable())
    response = await admin.post("/psi/compute")
    assert response.status_code == 503
    assert response.json()["error"]["details"]["detail"] == "ConnectError"


class _Unreachable:
    psi_client_url = "http://127.0.0.1:9"
    psi_timeout_seconds = 2.0
