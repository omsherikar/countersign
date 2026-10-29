"""The protocol round trip. Needs the openmined.psi wheel: linux x86_64 (the psi image,
`docker compose run --rm psi pytest -q`) or macOS arm64; skipped anywhere else."""

from __future__ import annotations

import pytest

pytest.importorskip(
    "private_set_intersection.python",
    reason="openmined.psi has no wheel for this platform; run inside the linux/amd64 psi image",
)

import private_set_intersection.python as psi  # noqa: E402

from app import protocol  # noqa: E402
from app.registry import apaar_hmac  # noqa: E402
from tests.conftest import KEY  # noqa: E402

pytestmark = pytest.mark.protocol


def digests(numbers: range) -> list[str]:
    return [apaar_hmac(KEY, str(100000000000 + n)) for n in numbers]


def test_the_client_learns_the_size_of_the_overlap():
    countersign = digests(range(0, 600))
    partner = digests(range(450, 1000))
    run = protocol.ClientRun(countersign)
    setup, response = protocol.answer(run.request, partner)
    assert run.intersection_size(setup, response) == 150


def test_disjoint_and_empty_sets_share_nothing():
    run = protocol.ClientRun(digests(range(0, 50)))
    assert run.intersection_size(*protocol.answer(run.request, digests(range(50, 90)))) == 0
    empty = protocol.ClientRun([])
    assert empty.intersection_size(*protocol.answer(empty.request, digests(range(0, 10)))) == 0


def test_the_request_shows_only_how_many_items_and_not_the_items():
    items = digests(range(0, 40))
    run = protocol.ClientRun(items)
    assert protocol.request_size(run.request) == 40
    for item in items:
        assert item.encode() not in run.request
        assert bytes.fromhex(item) not in run.request


def test_every_run_uses_new_keys():
    items = digests(range(0, 5))
    assert protocol.ClientRun(items).request != protocol.ClientRun(items).request


def test_the_partner_refuses_a_client_that_asks_for_the_members():
    nosy = psi.client.CreateWithNewKey(True)
    request = nosy.CreateRequest(digests(range(0, 5))).SerializeToString()
    with pytest.raises(protocol.ProtocolError, match="count only"):
        protocol.answer(request, digests(range(0, 5)))


def test_a_request_that_is_not_a_psi_message_is_refused():
    with pytest.raises(protocol.ProtocolError):
        protocol.answer(b"\xff\xfenot a request", digests(range(0, 5)))
    run = protocol.ClientRun(digests(range(0, 5)))
    with pytest.raises(protocol.ProtocolError):
        run.intersection_size(b"\xff\xfe", b"\x00\x01")
