from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .. import service
from ..auth import current_user, require_gm
from ..config import UserConfig
from ..perms import strip_for_user
from ._common import emit, http

router = APIRouter(prefix="/characters", tags=["characters"])


class CreateBody(BaseModel):
    playbook: str
    name: str = ""
    owner: str | None = None


class OwnerBody(BaseModel):
    owner: str | None


class ImportBody(BaseModel):
    character: dict[str, Any]
    owner: str | None = None


class PatchBody(BaseModel):
    path: str
    value: Any = None
    op: str = "set"
    patch: str | None = None


@router.get("")
def list_characters(request: Request, user: UserConfig = Depends(current_user)) -> list[dict]:
    return service.list_characters(request.app, user)


@router.post("")
async def create_character(body: CreateBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    try:
        row, renders = service.create_character(request.app, user, body.playbook, body.name, body.owner)
    except service.ServiceError as e:
        raise http(e) from e
    await emit(request, renders)
    return service.character_view(user, row)


@router.post("/import")
async def import_character(body: ImportBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    try:
        row, warnings, renders = service.import_character(request.app, user, body.character, body.owner)
    except service.ServiceError as e:
        raise http(e) from e
    await emit(request, renders)
    return {"character": service.character_view(user, row), "warnings": warnings}


@router.get("/{cid}")
def get_character(cid: str, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    row = request.app.state.db.get_character(cid)
    if row is None:
        raise HTTPException(404, "no such character")
    return service.character_view(user, row)


@router.get("/{cid}/export")
def export_character(cid: str, request: Request, user: UserConfig = Depends(current_user)) -> JSONResponse:
    row = request.app.state.db.get_character(cid)
    if row is None:
        raise HTTPException(404, "no such character")
    doc = strip_for_user(user, "character", row["data"])
    name = (doc.get("name") or "character").replace('"', "")
    return JSONResponse(doc, headers={"Content-Disposition": f'attachment; filename="{name}.json"'})


@router.post("/{cid}/patch")
async def patch_character(cid: str, body: PatchBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    try:
        renders = service.patch_entity(request.app, user, "character", cid, body.path, body.value, body.op, None, body.patch)
    except service.ServiceError as e:
        raise http(e) from e
    await emit(request, renders)
    row = request.app.state.db.get_character(cid)
    return {"revision": row["revision"] if row else None}


@router.post("/{cid}/owner")
async def set_owner(cid: str, body: OwnerBody, request: Request, user: UserConfig = Depends(require_gm)) -> dict:
    try:
        renders = service.set_owner(request.app, user, cid, body.owner)
    except service.ServiceError as e:
        raise http(e) from e
    await emit(request, renders)
    return {"ok": True}


@router.delete("/{cid}")
async def delete_character(cid: str, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    try:
        renders = service.delete_character(request.app, user, cid)
    except service.ServiceError as e:
        raise http(e) from e
    await emit(request, renders)
    return {"ok": True}
