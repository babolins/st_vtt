from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..auth import COOKIE, WS_SIGNED_IN_ELSEWHERE, authenticate, get_config, make_token, new_session_id, session_from_token, session_key
from ..config import Config, UserConfig

router = APIRouter(tags=["auth"])


class LoginBody(BaseModel):
    name: str
    password: str | None = None
    force: bool = False


def _user_json(u: UserConfig) -> dict:
    return {"name": u.name, "role": u.role, "has_password": u.has_password}


@router.get("/users")
def list_users(cfg: Config = Depends(get_config)) -> list[dict]:
    return [_user_json(u) for u in cfg.users]


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response, cfg: Config = Depends(get_config)) -> dict:
    user = authenticate(cfg, body.name, body.password)
    db = request.app.state.db
    hub = request.app.state.hub
    if cfg.single_session:
        current = session_from_token(cfg, db, request.cookies.get(COOKIE))
        if current and current[0].name == user.name:
            # Same browser signing in again: keep its session (other tabs stay connected).
            response.set_cookie(COOKIE, make_token(cfg, user, current[1]), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365)
            return _user_json(user)
        if hub.sessions_of(user.name):
            if not body.force:
                raise HTTPException(409, f"{user.name} is already signed in on another device")
            hub.kick(user.name, WS_SIGNED_IN_ELSEWHERE)
    sid = new_session_id()
    db.set_meta(session_key(user), sid)
    response.set_cookie(COOKIE, make_token(cfg, user, sid), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365)
    return _user_json(user)


@router.post("/logout")
def logout(request: Request, response: Response, cfg: Config = Depends(get_config)) -> dict:
    current = session_from_token(cfg, request.app.state.db, request.cookies.get(COOKIE))
    if current:
        request.app.state.db.set_meta(session_key(current[0]), "")
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/me")
def me(request: Request, cfg: Config = Depends(get_config)) -> dict | None:
    """The logged-in user, or null (200) when not logged in."""
    current = session_from_token(cfg, request.app.state.db, request.cookies.get(COOKIE))
    return _user_json(current[0]) if current else None
