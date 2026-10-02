from typing import Iterable

from fastapi import HTTPException, Request

from .. import service


async def emit(request: Request, renders: Iterable[service.Render]) -> None:
    request.app.state.hub.emit(renders)


def http(e: service.ServiceError) -> HTTPException:
    return HTTPException(e.status, str(e))
