"""What the API routers share."""

from typing import Any, Iterable

from fastapi import Request
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
