"""ECDH private set intersection, cardinality only (OpenMined `openmined.psi`).

One function per message of the protocol:

    client (Countersign)                    partner (the other regulator)
    ClientRun(items_c).request  = E_c(items_c)  ->
                                            <-  answer(): setup    = E_p(items_p), compressed
                                                          response = E_p(E_c(items_c)), shuffled
    ClientRun.intersection_size(setup, response) = |D_c(response) & setup|

Each side keeps its own elliptic-curve key. The client sees the partner's items only under
the partner's key and its own items under both keys, in shuffled order, so it can count the
matches but not tell which items matched. The partner sees the client's items only under
the client's key and learns nothing but how many there are. Both keys are new for every run.
"""

from __future__ import annotations

from collections.abc import Sequence

import private_set_intersection.python as psi

# False: the client learns how many items the sets share, never which ones.
REVEAL_INTERSECTION = False
# chance that one run counts a match that is not there
FALSE_POSITIVE_RATE = 1e-9


class ProtocolError(ValueError):
    """A message that does not parse or does not follow the protocol."""


class ClientRun:
    """The client's side of one run; holds its key in memory until the run ends."""

    def __init__(self, items: Sequence[str]) -> None:
        self._client = psi.client.CreateWithNewKey(REVEAL_INTERSECTION)
        self.count = len(items)
        self.request: bytes = self._client.CreateRequest(list(items)).SerializeToString()

    def intersection_size(self, setup: bytes, response: bytes) -> int:
        server_setup = psi.ServerSetup()
        server_response = psi.Response()
        try:
            server_setup.ParseFromString(setup)
            server_response.ParseFromString(response)
            return int(self._client.GetIntersectionSize(server_setup, server_response))
        except Exception as exc:  # protobuf DecodeError, RuntimeError from the C++ core
            raise ProtocolError("the partner's answer is not a PSI answer") from exc


def request_size(request: bytes) -> int:
    """How many encrypted items a client request carries (the only thing it shows)."""
    message = psi.Request()
    try:
        message.ParseFromString(request)
    except Exception as exc:
        raise ProtocolError("not a PSI request") from exc
    return len(message.encrypted_elements)


def answer(request: bytes, items: Sequence[str]) -> tuple[bytes, bytes]:
    """The partner's setup message and response for one client request.

    Refuses a request that asks to see the shared items (reveal_intersection true).
    """
    message = psi.Request()
    try:
        message.ParseFromString(request)
    except Exception as exc:
        raise ProtocolError("not a PSI request") from exc
    if message.reveal_intersection != REVEAL_INTERSECTION:
        raise ProtocolError("this partner answers with a count only")
    server = psi.server.CreateWithNewKey(REVEAL_INTERSECTION)
    client_count = len(message.encrypted_elements)
    try:
        setup = server.CreateSetupMessage(
            FALSE_POSITIVE_RATE, max(client_count, 1), list(items), psi.DataStructure.GCS
        )
        response = server.ProcessRequest(message)
    except RuntimeError as exc:
        raise ProtocolError(str(exc)) from exc
    return setup.SerializeToString(), response.SerializeToString()
