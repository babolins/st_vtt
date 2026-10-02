"""What the API routers share."""

import re
from typing import Any, Iterable
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .. import service


class PatchBody(BaseModel):
    path: str
    value: Any = None
    op: str = "set"
    patch: str | None = None


def emit(request: Request, renders: Iterable[service.Render]) -> None:
    """Broadcast to every connected client. The hub's outboxes belong to the event loop, so a
    route that emits is `async def` even with nothing to await: FastAPI would run a plain `def`
    route on a worker thread."""
    request.app.state.hub.emit(renders)


def json_download(doc: Any, name: str) -> JSONResponse:
    """`doc` as a download named after `name`. Headers go out as Latin-1, so the name rides in
    `filename*` (RFC 6266), with an ASCII copy in `filename` for anything that ignores that."""
    fallback = re.sub(r'[^\x20-\x7e]|["\\]', "", name).strip() or "download"
    return JSONResponse(
        doc,
        headers={
            "Content-Disposition": f"attachment; filename=\"{fallback}.json\"; filename*=UTF-8''{quote(name + '.json')}"
        },
    )
