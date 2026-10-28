import httpx
import respx

MOCKGOV = "http://mockgov.test"


async def test_admin_routes_are_admin_only(ro_west, registrar_abc, student, university):
    for c in (ro_west, registrar_abc, student, university):
        for path in ("/admin/audit", "/admin/audit/verify", "/admin/adapters/ping", "/admin/chaos"):
            response = await c.get(path)
            assert response.status_code == 403, path
            assert response.json()["error"]["details"] == {"required_roles": ["AICTE_ADMIN"]}
        assert (await c.post("/admin/chaos/reset")).status_code == 403
        assert (await c.post("/admin/demo/reset")).status_code == 403


async def test_audit_list_and_verify(admin):
    verify = (await admin.get("/admin/audit/verify")).json()
    assert verify["ok"] is True and verify["first_broken_seq"] is None
    assert verify["length"] > 0 and verify["checked_at"].endswith("Z")

    page = (await admin.get("/admin/audit", params={"page_size": 5})).json()
    assert page["page_size"] == 5 and len(page["items"]) == 5
    assert page["total"] == verify["length"] or page["total"] >= verify["length"]
    seqs = [row["seq"] for row in page["items"]]
    assert seqs == sorted(seqs, reverse=True)
    row = page["items"][0]
    assert set(row) == {
        "seq",
        "at",
        "actor_id",
        "actor_email",
        "action",
        "entity_type",
        "entity_id",
        "hash",
        "prev_hash",
    }
    assert row["at"].endswith("Z") and len(row["hash"]) == 64

    seed_rows = (await admin.get("/admin/audit", params={"entity_type": "upload_file"})).json()
    assert seed_rows["total"] == 4  # three initial files and one update file
    assert all(r["action"] == "SEED" and r["actor_id"] is None for r in seed_rows["items"])

    me = (await admin.get("/me")).json()["user"]
    mine = (await admin.get("/admin/audit", params={"actor_id": me["id"]})).json()
    assert mine["total"] >= 1 and all(r["actor_email"] == "admin@aicte.demo" for r in mine["items"])
    assert any(r["action"] == "LOGIN" for r in mine["items"])


async def test_adapters_ping_inmemory(admin):
    body = (await admin.get("/admin/adapters/ping")).json()
    assert body["adapter"] == "inmemory"
    assert set(body["sources"]) == {"apaar", "counselling", "abc", "digilocker", "sii"}
    for source in body["sources"].values():
        assert source["status"] == "OK" and source["detail"] is None
        assert isinstance(source["latency_ms"], int)
    assert body["checked_at"].endswith("Z")


@respx.mock(base_url=MOCKGOV)
async def test_chaos_passthrough_is_forwarded_and_audited(admin, respx_mock):
    state = {"apaar": {"latency_ms": 0, "fail_rate": 0.0, "down": False}}
    respx_mock.get("/admin/chaos").mock(return_value=httpx.Response(200, json=state))
    set_route = respx_mock.post("/admin/chaos").mock(
        return_value=httpx.Response(
            200, json={"apaar": {"latency_ms": 2500, "fail_rate": 0.0, "down": True}}
        )
    )
    respx_mock.post("/admin/chaos/reset").mock(return_value=httpx.Response(200, json=state))

    assert (await admin.get("/admin/chaos")).json() == state
    response = await admin.post(
        "/admin/chaos", json={"source": "apaar", "latency_ms": 2500, "fail_rate": 0.0, "down": True}
    )
    assert response.status_code == 200 and response.json()["apaar"]["down"] is True
    assert (
        set_route.calls[0].request.read()
        == b'{"source":"apaar","latency_ms":2500,"fail_rate":0.0,"down":true}'
    )
    assert (await admin.post("/admin/chaos/reset")).json() == state

    audit = (await admin.get("/admin/audit", params={"entity_type": "mockgov_chaos"})).json()
    assert [r["action"] for r in audit["items"]] == ["UPDATE", "UPDATE", "READ"]
    assert all(r["actor_email"] == "admin@aicte.demo" for r in audit["items"])


@respx.mock(base_url=MOCKGOV)
async def test_chaos_passthrough_when_mockgov_is_down(admin, respx_mock):
    respx_mock.get("/admin/chaos").mock(side_effect=httpx.ConnectError("refused"))
    response = await admin.get("/admin/chaos")
    assert response.status_code == 503
    body = response.json()["error"]
    assert body["code"] == "SOURCE_UNAVAILABLE" and body["details"]["source"] == "mockgov"


async def test_chaos_validation(admin):
    response = await admin.post("/admin/chaos", json={"source": "apaar", "fail_rate": 7})
    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"][0]["field"] == "fail_rate"


async def test_demo_reset_is_reserved(admin):
    response = await admin.post("/admin/demo/reset")
    assert response.status_code == 501
    assert response.json() == {
        "error": {"code": "NOT_IMPLEMENTED", "message": "Run make demo-reset.", "details": {}}
    }
