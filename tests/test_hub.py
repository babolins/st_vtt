"""The Hub when a client has gone: a send or a close that fails must not cost
anyone else their events, nor leave the departed user showing as online.

These check what the other clients hear, not the Hub's bookkeeping, so they
hold however a failed send ends up being handled.
"""

import json

import anyio

from st_vtt.config import UserConfig
from st_vtt.ws import Hub

ALICE = UserConfig(name="Alice")
BOB = UserConfig(name="Bob")


class Socket:
    """Just enough of a WebSocket for the Hub. A gone one fails the way Starlette's does
    once the connection is closed."""

    def __init__(self, gone: bool = False):
        self.gone = gone
        self.sent: list[dict] = []
        self.closed_with: int | None = None

    async def accept(self):
        pass

    async def send_text(self, text):
        if self.gone:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')
        self.sent.append(json.loads(text))

    async def close(self, code=1000):
        if self.gone:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')
        self.closed_with = code


def heard(ws: Socket, *, presence: bool = False) -> list[dict]:
    return [e for e in ws.sent if (e["type"] == "presence") == presence]


def test_a_gone_socket_does_not_cost_the_others_their_events():
    async def main():
        hub = Hub()
        gone, live = Socket(gone=True), Socket()
        await hub.connect(gone, ALICE, "s1")  # first, so every fan-out meets it before the live one
        await hub.connect(live, BOB, "s2")

        await hub.emit([lambda u: {"type": "one"}, lambda u: {"type": "two"}])
        await hub.broadcast_ephemeral({"type": "typing", "user": "Gm", "active": True})
        assert heard(live) == [{"type": "one"}, {"type": "two"}, {"type": "typing", "user": "Gm", "active": True}]
        before = len(heard(live, presence=True))
        await hub.broadcast_presence()
        assert len(heard(live, presence=True)) > before

    anyio.run(main)


def test_a_kick_that_cannot_close_the_socket_still_signs_it_out():
    async def main():
        hub = Hub()
        old, new, bob = Socket(gone=True), Socket(), Socket()
        await hub.connect(old, ALICE, "old")
        await hub.connect(new, ALICE, "new")
        await hub.connect(bob, BOB, "b")
        hub.set_focus(old, "c-old", {"entity": "shared", "id": "v", "path": "/notes"})

        await hub.kick("Alice", 4409, keep_session="new")
        assert new.closed_with is None
        assert hub.sessions_of("Alice") == {"new"}
        # Bob stops seeing the old tab on the field, and Alice is still online through the new one.
        assert heard(bob)[-1] == {"type": "field_presence", "user": "Alice", "client": "c-old", "entity": None, "id": None, "path": None}
        assert heard(bob, presence=True)[-1]["users"] == ["Alice", "Bob"]

        await hub.kick("Alice", 4409)
        assert new.closed_with == 4409
        assert hub.sessions_of("Alice") == set()
        assert heard(bob, presence=True)[-1]["users"] == ["Bob"]

    anyio.run(main)


def test_a_kicked_socket_disconnecting_again_is_harmless():
    """A kick disconnects the socket; then its own connection ends and disconnects it again."""

    async def main():
        hub = Hub()
        alice, bob = Socket(), Socket()
        await hub.connect(alice, ALICE, "a")
        await hub.connect(bob, BOB, "b")
        hub.set_focus(alice, "ca", {"entity": "shared", "id": "v", "path": "/notes"})

        await hub.kick("Alice", 4409)
        before = len(heard(bob))
        await hub.disconnect(alice)
        assert len(heard(bob)) == before  # no second field_presence
        assert heard(bob, presence=True)[-1]["users"] == ["Bob"]
        assert hub.focus_snapshot() == []

    anyio.run(main)
