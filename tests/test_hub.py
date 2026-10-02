"""The Hub when a client has gone: a send or a close that fails must not cost
anyone else their events, nor leave the departed user showing as online.

These check what the other clients hear, not the Hub's bookkeeping, so they
hold however a failed send ends up being handled.
"""

import json
import random

import anyio

from st_vtt import ws as ws_module
from st_vtt.config import UserConfig
from st_vtt.ws import WS_TOO_SLOW, Hub

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

        hub.emit([lambda u: {"type": "one"}, lambda u: {"type": "two"}])
        hub.broadcast_ephemeral({"type": "typing", "user": "Gm", "active": True})
        await hub.flush()
        assert heard(live) == [{"type": "one"}, {"type": "two"}, {"type": "typing", "user": "Gm", "active": True}]
        before = len(heard(live, presence=True))
        hub.broadcast_presence()
        await hub.flush()
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

        hub.kick("Alice", 4409, keep_session="new")
        await hub.flush()
        assert new.closed_with is None
        assert hub.sessions_of("Alice") == {"new"}
        # Bob stops seeing the old tab on the field, and Alice is still online through the new one.
        assert heard(bob)[-1] == {"type": "field_presence", "user": "Alice", "client": "c-old", "entity": None, "id": None, "path": None}
        assert heard(bob, presence=True)[-1]["users"] == ["Alice", "Bob"]

        hub.kick("Alice", 4409)
        await hub.flush()
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

        hub.kick("Alice", 4409)
        await hub.flush()
        before = len(heard(bob))
        hub.disconnect(alice)
        await hub.flush()
        assert len(heard(bob)) == before  # no second field_presence
        assert heard(bob, presence=True)[-1]["users"] == ["Bob"]
        assert hub.focus_snapshot() == []

    anyio.run(main)


class Stalled(Socket):
    """A client that has stopped reading: a send to it never completes. Its close may get
    through (a slow link, eventually) or hang as well (a dead one)."""

    def __init__(self, close_hangs: bool = False):
        super().__init__()
        self.close_hangs = close_hangs

    async def send_text(self, text):
        await anyio.sleep_forever()

    async def close(self, code=1000):
        if self.close_hangs:
            await anyio.sleep_forever()
        self.closed_with = code


class Slow(Socket):
    """A client that reads, but takes its time over each event."""

    async def send_text(self, text):
        await anyio.sleep(random.uniform(0, 0.003))
        await super().send_text(text)


async def until(check, within=2.0):
    with anyio.fail_after(within):
        while not check():
            await anyio.sleep(0.01)


def test_a_stalled_socket_does_not_hold_up_the_others(monkeypatch):
    monkeypatch.setattr(ws_module, "SEND_TIMEOUT", 60)  # so dropping it is not what lets the others hear

    async def main():
        with anyio.fail_after(2):
            hub = Hub()
            stalled, live = Stalled(), Socket()
            await hub.connect(stalled, ALICE, "s1")  # first, so every fan-out meets it before the live one
            await hub.connect(live, BOB, "s2")

            hub.emit([lambda u: {"type": "one"}])
            hub.broadcast_ephemeral({"type": "typing", "user": "Gm", "active": True})
            await until(lambda: heard(live) == [{"type": "one"}, {"type": "typing", "user": "Gm", "active": True}], within=1)

    anyio.run(main)


def test_a_stalled_socket_is_dropped_and_told_to_come_back(monkeypatch):
    monkeypatch.setattr(ws_module, "SEND_TIMEOUT", 0.05)

    async def main():
        hub = Hub()
        stalled, live = Stalled(), Socket()
        await hub.connect(stalled, ALICE, "s1")
        await hub.connect(live, BOB, "s2")
        hub.set_focus(stalled, "ca", {"entity": "shared", "id": "v", "path": "/notes"})

        await until(lambda: stalled.closed_with is not None)
        assert stalled.closed_with == WS_TOO_SLOW  # the client reconnects and reloads what it missed
        assert hub.users == ["Bob"]
        await hub.flush()
        assert heard(live, presence=True)[-1]["users"] == ["Bob"]
        assert heard(live)[-1] == {"type": "field_presence", "user": "Alice", "client": "ca", "entity": None, "id": None, "path": None}

    anyio.run(main)


def test_a_socket_that_cannot_even_be_closed_is_still_dropped(monkeypatch):
    monkeypatch.setattr(ws_module, "SEND_TIMEOUT", 0.05)

    async def main():
        hub = Hub()
        stalled, live = Stalled(close_hangs=True), Socket()
        await hub.connect(stalled, ALICE, "s1")
        await hub.connect(live, BOB, "s2")

        await until(lambda: hub.users == ["Bob"])
        hub.emit([lambda u: {"type": "one"}])
        with anyio.fail_after(1):
            await hub.flush()
        assert heard(live) == [{"type": "one"}]

    anyio.run(main)


def test_a_client_too_far_behind_is_dropped_before_its_send_times_out(monkeypatch):
    monkeypatch.setattr(ws_module, "SEND_TIMEOUT", 60)
    monkeypatch.setattr(ws_module, "OUTBOX_LIMIT", 5)

    async def main():
        hub = Hub()
        stalled, live = Stalled(), Socket()
        await hub.connect(stalled, ALICE, "s1")
        await hub.connect(live, BOB, "s2")

        for i in range(10):
            hub.emit([lambda u, i=i: {"type": "n", "i": i}])
            await anyio.sleep(0)  # events come one request at a time, and a client reading them keeps up
        assert hub.users == ["Bob"]  # noticed as the events are queued, not when a send gives up
        await until(lambda: stalled.closed_with == WS_TOO_SLOW)
        await hub.flush()
        assert [e["i"] for e in heard(live)] == list(range(10))

    anyio.run(main)


def test_each_client_hears_events_in_the_order_they_happened():
    async def main():
        hub = Hub()
        slow, quick = Slow(), Socket()
        await hub.connect(slow, ALICE, "s1")
        await hub.connect(quick, BOB, "s2")

        for i in range(30):
            hub.emit([lambda u, i=i: {"type": "n", "i": i}])
            hub.send(slow if i % 2 else quick, {"type": "ack", "ref": i})
        await hub.flush()
        assert [e.get("i", e.get("ref")) for e in heard(slow)] == [n for i in range(30) for n in ([i, i] if i % 2 else [i])]
        assert [e.get("i", e.get("ref")) for e in heard(quick)] == [n for i in range(30) for n in ([i] if i % 2 else [i, i])]

    anyio.run(main)
