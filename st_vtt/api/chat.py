"""The chat log: messages, rolls, shared moves, roll requests and applying a roll's outcome."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .. import service
from ..auth import current_user, require_gm
from ..config import UserConfig
from ..perms import visible_to
from ._common import emit

router = APIRouter(tags=["chat"])

# The most messages one request for older chat history may return.
MAX_MESSAGE_PAGE = 500


class ChatBody(BaseModel):
    text: str
    to: list[str] | None = None


class RollBody(BaseModel):
    expr: str | None = None
    label: str | None = None
    character_id: str | None = None
    shared_id: str | None = None
    move_id: str | None = None
    stat: str | None = None
    advantage: bool = False
    disadvantage: bool = False
    bonus: int = 0
    modifiers: dict[str, int] | None = None
    gm_only: bool = False
    request_id: int | None = None


class ShareMoveBody(BaseModel):
    character_id: str | None = None
    move_id: str


class RequestRollBody(BaseModel):
    user: str
    label: str = ""
    stat: str | None = None
    move_id: str | None = None


class ApplyBody(BaseModel):
    index: int
    choice: str | None = None


@router.get("/messages")
def list_messages(
    request: Request,
    before: int | None = None,
    limit: int = Query(100, ge=1),
    user: UserConfig = Depends(current_user),
) -> list[dict]:
    msgs = request.app.state.db.list_messages(limit=min(limit, MAX_MESSAGE_PAGE), before=before)
    return [m for m in msgs if visible_to(user, m.get("visibility"))]


@router.post("/chat")
async def post_chat(body: ChatBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    renders = service.post_chat(request.app, user, body.text, body.to)
    emit(request, renders)
    return {"ok": True}


@router.post("/roll")
async def post_roll(body: RollBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    renders = service.do_roll(request.app, user, body.model_dump())
    emit(request, renders)
    return {"ok": True}


@router.post("/messages/{mid}/apply")
async def apply_outcome(mid: int, body: ApplyBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    renders = service.apply_outcome(request.app, user, mid, body.index, body.choice)
    emit(request, renders)
    return {"ok": True}


@router.post("/share_move")
async def post_share_move(body: ShareMoveBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    renders = service.share_move(request.app, user, body.character_id, body.move_id)
    emit(request, renders)
    return {"ok": True}


@router.post("/request_roll")
async def post_request_roll(body: RequestRollBody, request: Request, user: UserConfig = Depends(require_gm)) -> dict:
    renders = service.request_roll(request.app, user, body.user, body.label, body.stat, body.move_id)
    emit(request, renders)
    return {"ok": True}


@router.delete("/messages")
async def clear_messages(request: Request, user: UserConfig = Depends(require_gm)) -> dict:
    renders = service.clear_chat(request.app, user)
    emit(request, renders)
    return {"ok": True}


@router.get("/export/campaign")
def export_campaign(request: Request, user: UserConfig = Depends(require_gm)) -> JSONResponse:
    data: dict[str, Any] = {"pack_id": request.app.state.pack.pack.id, **request.app.state.db.export_all()}
    return JSONResponse(data, headers={"Content-Disposition": 'attachment; filename="campaign.json"'})
