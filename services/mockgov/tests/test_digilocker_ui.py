"""GET /digilocker/ui: the demo's HTML window on the mock DigiLocker inbox."""

from httpx import AsyncClient

APAAR = "123456784417"
NOTICE = {
    "apaar_id": APAAR,
    "message": "ABC College of Engineering says you joined B.Tech CSE (2026-27). Is that right?",
    "callback_url": "http://localhost:3000/student/notices/tok_first",
}


async def page(client: AsyncClient, apaar_id: str | None = None):
    params = {} if apaar_id is None else {"apaar_id": apaar_id}
    return await client.get("/digilocker/ui", params=params)


def assert_self_contained(response) -> None:
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "script-src" not in csp
    body = response.text
    assert "Mock DigiLocker" in body
    assert "Demo DigiLocker inbox, synthetic data" in body
    assert "<script" not in body and "<link" not in body and " src=" not in body


async def test_without_an_apaar_the_page_shows_the_form(client: AsyncClient) -> None:
    response = await page(client)
    assert response.status_code == 200
    assert_self_contained(response)
    assert '<form method="get"' in response.text and 'name="apaar_id"' in response.text
    assert "Inbox for" not in response.text


async def test_lists_messages_newest_first_with_a_respond_link(
    client: AsyncClient, seeded: dict
) -> None:
    await client.post("/digilocker/notify", json=NOTICE)
    second = {
        **NOTICE,
        "message": "XYZ Institute of Technology says you joined M.Tech VLSI Design (2026-27).",
        "callback_url": "http://localhost:3000/student/notices/tok_second",
    }
    await client.post("/digilocker/notify", json=second)

    response = await page(client, APAAR)
    assert response.status_code == 200
    assert_self_contained(response)
    body = response.text
    assert "Inbox for APAAR XXXX XXXX 4417" in body and APAAR not in body
    assert "2 messages, newest first" in body
    assert body.index("XYZ Institute") < body.index("ABC College of Engineering")
    assert body.index("tok_second") < body.index("tok_first")
    assert body.count(">Respond</a>") == 2
    assert 'href="http://localhost:3000/student/notices/tok_first"' in body
    assert " IST</time>" in body and '<time datetime="' in body


async def test_every_value_is_escaped(client: AsyncClient, seeded: dict) -> None:
    await client.post(
        "/digilocker/notify",
        json={
            **NOTICE,
            "message": "<script>alert(\"x\")</script> & 'quoted'",
            "callback_url": 'http://localhost:3000/student/notices/a"><img src=x onerror=alert(1)>',
        },
    )
    body = (await page(client, APAAR)).text
    assert "<script" not in body and "<img" not in body
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &#x27;quoted&#x27;" in body
    assert (
        'href="http://localhost:3000/student/notices/a&quot;&gt;&lt;img src=x onerror=alert(1)&gt;"'
        in body
    )


async def test_a_link_that_is_not_http_gets_no_button(client: AsyncClient, seeded: dict) -> None:
    await client.post(
        "/digilocker/notify", json={**NOTICE, "callback_url": "javascript:alert(document.cookie)"}
    )
    body = (await page(client, APAAR)).text
    assert "javascript:" not in body
    assert ">Respond</a>" not in body
    assert "This message has no reply link." in body


async def test_an_apaar_that_is_not_12_digits_is_refused(client: AsyncClient) -> None:
    response = await page(client, "<b>12ab</b>")
    assert response.status_code == 422
    assert_self_contained(response)
    assert "Enter the 12-digit APAAR number." in response.text
    assert "<b>" not in response.text and "12ab" not in response.text


async def test_spaces_in_the_apaar_are_ignored(client: AsyncClient, seeded: dict) -> None:
    await client.post("/digilocker/notify", json=NOTICE)
    response = await page(client, "1234 5678 4417")
    assert response.status_code == 200
    assert "1 message, newest first" in response.text and ">Respond</a>" in response.text


async def test_an_apaar_with_no_account(client: AsyncClient, seeded: dict) -> None:
    response = await page(client, "000000000000")
    assert response.status_code == 200
    assert "No DigiLocker account is linked to this APAAR number." in response.text


async def test_an_account_with_no_messages(client: AsyncClient, seeded: dict) -> None:
    response = await page(client, "123456780003")
    assert response.status_code == 200
    assert "No messages yet." in response.text
    assert ">Respond</a>" not in response.text


async def test_the_page_stays_up_when_digilocker_is_down(client: AsyncClient, seeded: dict) -> None:
    """Chaos simulates the government API for the Countersign api, not the demo's viewer."""
    await client.post("/digilocker/notify", json=NOTICE)
    await client.post("/admin/chaos", json={"source": "digilocker", "down": True})
    assert (await client.get(f"/digilocker/inbox/{APAAR}")).status_code == 503
    response = await page(client, APAAR)
    assert response.status_code == 200 and ">Respond</a>" in response.text
