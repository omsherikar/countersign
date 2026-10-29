"""Both roles over HTTP: the client runs one PSI with the partner and returns three counts.

The partner's HTTP client is a TestClient on the partner app, so the test sees every byte
the partner receives and checks that none of Countersign's items is among them.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import httpx
import pytest

pytest.importorskip(
    "private_set_intersection.python",
    reason="openmined.psi has no wheel for this platform; run inside the linux/amd64 psi image",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.registry import apaar_hmac, partner_apaars, read_registry  # noqa: E402
from tests.conftest import KEY  # noqa: E402

pytestmark = pytest.mark.protocol


def settings_for(registry: Path) -> Settings:
    return Settings(
        role="partner",
        pii_hmac_key=KEY,
        registry_path=str(registry),
        partner_seed="test",
        partner_share=0.3,
        partner_extras=40,
        partner_url="http://psi.test",
        timeout_seconds=10,
        max_items=10_000,
    )


class RecordingClient(TestClient):
    """A TestClient that keeps every request body it sends."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sent: list[bytes] = []

    def send(self, request: httpx.Request, **kwargs) -> httpx.Response:  # type: ignore[override]
        self.sent.append(request.read())
        return super().send(request, **kwargs)


@pytest.fixture
def wired(registry: Path):
    settings = settings_for(registry)
    partner_app = create_app("partner", settings)
    to_partner = RecordingClient(partner_app, base_url="http://psi.test")
    client_app = create_app("client", dataclasses.replace(settings, role="client"), to_partner)
    return TestClient(client_app), to_partner, settings


def test_the_client_returns_the_counts_and_the_partner_never_sees_an_item(wired, registry):
    client, to_partner, settings = wired
    apaars = read_registry(registry)
    # Countersign holds the first 150 registry students and 10 the registry does not know
    countersign_apaars = apaars[:150] + [str(990000000000 + i) for i in range(10)]
    items = [apaar_hmac(KEY, a) for a in countersign_apaars]
    partner = set(partner_apaars(apaars, "test", 0.3, 40))
    expected = len(set(countersign_apaars) & partner)
    assert expected > 0

    answer = client.post("/psi/compute", json={"items": items})

    assert answer.status_code == 200, answer.text
    assert answer.json() == {
        "countersign_count": 160,
        "partner_count": len(partner),
        "overlap": expected,
    }
    sent = b"".join(to_partner.sent)
    assert sent
    for item in items:
        assert item.encode() not in sent
    assert set(json.loads(to_partner.sent[0])) == {"request"}


def test_duplicates_are_counted_once(wired, registry):
    client, _, _ = wired
    item = apaar_hmac(KEY, read_registry(registry)[0])
    answer = client.post("/psi/compute", json={"items": [item, item]})
    assert answer.status_code == 200
    assert answer.json()["countersign_count"] == 1


def test_items_that_are_not_digests_are_refused_without_echoing_them(wired):
    client, to_partner, _ = wired
    answer = client.post("/psi/compute", json={"items": ["123456784417"]})
    assert answer.status_code == 422
    assert answer.json()["error"]["code"] == "PSI_BAD_REQUEST"
    assert "123456784417" not in answer.text
    assert to_partner.sent == []


def test_a_partner_without_a_registry_is_reported(tmp_path):
    settings = settings_for(tmp_path / "missing.jsonl")
    partner_app = create_app("partner", settings)
    assert TestClient(partner_app).post("/psi/setup", json={"request": "AA=="}).status_code == 503
    to_partner = TestClient(partner_app, base_url="http://psi.test")
    client_settings = dataclasses.replace(settings, role="client")
    client = TestClient(create_app("client", client_settings, to_partner))
    answer = client.post("/psi/compute", json={"items": [apaar_hmac(KEY, "123456784417")]})
    assert answer.status_code == 502
    assert answer.json()["error"]["code"] == "PARTNER_UNAVAILABLE"


def test_an_unreachable_partner_is_a_503(registry):
    settings = dataclasses.replace(settings_for(registry), role="client")

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    unreachable = httpx.Client(base_url="http://psi.test", transport=httpx.MockTransport(refuse))
    client = TestClient(create_app("client", settings, unreachable))
    answer = client.post("/psi/compute", json={"items": []})
    assert answer.status_code == 503
    assert answer.json()["error"]["code"] == "PARTNER_UNAVAILABLE"


def test_the_partner_refuses_bytes_that_are_not_a_request(registry):
    partner = TestClient(create_app("partner", settings_for(registry)))
    assert partner.post("/psi/setup", json={"request": "not base64!"}).status_code == 422
    assert partner.post("/psi/setup", json={"request": "//79"}).status_code == 422


def test_each_role_serves_only_its_own_route(registry):
    settings = settings_for(registry)
    partner = TestClient(create_app("partner", settings))
    assert partner.get("/healthz").json() == {"status": "ok", "role": "partner"}
    assert partner.post("/psi/compute", json={"items": []}).status_code == 404
    client = TestClient(create_app("client", dataclasses.replace(settings, role="client")))
    assert client.post("/psi/setup", json={"request": "AA=="}).status_code == 404
