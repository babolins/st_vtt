"""WebSocket hub: one socket per client, per-user rendered broadcasts, presence."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Iterable

import anyio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from . import service
from .auth import WS_NOT_LOGGED_IN, ws_session
from .config import UserConfig
from .perms import is_hidden_path

log = logging.getLogger("st_vtt.ws")

# Close code for a client dropped for not keeping up ("Try Again Later"): it reconnects and
# reloads what it missed.
WS_TOO_SLOW = 1013
# A client is dropped when one send to it takes longer than this (seconds), or when this
# many events are waiting for it: it has stopped reading, or can't keep up.
SEND_TIMEOUT = 5.0
OUTBOX_LIMIT = 1000


class Hub:
    """The connected clients, and what goes out to them.

    Sending only queues an event: each client has its own outbox, emptied by its own writer
    task, so a client that stops reading holds up nobody else. That client is dropped instead
    (see SEND_TIMEOUT). Everything here runs on the server's one event loop and nothing that
    changes the Hub's state awaits partway through, so it needs no lock.
    """

    def __init__(self) -> None:
        self._clients: dict[WebSocket, UserConfig] = {}
        self._focus: dict[WebSocket, dict[str, Any]] = {}
        self._client_ids: dict[WebSocket, str | None] = {}
        self._sessions: dict[WebSocket, str] = {}
        self._outboxes: dict[WebSocket, asyncio.Queue[str]] = {}
        self._writers: dict[WebSocket, asyncio.Task[None]] = {}
        self._closing: set[asyncio.Task[None]] = set()

    @property
    def users(self) -> list[str]:
        return sorted({u.name for u in self._clients.values()})

    async def connect(self, ws: WebSocket, user: UserConfig, sid: str) -> None:
        await ws.accept()
        self._clients[ws] = user
        self._sessions[ws] = sid
        outbox: asyncio.Queue[str] = asyncio.Queue()
        self._outboxes[ws] = outbox
        self._writers[ws] = asyncio.create_task(self._write(ws, outbox))
        self.broadcast_presence()

    def sessions_of(self, name: str) -> set[str]:
        """Session ids with a live connection for this user."""
        return {self._sessions[ws] for ws, u in self._clients.items() if u.name == name and ws in self._sessions}

    def kick(self, name: str, code: int, keep_session: str | None = None) -> None:
        """Close every connection of `name` (except those of `keep_session`)."""
        for ws in [
            ws for ws, u in list(self._clients.items()) if u.name == name and self._sessions.get(ws) != keep_session
        ]:
            self._drop(ws, code)

    def end_session(self, sid: str, code: int) -> None:
        """Close every connection made with session `sid` (all the tabs of one browser)."""
        for ws in [ws for ws, s in list(self._sessions.items()) if s == sid]:
            self._drop(ws, code)

    def disconnect(self, ws: WebSocket) -> None:
        """Forget a connection and tell everyone else. Harmless for one already forgotten."""
        user = self._clients.pop(ws, None)
        had_focus = self._focus.pop(ws, None)
        client = self._client_ids.pop(ws, None)
        self._sessions.pop(ws, None)
        outbox = self._outboxes.pop(ws, None)
        writer = self._writers.pop(ws, None)
        if writer is not None and writer is not asyncio.current_task():
            writer.cancel()
        while outbox is not None and not outbox.empty():
            outbox.get_nowait()
            outbox.task_done()
        if user and had_focus:
            self.broadcast_ephemeral(
                {
                    "type": "field_presence",
                    "user": user.name,
                    "client": client,
                    "entity": None,
                    "id": None,
                    "path": None,
                },
                exclude=ws,
            )
        self.broadcast_presence()

    def _drop(self, ws: WebSocket, code: int) -> None:
        """Disconnect `ws` and close it, without waiting for the close to get through: a
        client that has stopped reading can't take a close frame either."""
        self.disconnect(ws)
        task = asyncio.create_task(self._close(ws, code))
        self._closing.add(task)
        task.add_done_callback(self._closing.discard)

    async def _close(self, ws: WebSocket, code: int) -> None:
        with anyio.move_on_after(SEND_TIMEOUT):
            try:
                await ws.close(code=code)
            except Exception:  # noqa: BLE001 - client went away
                pass

    async def _write(self, ws: WebSocket, outbox: asyncio.Queue[str]) -> None:
        while True:
            text = await outbox.get()
            try:
                with anyio.fail_after(SEND_TIMEOUT):
                    await ws.send_text(text)
            except Exception:  # noqa: BLE001 - too slow, or the client went away
                if self._outboxes.get(ws) is outbox:
                    self._drop(ws, WS_TOO_SLOW)
                return
            finally:
                outbox.task_done()

    def send(self, ws: WebSocket, event: dict[str, Any]) -> None:
        outbox = self._outboxes.get(ws)
        if outbox is None:
            return  # not connected, or dropped
        if outbox.qsize() >= OUTBOX_LIMIT:
            self._drop(ws, WS_TOO_SLOW)
            return
        outbox.put_nowait(json.dumps(event))

    async def flush(self) -> None:
        """Wait until everything queued so far is sent or given up on, and every close begun is done."""
        await asyncio.gather(*(outbox.join() for outbox in list(self._outboxes.values())), *list(self._closing))

    def emit(self, renders: Iterable[service.Render]) -> None:
        clients = list(self._clients.items())
        for render in renders:
            for ws, user in clients:
                event = render(user)
                if event is not None:
                    self.send(ws, event)

    def broadcast_ephemeral(
        self, event: dict[str, Any], exclude: WebSocket | None = None, gm_only: bool = False
    ) -> None:
        """Send an un-persisted event to every other client (optionally GMs only)."""
        for ws, user in list(self._clients.items()):
            if ws is exclude:
                continue
            if gm_only and not user.is_gm:
                continue
            self.send(ws, event)

    def set_focus(self, ws: WebSocket, client: str | None, focus: dict[str, Any] | None) -> None:
        if ws not in self._clients:
            return  # dropped
        self._client_ids[ws] = client
        if focus is None:
            self._focus.pop(ws, None)
        else:
            self._focus[ws] = focus

    def focus_snapshot(self) -> list[dict[str, Any]]:
        """Current focus of every connected client, for a newly connected one."""
        return [
            {"user": self._clients[ws].name, "client": self._client_ids.get(ws), **f}
            for ws, f in self._focus.items()
            if ws in self._clients
        ]

    def broadcast_presence(self) -> None:
        users = self.users
        for ws in list(self._clients):
            self.send(ws, {"type": "presence", "users": users})


async def websocket_endpoint(ws: WebSocket) -> None:
    app: FastAPI = ws.app
    hub: Hub = app.state.hub
    found = ws_session(ws)
    if found is None:
        await ws.close(code=WS_NOT_LOGGED_IN)
        return
    user, sid = found
    await hub.connect(ws, user, sid)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                hub.send(ws, {"type": "error", "message": "invalid JSON"})
                continue
            if not isinstance(msg, dict):
                continue
            ref = msg.get("ref")
            if msg.get("type") in EPHEMERAL:
                handle_ephemeral(app, hub, ws, user, msg)
                continue
            try:
                renders = handle(app, user, msg)
            except service.ServiceError as e:
                hub.send(ws, {"type": "error", "message": str(e), "ref": ref})
                continue
            except Exception as e:  # noqa: BLE001
                log.exception("ws handler failed")
                hub.send(ws, {"type": "error", "message": f"server error: {e}", "ref": ref})
                continue
            if renders is None:
                continue
            hub.emit(renders)
            if ref is not None:
                hub.send(ws, {"type": "ack", "ref": ref})
    except WebSocketDisconnect:
        pass
    finally:
        # This task may be the one being cancelled (a shutdown, or the TestClient closing a
        # socket). disconnect() doesn't await, so a cancel can't stop it partway, before it
        # has told everyone else the user left.
        hub.disconnect(ws)


EPHEMERAL = {"focus", "blur", "typing", "presence_sync"}


def _gm_only_focus(app: FastAPI, focus: dict[str, Any]) -> bool:
    """Whether presence on this field should only be shown to GMs: a sheet or record
    the table cannot see, or one of its hidden fields (gm_notes, a record's secret).
    Presence carries no content, but it would still say that such a thing exists."""
    entity, eid, path = focus.get("entity"), focus.get("id"), focus.get("path")
    if entity == "shared" and service.shared_is_gm_only(app, eid):
        return True
    if entity == "record" and service.record_is_hidden(app, eid):
        return True
    return is_hidden_path(entity, path)


def handle_ephemeral(app: FastAPI, hub: Hub, ws: WebSocket, user: UserConfig, msg: dict[str, Any]) -> None:
    kind = msg.get("type")
    client = msg.get("client")
    if kind == "focus":
        focus = {"entity": msg.get("entity"), "id": msg.get("id"), "path": msg.get("path")}
        hub.set_focus(ws, client, focus)
        hub.broadcast_ephemeral(
            {"type": "field_presence", "user": user.name, "client": client, **focus},
            exclude=ws,
            gm_only=_gm_only_focus(app, focus),
        )
    elif kind == "blur":
        hub.set_focus(ws, client, None)
        hub.broadcast_ephemeral(
            {"type": "field_presence", "user": user.name, "client": client, "entity": None, "id": None, "path": None},
            exclude=ws,
        )
    elif kind == "typing":
        hub.broadcast_ephemeral({"type": "typing", "user": user.name, "active": bool(msg.get("active"))}, exclude=ws)
    elif kind == "presence_sync":
        for f in hub.focus_snapshot():
            if f.get("client") == client:
                continue
            if _gm_only_focus(app, f) and not user.is_gm:
                continue
            hub.send(ws, {"type": "field_presence", **f})


def handle(app: FastAPI, user: UserConfig, msg: dict[str, Any]) -> list[service.Render] | None:
    kind = msg.get("type")
    if kind == "ping":
        return None
    if kind == "patch":
        return service.patch_entity(
            app,
            user,
            str(msg.get("entity")),
            msg.get("id"),
            str(msg.get("path", "")),
            msg.get("value"),
            op=str(msg.get("op", "set")),
            patch=msg.get("patch"),
            client=msg.get("client"),
            ref=msg.get("ref"),
        )
    if kind == "chat":
        to = msg.get("to")
        # As ChatBody requires over REST: list() would split a bare name into letters.
        if to is not None and not (isinstance(to, list) and all(isinstance(n, str) for n in to)):
            raise service.ServiceError("to must be a list of user names")
        return service.post_chat(app, user, str(msg.get("text", "")), to or None)
    if kind == "roll":
        return service.do_roll(app, user, msg)
    if kind == "share_move":
        return service.share_move(app, user, msg.get("character_id"), str(msg.get("move_id", "")))
    if kind == "request_roll":
        return service.request_roll(app, user, str(msg.get("user", "")), str(msg.get("label", "")), msg.get("stat"))
    raise service.ServiceError(f"unknown message type {kind!r}")
