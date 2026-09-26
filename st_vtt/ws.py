"""WebSocket hub: one socket per client, per-user rendered broadcasts, presence."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Iterable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from . import service
from .auth import WS_NOT_LOGGED_IN, ws_session
from .config import UserConfig
from .perms import GM_ONLY_PATHS

log = logging.getLogger("st_vtt.ws")


class Hub:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, UserConfig] = {}
        self._focus: dict[WebSocket, dict[str, Any]] = {}
        self._client_ids: dict[WebSocket, str | None] = {}
        self._sessions: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    @property
    def users(self) -> list[str]:
        return sorted({u.name for u in self._clients.values()})

    async def connect(self, ws: WebSocket, user: UserConfig, sid: str) -> None:
        await ws.accept()
        async with self._lock:
            self._clients[ws] = user
            self._sessions[ws] = sid
        await self.broadcast_presence()

    def sessions_of(self, name: str) -> set[str]:
        """Session ids with a live connection for this user."""
        return {self._sessions[ws] for ws, u in self._clients.items() if u.name == name and ws in self._sessions}

    async def kick(self, name: str, code: int, keep_session: str | None = None) -> None:
        """Close every connection of `name` (except those of `keep_session`)."""
        targets = [ws for ws, u in list(self._clients.items()) if u.name == name and self._sessions.get(ws) != keep_session]
        for ws in targets:
            try:
                await ws.close(code=code)
            except Exception:  # noqa: BLE001
                pass
            await self.disconnect(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            user = self._clients.pop(ws, None)
            had_focus = self._focus.pop(ws, None)
            client = self._client_ids.pop(ws, None)
            self._sessions.pop(ws, None)
        if user and had_focus:
            await self.broadcast_ephemeral({"type": "field_presence", "user": user.name, "client": client, "entity": None, "id": None, "path": None}, exclude=ws)
        await self.broadcast_presence()

    async def broadcast_ephemeral(self, event: dict[str, Any], exclude: WebSocket | None = None, gm_only: bool = False) -> None:
        """Send an un-persisted event to every other client (optionally GMs only)."""
        for ws, user in list(self._clients.items()):
            if ws is exclude:
                continue
            if gm_only and not user.is_gm:
                continue
            await self.send(ws, event)

    def set_focus(self, ws: WebSocket, client: str | None, focus: dict[str, Any] | None) -> None:
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

    async def send(self, ws: WebSocket, event: dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(event))
        except Exception:  # noqa: BLE001 - client went away
            pass

    async def emit(self, renders: Iterable[service.Render]) -> None:
        clients = list(self._clients.items())
        for render in renders:
            for ws, user in clients:
                event = render(user)
                if event is not None:
                    await self.send(ws, event)

    async def broadcast_presence(self) -> None:
        users = self.users
        for ws in list(self._clients):
            await self.send(ws, {"type": "presence", "users": users})


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
                await hub.send(ws, {"type": "error", "message": "invalid JSON"})
                continue
            if not isinstance(msg, dict):
                continue
            ref = msg.get("ref")
            if msg.get("type") in EPHEMERAL:
                await handle_ephemeral(app, hub, ws, user, msg)
                continue
            try:
                renders = handle(app, user, msg)
            except service.ServiceError as e:
                await hub.send(ws, {"type": "error", "message": str(e), "ref": ref})
                continue
            except Exception as e:  # noqa: BLE001
                log.exception("ws handler failed")
                await hub.send(ws, {"type": "error", "message": f"server error: {e}", "ref": ref})
                continue
            if renders is None:
                continue
            await hub.emit(renders)
            if ref is not None:
                await hub.send(ws, {"type": "ack", "ref": ref})
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(ws)


EPHEMERAL = {"focus", "blur", "typing", "presence_sync"}


def _gm_only_focus(app: FastAPI, focus: dict[str, Any]) -> bool:
    """Whether presence on this field should only be shown to GMs: a sheet or record
    the table cannot see, or a field it is never sent (gm_notes, a record's secret).
    Presence carries no content, but it would still say that such a thing exists."""
    entity, eid, path = focus.get("entity"), focus.get("id"), focus.get("path")
    if entity == "shared" and service.shared_is_gm_only(app, eid):
        return True
    if entity == "record" and service.record_is_hidden(app, eid):
        return True
    return isinstance(path, str) and any(path == p or path.startswith(p + "/") for p in GM_ONLY_PATHS)


async def handle_ephemeral(app: FastAPI, hub: Hub, ws: WebSocket, user: UserConfig, msg: dict[str, Any]) -> None:
    kind = msg.get("type")
    client = msg.get("client")
    if kind == "focus":
        focus = {"entity": msg.get("entity"), "id": msg.get("id"), "path": msg.get("path")}
        hub.set_focus(ws, client, focus)
        await hub.broadcast_ephemeral(
            {"type": "field_presence", "user": user.name, "client": client, **focus},
            exclude=ws, gm_only=_gm_only_focus(app, focus),
        )
    elif kind == "blur":
        hub.set_focus(ws, client, None)
        await hub.broadcast_ephemeral({"type": "field_presence", "user": user.name, "client": client, "entity": None, "id": None, "path": None}, exclude=ws)
    elif kind == "typing":
        await hub.broadcast_ephemeral({"type": "typing", "user": user.name, "active": bool(msg.get("active"))}, exclude=ws)
    elif kind == "presence_sync":
        for f in hub.focus_snapshot():
            if f.get("client") == client:
                continue
            if _gm_only_focus(app, f) and not user.is_gm:
                continue
            await hub.send(ws, {"type": "field_presence", **f})


def handle(app: FastAPI, user: UserConfig, msg: dict[str, Any]) -> list[service.Render] | None:
    kind = msg.get("type")
    if kind == "ping":
        return None
    if kind == "patch":
        return service.patch_entity(app, user, str(msg.get("entity")), msg.get("id"), str(msg.get("path", "")), msg.get("value"), str(msg.get("op", "set")), msg.get("client"), msg.get("patch"))
    if kind == "chat":
        to = msg.get("to")
        return service.post_chat(app, user, str(msg.get("text", "")), list(to) if to else None)
    if kind == "roll":
        return service.do_roll(app, user, msg)
    if kind == "share_move":
        return service.share_move(app, user, msg.get("character_id"), str(msg.get("move_id", "")))
    if kind == "request_roll":
        return service.request_roll(app, user, str(msg.get("user", "")), str(msg.get("label", "")), msg.get("stat"))
    raise service.ServiceError(f"unknown message type {kind!r}")
