import time

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.chaos import SOURCES
from app.config import Settings
from app.main import create_app, startup

ZERO = {"latency_ms": 0, "fail_rate": 0.0, "down": False}
APAAR = {"apaar_id": "123456784417", "name": "Ravi Kumar Sharma", "dob": "2007-03-21"}

SOURCE_CALLS = {
    "apaar": ("post", "/apaar/verify", APAAR),
    "counselling": (
        "post",
        "/counselling/verify",
        {"state": "MH", "year": 2026, "name": "Ravi", "dob": "2007-03-21", "programme": "CSE"},
    ),
    "abc": ("post", "/abc/credits", {"apaar_id": "123456784417", "academic_year": "2025-26"}),
    "digilocker": ("get", "/digilocker/inbox/123456784417", None),
    "sii": ("post", "/sii/verify", {"passport_no": "N1", "name": "A", "nationality": "BD"}),
    "admission_authority": (
        "get",
        "/admission-authority/joinings?institution_code=1-ABC-0001&academic_year=2026-27",
        None,
    ),
}


async def call(client: AsyncClient, source: str):
    method, path, body = SOURCE_CALLS[source]
    if method == "get":
        return await client.get(path)
    return await client.post(path, json=body)


async def test_defaults_are_all_zero(client: AsyncClient) -> None:
    response = await client.get("/admin/chaos")
    assert response.status_code == 200
    assert response.json() == {source: ZERO for source in SOURCES}


async def test_set_one_source_returns_only_that_source(client: AsyncClient) -> None:
    response = await client.post(
        "/admin/chaos", json={"source": "apaar", "latency_ms": 2500, "fail_rate": 0.0, "down": True}
    )
    assert response.status_code == 200
    assert response.json() == {"apaar": {"latency_ms": 2500, "fail_rate": 0.0, "down": True}}

    everything = (await client.get("/admin/chaos")).json()
    assert everything["apaar"] == {"latency_ms": 2500, "fail_rate": 0.0, "down": True}
    assert everything["sii"] == ZERO


async def test_set_all_sources(client: AsyncClient) -> None:
    response = await client.post("/admin/chaos", json={"source": "all", "fail_rate": 0.5})
    assert response.json() == {
        source: {"latency_ms": 0, "fail_rate": 0.5, "down": False} for source in SOURCES
    }


async def test_unknown_source_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/admin/chaos", json={"source": "passport", "down": True})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_fail_rate_must_be_a_probability(client: AsyncClient) -> None:
    response = await client.post("/admin/chaos", json={"source": "apaar", "fail_rate": 1.5})
    assert response.status_code == 422


async def test_reset_restores_defaults(client: AsyncClient) -> None:
    await client.post("/admin/chaos", json={"source": "all", "latency_ms": 10, "down": True})
    response = await client.post("/admin/chaos/reset")
    assert response.status_code == 200
    assert response.json() == {source: ZERO for source in SOURCES}


@pytest.mark.parametrize("source", SOURCES)
async def test_down_returns_503_envelope(client: AsyncClient, source: str) -> None:
    await client.post("/admin/chaos", json={"source": source, "down": True})
    response = await call(client, source)
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "SOURCE_DOWN"
    assert body["error"]["message"].endswith("unavailable.")
    assert body["error"]["details"] == {}


async def test_apaar_down_message(client: AsyncClient) -> None:
    await client.post("/admin/chaos", json={"source": "apaar", "down": True})
    response = await call(client, "apaar")
    assert response.json()["error"]["message"] == "APAAR registry unavailable."


async def test_down_source_does_not_affect_others(client: AsyncClient, seeded: dict) -> None:
    await client.post("/admin/chaos", json={"source": "apaar", "down": True})
    assert (await call(client, "apaar")).status_code == 503
    assert (await call(client, "abc")).status_code == 200


async def test_fail_rate_one_always_fails(client: AsyncClient) -> None:
    await client.post("/admin/chaos", json={"source": "abc", "fail_rate": 1.0})
    for _ in range(5):
        assert (await call(client, "abc")).status_code == 503


async def test_fail_rate_zero_never_fails(client: AsyncClient, seeded: dict) -> None:
    await client.post("/admin/chaos", json={"source": "abc", "fail_rate": 0.0})
    for _ in range(5):
        assert (await call(client, "abc")).status_code == 200


async def test_latency_is_applied(client: AsyncClient, seeded: dict) -> None:
    await client.post("/admin/chaos", json={"source": "sii", "latency_ms": 300})
    started = time.perf_counter()
    response = await call(client, "sii")
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert elapsed >= 0.3


async def test_latency_applies_before_a_down_answer(client: AsyncClient) -> None:
    await client.post("/admin/chaos", json={"source": "sii", "latency_ms": 200, "down": True})
    started = time.perf_counter()
    response = await call(client, "sii")
    assert response.status_code == 503
    assert time.perf_counter() - started >= 0.2


async def test_admin_and_healthz_ignore_chaos(client: AsyncClient) -> None:
    await client.post("/admin/chaos", json={"source": "all", "latency_ms": 5000, "down": True})
    started = time.perf_counter()
    health = await client.get("/healthz")
    chaos = await client.get("/admin/chaos")
    reset = await client.post("/admin/chaos/reset")
    assert time.perf_counter() - started < 1.0
    assert health.status_code == 200
    assert health.json()["chaos"]["apaar"]["down"] is True
    assert chaos.status_code == 200
    assert reset.status_code == 200


async def test_chaos_survives_a_restart(
    client: AsyncClient, app: FastAPI, settings: Settings
) -> None:
    await client.post(
        "/admin/chaos", json={"source": "counselling", "latency_ms": 50, "down": True}
    )

    restarted = create_app(settings)
    await startup(restarted)
    try:
        transport = ASGITransport(app=restarted)
        async with AsyncClient(transport=transport, base_url="http://mockgov") as fresh:
            state = (await fresh.get("/admin/chaos")).json()
            assert state["counselling"] == {"latency_ms": 50, "fail_rate": 0.0, "down": True}
            assert state["apaar"] == ZERO
            assert (await call(fresh, "counselling")).status_code == 503
    finally:
        await restarted.state.db.dispose()


async def test_env_defaults_seed_every_source(settings: Settings) -> None:
    custom = settings.model_copy(update={"mockgov_latency_ms": 20, "mockgov_fail_rate": 0.25})
    application = create_app(custom)
    try:
        state = application.state.chaos.snapshot()
        assert state["apaar"] == {"latency_ms": 20, "fail_rate": 0.25, "down": False}
        application.state.chaos.set("apaar", 0, 0.0, True)
        application.state.chaos.reset()
        assert application.state.chaos.snapshot()["apaar"] == {
            "latency_ms": 20,
            "fail_rate": 0.25,
            "down": False,
        }
    finally:
        await application.state.db.dispose()


async def test_an_older_chaos_table_is_widened_for_the_admission_authority(app: FastAPI) -> None:
    """Databases created before the admission authority had a 16-character source column."""
    from sqlalchemy import text

    async with app.state.db.engine.begin() as conn:
        await conn.execute(text("DELETE FROM chaos"))
        await conn.execute(text("ALTER TABLE chaos ALTER COLUMN source TYPE varchar(16)"))
    await app.state.db.create_all()
    async with app.state.db.sessions() as session:
        await app.state.chaos.save(session)
        width = await session.scalar(
            text(
                "SELECT character_maximum_length FROM information_schema.columns "
                "WHERE table_name = 'chaos' AND column_name = 'source'"
            )
        )
    assert width == 32
