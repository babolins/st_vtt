"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from . import service
from .config import Config, load_config
from .content import load_content
from .db import Database
from .ws import Hub, websocket_endpoint

log = logging.getLogger("st_vtt")


class ImmutableStatic(StaticFiles):
    """The bundle's files carry a content hash in their name, so a given URL's
    bytes never change; telling the browser that saves it re-asking on every
    load. index.html is the opposite case and is served `no-cache` below."""

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def create_app(config: Config | None = None) -> FastAPI:
    if config is None:
        config = load_config(os.environ.get("ST_VTT_CONFIG", "config.json"))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    pack = load_content(config.content_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.db.close()

    app = FastAPI(title="Shared Table", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.config = config
    app.state.pack = pack
    app.state.pack_json = pack.model_dump(mode="json", by_alias=True)
    app.state.db = Database(config.database_path)
    app.state.hub = Hub()
    service.autocreate_shared(app)

    app.include_router(api_router)
    app.add_api_websocket_route("/ws", websocket_endpoint)

    static = config.static_path
    index = static / "index.html"
    if index.exists():
        app.mount("/assets", ImmutableStatic(directory=static / "assets"), name="assets")

        # index.html names the bundle by content hash, so it must never be served
        # from a stale cache: a cached copy points at asset files that the next
        # build deleted, and the app comes up blank. The hashed assets themselves
        # are safe to keep forever, since a change to one changes its name.
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = static / path
            if path and candidate.is_file():
                return FileResponse(candidate, headers={"Cache-Control": "no-cache"})
            return FileResponse(index, headers={"Cache-Control": "no-cache"})

    else:
        log.warning("frontend build not found at %s (run `npm run build` in frontend/)", static)

        @app.get("/", include_in_schema=False)
        def no_frontend() -> JSONResponse:
            return JSONResponse({"error": f"frontend not built; expected {index}. Run `npm run build` in frontend/."}, status_code=503)

    log.info("loaded content pack %r (%d playbooks) from %s", pack.pack.name, len(pack.playbooks), config.content_path)
    log.info("database: %s", config.database_path)
    return app
