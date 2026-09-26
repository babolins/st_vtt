from typing import Any

from fastapi import APIRouter, Depends, Request

from .. import service
from ..auth import current_user
from ..config import UserConfig

router = APIRouter(tags=["content"])


@router.get("/content")
def get_content(request: Request, user: UserConfig = Depends(current_user)) -> dict[str, Any]:
    return request.app.state.pack_json


@router.get("/state")
def get_state(request: Request, user: UserConfig = Depends(current_user)) -> dict[str, Any]:
    """Everything a client needs at load time."""
    app = request.app
    from ..perms import visible_to

    messages = [m for m in app.state.db.list_messages(limit=200) if visible_to(user, m.get("visibility"))]
    return {
        "me": {"name": user.name, "role": user.role},
        "campaign_name": app.state.config.campaign_name,
        "users": [{"name": u.name, "role": u.role} for u in app.state.config.users],
        "online": app.state.hub.users,
        "characters": service.list_characters(app, user),
        "shared": service.list_shared(app, user),
        "records": service.list_records(app, user),
        "messages": messages,
    }
