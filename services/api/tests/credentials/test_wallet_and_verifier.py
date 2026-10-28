"""The wallet and the verifier end to end over HTTP: issue, share, verify, expire, revoke,
tampering, pasted presentations, the public issuer endpoints and who may do what."""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from datetime import UTC, datetime, timedelta

from jwcrypto.jws import JWS
from sd_jwt.common import SDObj
from sd_jwt.issuer import SDJWTIssuer
from sd_jwt.verifier import SDJWTVerifier
from sqlalchemy import select, update

from app.credentials import keys, status_list
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.credential import CredentialPresentation
from tests.credentials.helpers import (
    b64,
    b64json,
    public,
    ravis_proof,
    signed_in,
    stored_presentation,
)

THREE = ["institution", "programme", "academic_year"]


async def _share(student, credential_id, fields=("academic_year",)) -> dict:
    response = await student.post(
        f"/credentials/{credential_id}/present", json={"fields": list(fields), "consent": True}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _age(presentation_id: str, minutes: int) -> None:
    async with session_factory()() as session:
        await session.execute(
            update(CredentialPresentation)
            .where(CredentialPresentation.id == uuid.UUID(presentation_id))
            .values(
                created_at=CredentialPresentation.created_at - timedelta(minutes=minutes),
                expires_at=CredentialPresentation.expires_at - timedelta(minutes=minutes),
            )
        )
        await session.commit()


async def _store(presentation_id: str, presentation: str) -> None:
    async with session_factory()() as session:
        await session.execute(
            update(CredentialPresentation)
            .where(CredentialPresentation.id == uuid.UUID(presentation_id))
            .values(presentation=presentation)
        )
        await session.commit()


async def test_issue_share_verify_expire_revoke(world):
    credential = await ravis_proof()
    async with signed_in("student@demo") as student, signed_in("admin@aicte.demo") as admin:
        [card] = (await student.get("/credentials")).json()["items"]
        assert card["id"] == str(credential.id) and card["status"] == "ACTIVE"
        assert card["holder_bound"] is True and card["shares"] == 0
        assert card["presentations"] == [] and card["last_verified_at"] is None
        assert [(d["key"], d["always"]) for d in card["disclosable"]] == [
            ("name", False),
            ("dob", False),
            ("apaar_masked", False),
            ("institution", True),
            ("programme", True),
            ("academic_year", False),
            ("year_of_study", False),
            ("countersigned", False),
        ]
        assert card["issuer"] == {"name": "Countersign", "url": "http://localhost:8000"}
        assert card["institution_name"] == "ABC College of Engineering"
        assert card["programme_name"] == "B.Tech Computer Science and Engineering"
        assert card["university_name"] is None and card["expires_at"] == "2027-08-31T18:29:59Z"

        share = await _share(student, credential.id)
        assert share["disclosed"] == THREE and share["total"] == 8

        async with public() as anyone:
            typed = share["code"].lower().replace("-", " ")
            response = await anyone.get(f"/verify/{typed}")
            assert response.status_code == 200
            body = response.json()
            assert body["result"] == "VALID" and body["method"] == "signature"
            assert body["kind"] == "ENROLMENT" and body["holder_bound"] is True
            assert body["institution_name"] == "ABC College of Engineering"
            assert body["disclosed"] == [
                {
                    "key": "institution",
                    "label": "Institution",
                    "value": "ABC College of Engineering (1-ABC-0001)",
                },
                {
                    "key": "programme",
                    "label": "Programme",
                    "value": "B.Tech Computer Science and Engineering (UG)",
                },
                {"key": "academic_year", "label": "Academic year", "value": "2026-27"},
            ]
            for undisclosed in ("Ravi", "2007", "4417", "Mar", "IDENTITY"):
                assert undisclosed not in response.text
            assert body["expires_at"] == share["expires_at"] and body["nonce"] is None
            assert body["revoked_at"] is None and body["status_checked_at"]
            assert body["issued_at"] == card["issued_at"].split(".")[0].rstrip("Z") + "Z"

            [listed] = (await student.get("/credentials")).json()["items"]
            assert listed["shares"] == 1 and listed["last_verified_at"] is not None
            assert listed["presentations"][0]["verify_count"] == 1
            assert listed["presentations"][0]["disclosed"] == THREE

            await _age(share["id"], 10)
            expired = (await anyone.get(f"/verify/{share['code']}")).json()
            assert expired["result"] == "EXPIRED"
            assert expired["disclosed"] == [] and expired["institution_name"] is None
            rows = (await student.get(f"/credentials/{credential.id}/presentations")).json()
            assert rows["items"][0]["state"] == "EXPIRED"
            assert rows["items"][0]["verify_count"] == 2
            assert "code" not in rows["items"][0] and "presentation" not in rows["items"][0]

            live = await _share(student, credential.id, ["name"])
            revoked = await admin.post(
                f"/credentials/{credential.id}/revoke",
                json={"reason": "Admission found to be fraudulent after inquiry."},
            )
            assert revoked.status_code == 200 and revoked.json()["status"] == "REVOKED"
            after = (await anyone.get(f"/verify/{live['code']}")).json()
            assert after["result"] == "REVOKED" and after["revoked_at"] is not None
            assert after["disclosed"] == [] and "fraudulent" not in json.dumps(after)

            for code in ("K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF", "not-a-code"):
                missing = await anyone.get(f"/verify/{code}")
                assert missing.status_code == 404
                assert missing.json() == {
                    "error": {
                        "code": "PRESENTATION_NOT_FOUND",
                        "message": "This code is not a Countersign proof.",
                        "details": {},
                    }
                }

    async with session_factory()() as session:
        reads = (
            (
                await session.execute(
                    select(AuditLog).where(AuditLog.entity_type == "credential_presentation")
                )
            )
            .scalars()
            .all()
        )
    verifier_reads = [r for r in reads if r.action.value == "READ"]
    assert [r.after["result"] for r in verifier_reads] == ["VALID", "EXPIRED", "REVOKED"]
    assert all(r.actor_id is None and len(r.after["ip_hash"]) == 16 for r in verifier_reads)
    assert all(r.after["via"] == "verifier" for r in verifier_reads)


async def test_tampering_and_borrowed_key_binding_are_invalid(world):
    credential = await ravis_proof()
    async with signed_in("student@demo") as student, public() as anyone:
        a = await _share(student, credential.id)
        b = await _share(student, credential.id)
        a_row = await stored_presentation(a["id"])
        b_row = await stored_presentation(b["id"])
        jwt, *disclosures, kb = a_row.presentation.split("~")

        # a disclosure changed after signing: academic_year now claims another year
        changed = []
        for d in disclosures:
            salt, key, value = b64json(d)
            changed.append(b64([salt, key, "2030-31"]) if key == "academic_year" else d)
        tampered = "~".join([jwt, *changed, kb])
        await _store(a["id"], tampered)
        assert (await anyone.get(f"/verify/{a['code']}")).json()["result"] == "INVALID"
        pasted = (await anyone.post("/verify", json={"presentation": tampered})).json()
        assert pasted["result"] == "INVALID" and pasted["kind"] is None

        # the same disclosures bound to code b: valid for b, never for a
        borrowed = "~".join([jwt, *disclosures, b_row.presentation.rsplit("~", 1)[1]])
        await _store(a["id"], borrowed)
        invalid = (await anyone.get(f"/verify/{a['code']}")).json()
        assert invalid["result"] == "INVALID"
        assert invalid["issuer"] is None and invalid["issued_at"] is None
        assert invalid["holder_bound"] is False and invalid["status_checked_at"] is None
        assert (await anyone.get(f"/verify/{b['code']}")).json()["result"] == "VALID"

        # a holder-bound proof without its key binding
        unbound = "~".join([jwt, *disclosures, ""])
        await _store(a["id"], unbound)
        assert (await anyone.get(f"/verify/{a['code']}")).json()["result"] == "INVALID"
        assert (await anyone.post("/verify", json={"presentation": unbound})).json()[
            "result"
        ] == "INVALID"

        # signed by someone else, or naming another issuer
        stranger = keys.generate()
        for claims, signer in (
            ({"iss": "http://localhost:8000"}, stranger),
            ({"iss": "https://elsewhere.example"}, stranger),
        ):
            forged = SDJWTIssuer(
                {
                    **claims,
                    "iat": int(time.time()),
                    "vct": "countersign:enrolment:v1",
                    "status": {"status_list": {"idx": 5, "uri": status_list.uri()}},
                    SDObj("name"): "Forged Name",
                },
                signer,
                extra_header_parameters={"typ": "dc+sd-jwt", "kid": signer["kid"]},
            ).sd_jwt_issuance
            result = (await anyone.post("/verify", json={"presentation": forged})).json()
            assert result["result"] == "INVALID" and "Forged" not in json.dumps(result)

        for garbage in ("eyJ", "a~b~c", "x" * 50):
            result = (await anyone.post("/verify", json={"presentation": garbage})).json()
            assert result["result"] == "INVALID"
        too_long = await anyone.post("/verify", json={"presentation": "x" * 16_385})
        assert too_long.status_code == 422
        assert (await anyone.post("/verify", json={"presentation": ""})).status_code == 422

    async with session_factory()() as session:
        pastes = (
            (
                await session.execute(
                    select(AuditLog).where(AuditLog.after["via"].astext == "verifier-paste")
                )
            )
            .scalars()
            .all()
        )
    linked = [p for p in pastes if p.entity_id is not None]
    assert {p.entity_id for p in linked} == {credential.id}
    assert any(p.entity_id is None and p.entity_type == "credential" for p in pastes)


async def test_a_pasted_presentation_reports_its_nonce(world, monkeypatch):
    credential = await ravis_proof()
    async with signed_in("student@demo") as student, public() as anyone:
        share = await _share(student, credential.id, ["name", "academic_year"])
        row = await stored_presentation(share["id"])
        body = (await anyone.post("/verify", json={"presentation": row.presentation})).json()
        assert body["result"] == "VALID" and body["nonce"] == share["code"]
        assert [d["key"] for d in body["disclosed"]] == [
            "name",
            "institution",
            "programme",
            "academic_year",
        ]
        assert body["expires_at"] == "2027-08-31T18:29:59Z" and body["holder_bound"] is True
        assert (await stored_presentation(share["id"])).verify_count == 1

        # an altered copy is not that share, so its counters stay put
        jwt, *disclosures, kb = row.presentation.split("~")
        fewer = "~".join([jwt, disclosures[0], kb])
        assert (await anyone.post("/verify", json={"presentation": fewer})).json()[
            "result"
        ] == "INVALID"
        assert (await stored_presentation(share["id"])).verify_count == 1

        # a key binding made more than 10 minutes ago
        import sd_jwt.holder as library_holder

        monkeypatch.setattr(library_holder, "time", lambda: time.time() - 11 * 60)
        old = await _share(student, credential.id)
        monkeypatch.undo()
        old_row = await stored_presentation(old["id"])
        stale = (await anyone.post("/verify", json={"presentation": old_row.presentation})).json()
        assert stale["result"] == "EXPIRED" and stale["disclosed"] == []


async def test_the_public_issuer_documents(world):
    credential = await ravis_proof()
    async with signed_in("admin@aicte.demo") as admin, public() as anyone:
        await admin.post(f"/credentials/{credential.id}/revoke", json={"reason": "Test revoke."})

        response = await anyone.get("/.well-known/jwks.json")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=300"
        jwks = response.json()
        assert [set(k) for k in jwks["keys"]] == [{"kty", "crv", "x", "y", "kid", "use", "alg"}]

        metadata = (await anyone.get("/.well-known/jwt-vc-issuer")).json()
        assert metadata == {
            "issuer": "http://localhost:8000",
            "jwks_uri": "http://localhost:8000/.well-known/jwks.json",
        }

        token = await anyone.get("/status-lists/1")
        assert token.status_code == 200
        assert token.headers["content-type"] == "application/statuslist+jwt"
        assert token.headers["cache-control"] == "public, max-age=60"
        jws = JWS()
        jws.deserialize(token.text)
        kid = b64json(token.text.split(".")[0])["kid"]
        jws.verify(keys.key_in(jwks, kid))
        payload = json.loads(jws.payload)
        bits = status_list.decode(payload["status_list"]["lst"])
        assert status_list.bit(bits, credential.status_list_index) == 1
        assert sum(bin(b).count("1") for b in bits) == 1

        for other in ("2", "0", "abc"):
            missing = await anyone.get(f"/status-lists/{other}")
            assert missing.status_code == 404
            assert missing.json()["error"]["message"] == "Status list not found."

        # the issued SD-JWT checks out against the fetched JWKS and nothing else
        verified = SDJWTVerifier(
            credential.sd_jwt,
            lambda iss, header: keys.key_in(jwks, header["kid"]),
        ).get_verified_payload()
        assert verified["name"] == "Ravi Kumar Sharma"


async def test_who_may_use_the_wallet(world):
    credential = await ravis_proof()
    async with (
        signed_in("student@demo") as student,
        signed_in("admin@aicte.demo") as admin,
        signed_in("ro.west@aicte.demo") as ro,
        signed_in("registrar@abc.edu.demo") as registrar,
        signed_in("coe@univ.demo") as university,
        public() as anyone,
    ):
        for client in (ro, registrar, university):
            assert (await client.get("/credentials")).status_code == 403
            assert (await client.get(f"/credentials/{credential.id}")).status_code == 403
        assert (await anyone.get("/credentials")).status_code == 401

        detail = (await student.get(f"/credentials/{credential.id}")).json()
        claims = {c["key"]: c["value"] for c in detail["claims"]}
        assert claims["name"] == "Ravi Kumar Sharma" and claims["dob"] == "21 Mar 2007"
        assert claims["apaar_masked"] == "XXXX XXXX 4417"
        assert claims["expires"] == "31 Aug 2027"
        unknown = await student.get(f"/credentials/{uuid.uuid4()}")
        assert unknown.status_code == 404
        assert unknown.json()["error"]["message"] == "Credential not found."

        present = f"/credentials/{credential.id}/present"
        assert (await admin.post(present, json={"fields": [], "consent": True})).status_code == 403
        bad_shape = await student.post(present, json={"fields": "name", "consent": True})
        assert bad_shape.status_code == 422
        no_consent = await student.post(present, json={"fields": ["name"], "consent": False})
        assert no_consent.status_code == 422
        assert no_consent.json()["error"]["details"]["fields"] == [
            {"field": "consent", "message": "Agree to the share text to create a proof."}
        ]
        unknown_field = await student.post(present, json={"fields": ["gpa"], "consent": True})
        assert unknown_field.json()["error"]["message"] == "fields: unknown field: gpa."
        minimal = await _share(student, credential.id, [])
        assert minimal["disclosed"] == ["institution", "programme"]

        revoke = f"/credentials/{credential.id}/revoke"
        assert (await student.post(revoke, json={"reason": "Not mine."})).status_code == 403
        assert (await admin.post(revoke, json={"reason": "No"})).status_code == 422
        assert (await admin.post(revoke, json={"reason": "FLAG_CONFIRMED"})).status_code == 422
        assert (await admin.post(revoke, json={"reason": "Fraud found."})).status_code == 200
        again = await admin.post(revoke, json={"reason": "Fraud found."})
        assert again.status_code == 409
        assert again.json()["error"]["message"] == "This proof is already revoked."

        refused = await student.post(present, json={"fields": [], "consent": False})
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "CREDENTIAL_REVOKED"

        everything = (await admin.get("/credentials")).json()
        assert everything["total"] == 1
        for params, total in (
            ({"status": "REVOKED"}, 1),
            ({"status": "ACTIVE"}, 0),
            ({"kind": "DEGREE"}, 0),
            ({"student_id": str(credential.student_id)}, 1),
            ({"enrolment_id": str(uuid.uuid4())}, 0),
        ):
            assert (await admin.get("/credentials", params=params)).json()["total"] == total
        # a student's filters are ignored
        own = await student.get("/credentials", params={"status": "ACTIVE"})
        assert own.json()["total"] == 1
        history = (await admin.get(f"/credentials/{credential.id}/presentations")).json()
        assert history["total"] == 1


async def test_the_status_list_and_jwks_alone_verify_a_share(world):
    """A third party with only the published documents reaches the same answer."""
    credential = await ravis_proof()
    async with signed_in("student@demo") as student, public() as anyone:
        share = await _share(student, credential.id)
        presentation = (await stored_presentation(share["id"])).presentation
        jwks = (await anyone.get("/.well-known/jwks.json")).json()
        verified = SDJWTVerifier(
            presentation,
            lambda iss, header: keys.key_in(jwks, header["kid"]),
            expected_aud="http://localhost:8000/verify",
            expected_nonce=share["code"],
        ).get_verified_payload()
        assert set(verified) >= set(THREE) and "name" not in verified
        token = (await anyone.get("/status-lists/1")).text
        lst = b64json(token.split(".")[1])["status_list"]["lst"]
        index = verified["status"]["status_list"]["idx"]
        assert status_list.bit(status_list.decode(lst), index) == 0
        digest = base64.urlsafe_b64encode(
            hashlib.sha256(presentation.rsplit("~", 1)[0].encode() + b"~").digest()
        ).rstrip(b"=")
        assert b64json(presentation.rsplit("~", 1)[1].split(".")[1])["sd_hash"] == digest.decode()
        assert datetime.fromtimestamp(verified["exp"], UTC).year == 2027


async def test_public_routes_are_rate_limited(world):
    from app.core.ratelimit import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        async with public() as anyone:
            codes = [
                (await anyone.get("/verify/K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF")).status_code
                for _ in range(61)
            ]
            assert codes[:60] == [404] * 60 and codes[60] == 429
            limited = await anyone.post("/verify", json={"presentation": "x"})
            assert limited.status_code == 429
            assert limited.json()["error"]["details"]["retry_after"] == 60
            issuer_codes = [
                (await anyone.get("/.well-known/jwt-vc-issuer")).status_code for _ in range(121)
            ]
            assert issuer_codes[:120] == [200] * 120 and issuer_codes[120] == 429
    finally:
        limiter.enabled = False
        limiter.reset()


async def test_shares_are_limited_per_student(world):
    from app.core.ratelimit import limiter

    credential = await ravis_proof()
    limiter.enabled = True
    limiter.reset()
    try:
        async with signed_in("student@demo") as student:
            codes = [
                (
                    await student.post(
                        f"/credentials/{credential.id}/present",
                        json={"fields": [], "consent": True},
                    )
                ).status_code
                for _ in range(11)
            ]
        assert codes == [201] * 10 + [429]
    finally:
        limiter.enabled = False
        limiter.reset()
