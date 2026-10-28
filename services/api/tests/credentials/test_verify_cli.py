"""The standalone verifier reaches the api's answer from the public documents alone."""

from __future__ import annotations

import asyncio
import json

import httpx
import respx

from app.credentials import verify_cli
from tests.credentials.helpers import public, ravis_proof, signed_in, stored_presentation

JWKS = "http://test/.well-known/jwks.json"
STATUS = "http://test/status-lists/1"


async def test_a_third_party_needs_only_the_published_documents(world, capsys):
    credential = await ravis_proof()
    async with signed_in("student@demo") as student, signed_in("admin@aicte.demo") as admin:
        share = (
            await student.post(
                f"/credentials/{credential.id}/present",
                json={"fields": ["academic_year"], "consent": True},
            )
        ).json()
        presentation = (await stored_presentation(share["id"])).presentation

        async with public() as anyone:
            result = await verify_cli.verify(
                presentation,
                jwks_url=JWKS,
                status_url=STATUS,
                client=anyone,
                issuer="http://localhost:8000",
            )
            assert result["result"] == "VALID" and result["kind"] == "ENROLMENT"
            assert result["nonce"] == share["code"] and result["holder_bound"] is True
            assert set(result["disclosed"]) == {"institution", "programme", "academic_year"}
            api = (await anyone.post("/verify", json={"presentation": presentation})).json()
            assert api["result"] == result["result"]

            jwt, *disclosures, kb = presentation.split("~")
            wrong = await verify_cli.verify(
                "~".join([jwt, *disclosures[:-1], kb]),
                jwks_url=JWKS,
                status_url=STATUS,
                client=anyone,
                issuer="http://localhost:8000",
            )
            assert wrong["result"] == "INVALID" and wrong["disclosed"] == {}
            stranger = await verify_cli.verify(
                presentation,
                jwks_url=JWKS,
                status_url=STATUS,
                client=anyone,
                issuer="https://elsewhere.example",
            )
            assert stranger["result"] == "INVALID"

            await admin.post(f"/credentials/{credential.id}/revoke", json={"reason": "Test it."})
            jwks = (await anyone.get("/.well-known/jwks.json")).json()
            token = (await anyone.get("/status-lists/1")).text

    # the command line, against the same documents served from somewhere else
    with respx.mock:
        respx.get("https://issuer.example/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json=jwks)
        )
        respx.get("https://issuer.example/status-lists/1").mock(
            return_value=httpx.Response(200, text=token)
        )
        code = await asyncio.to_thread(
            verify_cli.main,
            [
                presentation,
                "--jwks-url",
                "https://issuer.example/.well-known/jwks.json",
                "--status-url",
                "https://issuer.example/status-lists/1",
                "--issuer",
                "http://localhost:8000",
            ],
        )
    printed = json.loads(capsys.readouterr().out)
    assert code == 1 and printed["result"] == "REVOKED" and printed["disclosed"] == {}
