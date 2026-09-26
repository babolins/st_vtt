"""People, factions and places the campaign remembers.

Anyone at the table may write one down and edit it — this is collaborative
storytelling, and the session notes it is modelled on were written by everyone
at once. Two things stay the GM's: a record's `secret`, and whether the record
is visible to the table at all.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Any

from .. import service
from ..auth import current_user
from ..config import UserConfig
from ._common import emit, http

router = APIRouter(prefix="/records", tags=["records"])


class CreateBody(BaseModel):
    kind: str = "npc"
    name: str


class PatchBody(BaseModel):
    path: str
    value: Any = None
    op: str = "set"
    patch: str | None = None


def _visible_row(request: Request, user: UserConfig, rid: str) -> dict:
    row = request.app.state.db.get_record(rid)
    if row is None or not service.record_visible(user, row):
        raise HTTPException(404, "no such record")
    return row


@router.get("")
def list_records(request: Request, user: UserConfig = Depends(current_user)) -> list[dict]:
    return service.list_records(request.app, user)


@router.post("")
async def create_record(body: CreateBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    try:
        row, renders = service.create_record(request.app, user, body.kind, body.name)
    except service.ServiceError as e:
        raise http(e) from e
    await emit(request, renders)
    return service.record_view(user, row)


@router.get("/{rid}")
def get_record(rid: str, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    return service.record_view(user, _visible_row(request, user, rid))


@router.post("/{rid}/patch")
async def patch_record(rid: str, body: PatchBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    _visible_row(request, user, rid)
    try:
        renders = service.patch_entity(
            request.app, user, "record", rid, body.path, body.value, body.op, patch=body.patch
        )
    except service.ServiceError as e:
        raise http(e) from e
    await emit(request, renders)
    return {"ok": True}


@router.delete("/{rid}")
async def delete_record(rid: str, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    try:
        renders = service.delete_record(request.app, user, rid)
    except service.ServiceError as e:
        raise http(e) from e
    await emit(request, renders)
    return {"ok": True}
