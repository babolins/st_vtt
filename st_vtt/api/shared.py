"""Shared sheets: the village, a GM screen, anything the table edits together. Creating,
replacing and deleting one is the GM's job; editing it is anyone's, unless it is GM-only.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .. import service
from ..auth import current_user, require_gm
from ..config import UserConfig
from ..perms import strip_for_user
from ._common import PatchBody, emit

router = APIRouter(prefix="/shared", tags=["shared"])


class CreateBody(BaseModel):
    template: str
    name: str | None = None



def _visible_row(request: Request, user: UserConfig, sid: str) -> dict:
    row = request.app.state.db.get_shared(sid)
    if row is None or not service.shared_visible(request.app, user, row):
        raise HTTPException(404, "no such shared sheet")
    return row


@router.get("")
def list_shared(request: Request, user: UserConfig = Depends(current_user)) -> list[dict]:
    return service.list_shared(request.app, user)


@router.post("")
async def create_shared(body: CreateBody, request: Request, user: UserConfig = Depends(require_gm)) -> dict:
    row, renders = service.create_shared(request.app, user, body.template, body.name)
    emit(request, renders)
    return service.shared_view(user, row)


@router.get("/{sid}")
def get_shared(sid: str, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    return service.shared_view(user, _visible_row(request, user, sid))


@router.get("/{sid}/export")
def export_shared(sid: str, request: Request, user: UserConfig = Depends(current_user)) -> JSONResponse:
    doc = strip_for_user(user, "shared", _visible_row(request, user, sid)["data"])
    name = (doc.get("name") or "shared").replace('"', "")
    return JSONResponse(doc, headers={"Content-Disposition": f'attachment; filename="{name}.json"'})


@router.post("/{sid}/import")
async def import_shared(sid: str, body: dict[str, Any], request: Request, user: UserConfig = Depends(require_gm)) -> dict:
    renders = service.import_shared(request.app, user, sid, body)
    emit(request, renders)
    return {"ok": True}


@router.post("/{sid}/patch")
async def patch_shared(sid: str, body: PatchBody, request: Request, user: UserConfig = Depends(current_user)) -> dict:
    renders = service.patch_entity(request.app, user, "shared", sid, body.path, body.value, body.op, None, body.patch)
    emit(request, renders)
    row = request.app.state.db.get_shared(sid)
    return {"revision": row["revision"] if row else None}


@router.delete("/{sid}")
async def delete_shared(sid: str, request: Request, user: UserConfig = Depends(require_gm)) -> dict:
    renders = service.delete_shared(request.app, user, sid)
    emit(request, renders)
    return {"ok": True}
