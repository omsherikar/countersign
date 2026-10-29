"""HTTP adapters for services/mockgov (API_CONTRACT §C). 3 s timeout, one retry."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.adapters import digilocker_oidc
from app.adapters.base import (
    PROBE_APAAR_ID,
    AbcResult,
    AdapterRequestError,
    ApaarResult,
    CounsellingResult,
    DigiLockerIdentity,
    DigiLockerResult,
    IdTokenInvalid,
    Semester,
    SiiResult,
    SourceUnavailable,
)

DEFAULT_TIMEOUT = 3.0
RETRIES = 1


class MockGovClient:
    """Shared httpx client; maps timeouts, connection errors and 5xx to SourceUnavailable."""

    def __init__(
        self,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client or httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        source: str,
        method: str,
        path: str,
        json: Any | None = None,
        *,
        data: dict[str, str] | None = None,
    ) -> Any:
        """`json` for mockgov's own routes; `data` sends a form (the DigiLocker token call)."""
        last_error: SourceUnavailable | None = None
        for _attempt in range(RETRIES + 1):
            try:
                response = await self._client.request(method, path, json=json, data=data)
            except httpx.TimeoutException:
                last_error = SourceUnavailable(
                    source, f"timeout after {int(self.timeout * 1000)} ms"
                )
                continue
            except httpx.TransportError as exc:
                last_error = SourceUnavailable(
                    source, f"connection error: {exc.__class__.__name__}"
                )
                continue
            if response.status_code >= 500:
                last_error = SourceUnavailable(source, f"HTTP {response.status_code}")
                continue
            if response.status_code >= 400:
                raise AdapterRequestError(source, response.status_code, response.text)
            return response.json()
        assert last_error is not None
        raise last_error


class _MockGovBase:
    source: str = ""

    def __init__(self, client: MockGovClient) -> None:
        self.client = client


class MockGovApaar(_MockGovBase):
    source = "apaar"

    async def verify(self, apaar_id: str, name: str, dob: date) -> ApaarResult:
        data = await self.client.request(
            self.source,
            "POST",
            "/apaar/verify",
            {"apaar_id": apaar_id, "name": name, "dob": dob.isoformat()},
        )
        return ApaarResult(
            exists=bool(data["exists"]),
            name_score=int(data.get("name_score") or 0),
            dob_match=bool(data.get("dob_match")),
        )

    async def ping(self) -> None:
        await self.verify(PROBE_APAAR_ID, "probe", date(2000, 1, 1))


class MockGovCounselling(_MockGovBase):
    source = "counselling"

    async def verify(
        self,
        *,
        state: str,
        year: int,
        name: str,
        dob: date,
        programme: str,
        roll_no: str | None = None,
        institution_aicte_id: str | None = None,
    ) -> CounsellingResult:
        body: dict[str, Any] = {
            "state": state,
            "year": year,
            "name": name,
            "dob": dob.isoformat(),
            "programme": programme,
        }
        if roll_no is not None:
            body["roll_no"] = roll_no
        if institution_aicte_id is not None:
            body["institution_aicte_id"] = institution_aicte_id
        data = await self.client.request(self.source, "POST", "/counselling/verify", body)
        return CounsellingResult(
            found=bool(data["found"]),
            round=data.get("round"),
            category=data.get("category"),
            allotment_ref=data.get("allotment_ref"),
        )

    async def ping(self) -> None:
        await self.verify(
            state="MH", year=2026, name="probe", dob=date(2000, 1, 1), programme="CSE"
        )


class MockGovAbc(_MockGovBase):
    source = "abc"

    async def credits(self, apaar_id: str, academic_year: str) -> AbcResult:
        data = await self.client.request(
            self.source,
            "POST",
            "/abc/credits",
            {"apaar_id": apaar_id, "academic_year": academic_year},
        )
        return AbcResult(
            apaar_id_known=bool(data["apaar_id_known"]),
            semesters=[
                Semester(
                    sem=int(s["sem"]),
                    credits=int(s["credits"]),
                    uploaded_at=s.get("uploaded_at"),
                    result=s.get("result", "PENDING"),
                )
                for s in data.get("semesters", [])
            ],
        )

    async def ping(self) -> None:
        await self.credits(PROBE_APAAR_ID, "2026-27")


class MockGovDigiLocker(_MockGovBase):
    source = "digilocker"

    def __init__(
        self, client: MockGovClient, oauth: digilocker_oidc.OAuthClient | None = None
    ) -> None:
        super().__init__(client)
        self.oauth = oauth

    def _oauth(self) -> digilocker_oidc.OAuthClient:
        return self.oauth or digilocker_oidc.OAuthClient.from_settings()

    def authorize_url(self, *, state: str, nonce: str, redirect_uri: str) -> str:
        """The simulator's sign-in page, which the browser opens (DIGILOCKER_AUTHORIZE_URL)."""
        return digilocker_oidc.authorize_url(
            self._oauth(), state=state, nonce=nonce, redirect_uri=redirect_uri
        )

    async def exchange_code(
        self, *, code: str, redirect_uri: str, nonce: str
    ) -> DigiLockerIdentity:
        """POST /digilocker/oauth/token (API_CONTRACT C.12), then verify the id token. OAuth
        errors arrive as AdapterRequestError; an outage as SourceUnavailable."""
        oauth = self._oauth()
        data = await self.client.request(
            self.source,
            "POST",
            "/digilocker/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": oauth.client_id,
                "client_secret": oauth.client_secret,
            },
        )
        token = data.get("id_token") if isinstance(data, dict) else None
        if not isinstance(token, str):
            raise IdTokenInvalid("no id_token in the answer")
        return digilocker_oidc.read_id_token(token, oauth, nonce=nonce)

    async def notify(self, apaar_id: str, message: str, callback_url: str) -> DigiLockerResult:
        data = await self.client.request(
            self.source,
            "POST",
            "/digilocker/notify",
            {"apaar_id": apaar_id, "message": message, "callback_url": callback_url},
        )
        return DigiLockerResult(
            delivered=bool(data["delivered"]),
            inbox_id=data.get("inbox_id"),
            reason=data.get("reason"),
        )

    async def inbox(self, apaar_id: str) -> list[dict[str, Any]]:
        data = await self.client.request(self.source, "GET", f"/digilocker/inbox/{apaar_id}")
        return list(data.get("items", []))

    async def ping(self) -> None:
        await self.inbox(PROBE_APAAR_ID)


class MockGovSii(_MockGovBase):
    source = "sii"

    async def verify(self, passport_no: str, name: str, nationality: str) -> SiiResult:
        data = await self.client.request(
            self.source,
            "POST",
            "/sii/verify",
            {"passport_no": passport_no, "name": name, "nationality": nationality},
        )
        return SiiResult(
            admitted=bool(data["admitted"]),
            institution_aicte_id=data.get("institution_aicte_id"),
            programme=data.get("programme"),
            academic_year=data.get("academic_year"),
        )

    async def ping(self) -> None:
        await self.verify("X0000000", "probe", "XX")
