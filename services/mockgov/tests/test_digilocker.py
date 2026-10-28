from httpx import AsyncClient

NOTICE = {
    "apaar_id": "123456784417",
    "message": "ABC College of Engineering says you joined B.Tech CSE (2026-27). Is that right?",
    "callback_url": "http://localhost:3000/student/notices/tok_abc123",
}


async def test_notify_delivers_to_a_linked_id(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/digilocker/notify", json=NOTICE)
    assert response.status_code == 202
    body = response.json()
    assert body["delivered"] is True
    assert body["inbox_id"].startswith("ib_")
    assert len(body["inbox_id"]) == 3 + 26


async def test_notify_unlinked_id(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/digilocker/notify", json={**NOTICE, "apaar_id": "000000000000"})
    assert response.status_code == 200
    assert response.json() == {"delivered": False, "inbox_id": None, "reason": "APAAR_NOT_LINKED"}


async def test_inbox_lists_newest_first(client: AsyncClient, seeded: dict) -> None:
    first = (await client.post("/digilocker/notify", json=NOTICE)).json()["inbox_id"]
    second = (
        await client.post("/digilocker/notify", json={**NOTICE, "message": "Second notice"})
    ).json()["inbox_id"]

    response = await client.get(f"/digilocker/inbox/{NOTICE['apaar_id']}")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [i["inbox_id"] for i in items] == [second, first]
    assert items[1] == {
        "inbox_id": first,
        "message": NOTICE["message"],
        "callback_url": NOTICE["callback_url"],
        "received_at": items[1]["received_at"],
        "read": False,
    }
    assert items[1]["received_at"].endswith("Z")


async def test_inbox_is_empty_for_an_id_with_no_notices(client: AsyncClient, seeded: dict) -> None:
    response = await client.get("/digilocker/inbox/123456780003")
    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_inbox_path_must_be_an_apaar_id(client: AsyncClient) -> None:
    response = await client.get("/digilocker/inbox/abc")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_notify_validation(client: AsyncClient) -> None:
    response = await client.post("/digilocker/notify", json={"apaar_id": "123456784417"})
    assert response.status_code == 422
    fields = {f["field"] for f in response.json()["error"]["details"]["fields"]}
    assert fields == {"message", "callback_url"}
