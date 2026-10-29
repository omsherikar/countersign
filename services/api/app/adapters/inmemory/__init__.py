"""In-memory adapters for unit tests: registries are plain dicts and lists."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import date

from rapidfuzz import fuzz

from app.adapters import digilocker_oidc
from app.adapters.base import (
    AbcResult,
    AdapterRequestError,
    ApaarResult,
    CounsellingResult,
    DigiLockerIdentity,
    DigiLockerResult,
    Semester,
    SiiResult,
    SourceUnavailable,
)
from app.core.crypto import normalise_name


class _Downable:
    """Mixin: flip `down` to make the fake source behave like an outage."""

    down: bool = False
    source: str = ""

    def _guard(self) -> None:
        if self.down:
            raise SourceUnavailable(self.source, "in-memory source marked down")

    async def ping(self) -> None:
        self._guard()


@dataclass
class InMemoryApaar(_Downable):
    """registry: {apaar_id: {"name": str, "dob": date}}"""

    registry: dict[str, dict] = field(default_factory=dict)
    source: str = "apaar"
    down: bool = False

    async def verify(self, apaar_id: str, name: str, dob: date) -> ApaarResult:
        self._guard()
        row = self.registry.get(apaar_id)
        if row is None:
            return ApaarResult(exists=False, name_score=0, dob_match=False)
        score = int(round(fuzz.token_set_ratio(normalise_name(name), normalise_name(row["name"]))))
        return ApaarResult(exists=True, name_score=score, dob_match=row["dob"] == dob)


@dataclass
class InMemoryCounselling(_Downable):
    """allotments: list of dicts shaped like datagen's counselling.jsonl rows."""

    allotments: list[dict] = field(default_factory=list)
    source: str = "counselling"
    down: bool = False

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
        self._guard()
        for row in self.allotments:
            if roll_no is not None:
                if row.get("roll_no") == roll_no:
                    return self._found(row)
                continue
            if (
                row.get("state") == state
                and int(row.get("year", 0)) == year
                and row.get("programme") == programme
                and str(row.get("dob")) == dob.isoformat()
                and fuzz.token_set_ratio(normalise_name(name), normalise_name(row["name"])) >= 90
            ):
                return self._found(row)
        return CounsellingResult(found=False)

    @staticmethod
    def _found(row: dict) -> CounsellingResult:
        return CounsellingResult(
            found=True,
            round=row.get("round"),
            category=row.get("category"),
            allotment_ref=row.get("allotment_ref"),
        )


@dataclass
class InMemoryAbc(_Downable):
    """credits: {apaar_id: {academic_year: [Semester-like dicts]}}"""

    credits_by_apaar: dict[str, dict[str, list[dict]]] = field(default_factory=dict)
    source: str = "abc"
    down: bool = False

    async def credits(self, apaar_id: str, academic_year: str) -> AbcResult:
        self._guard()
        years = self.credits_by_apaar.get(apaar_id)
        if years is None:
            return AbcResult(apaar_id_known=False)
        return AbcResult(
            apaar_id_known=True,
            semesters=[
                Semester(
                    sem=int(s["sem"]),
                    credits=int(s["credits"]),
                    uploaded_at=s.get("uploaded_at"),
                    result=s.get("result", "PENDING"),
                )
                for s in years.get(academic_year, [])
            ],
        )


@dataclass
class InMemoryDigiLocker(_Downable):
    """linked: set of APAAR ids that can receive notices; inbox collects deliveries.

    An APAAR with no DigiLocker account is a 404, as mockgov answers (API_CONTRACT §A3.28).

    Sign-in: `accounts` holds synthetic accounts {digilocker_id: {"name", "dob", "gender",
    "apaar_id"}}; `sign_in` is what the Demo DigiLocker page does after the OTP (a one-time
    code for that account), and `exchange_code` accepts only codes it minted, once, for the
    same redirect address, returning the identity of an id token it signed and then verified
    like any other. As in mockgov, sign-in works while `down` stops the notices.
    """

    linked: set[str] = field(default_factory=set)
    inbox: list[dict] = field(default_factory=list)
    source: str = "digilocker"
    down: bool = False
    accounts: dict[str, dict] = field(default_factory=dict)
    codes: dict[str, dict] = field(default_factory=dict)
    oauth: digilocker_oidc.OAuthClient | None = None

    def _client(self) -> digilocker_oidc.OAuthClient:
        return self.oauth or digilocker_oidc.OAuthClient.from_settings()

    def authorize_url(self, *, state: str, nonce: str, redirect_uri: str) -> str:
        return digilocker_oidc.authorize_url(
            self._client(), state=state, nonce=nonce, redirect_uri=redirect_uri
        )

    def sign_in(self, digilocker_id: str, *, redirect_uri: str, nonce: str) -> str:
        """A one-time code for the account, as the demo page gives after the OTP."""
        if digilocker_id not in self.accounts:
            raise KeyError(digilocker_id)
        code = secrets.token_urlsafe(24)
        self.codes[code] = {
            "account": digilocker_id,
            "redirect_uri": redirect_uri,
            "nonce": nonce,
        }
        return code

    async def exchange_code(
        self, *, code: str, redirect_uri: str, nonce: str
    ) -> DigiLockerIdentity:
        grant = self.codes.pop(code, None)
        if grant is None or grant["redirect_uri"] != redirect_uri:
            raise AdapterRequestError(self.source, 400, '{"error": "invalid_grant"}')
        account = self.accounts[grant["account"]]
        client = self._client()
        token = digilocker_oidc.mint_id_token(
            client,
            sub=grant["account"],
            name=account["name"],
            birthdate=account["dob"],
            gender=account.get("gender"),
            apaar_id=account.get("apaar_id"),
            nonce=grant["nonce"],
        )
        return digilocker_oidc.read_id_token(token, client, nonce=nonce)

    async def notify(self, apaar_id: str, message: str, callback_url: str) -> DigiLockerResult:
        self._guard()
        if apaar_id not in self.linked:
            raise AdapterRequestError(self.source, 404, '{"error": {"code": "APAAR_NOT_LINKED"}}')
        inbox_id = f"ib_mem_{len(self.inbox) + 1:06d}"
        self.inbox.append(
            {
                "inbox_id": inbox_id,
                "apaar_id": apaar_id,
                "message": message,
                "callback_url": callback_url,
            }
        )
        return DigiLockerResult(delivered=True, inbox_id=inbox_id)


@dataclass
class InMemorySii(_Downable):
    """admissions: {passport_no: {name, nationality, institution_aicte_id, programme,
    academic_year}}"""

    admissions: dict[str, dict] = field(default_factory=dict)
    source: str = "sii"
    down: bool = False

    async def verify(self, passport_no: str, name: str, nationality: str) -> SiiResult:
        self._guard()
        row = self.admissions.get(passport_no)
        if row is None or row.get("nationality") != nationality:
            return SiiResult(admitted=False)
        return SiiResult(
            admitted=True,
            institution_aicte_id=row.get("institution_aicte_id"),
            programme=row.get("programme"),
            academic_year=row.get("academic_year"),
        )
