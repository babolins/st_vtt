"""Login with a name from the config (plus optional password) -> signed cookie.

The cookie carries the user name and a session id. With `single_session`
(the default) only the most recently issued session id for a user is valid,
so signing in on a new device signs the old one out.
"""

from __future__ import annotations

import hmac
import secrets
import uuid

from fastapi import Depends, HTTPException, Request, WebSocket
from itsdangerous import BadSignature, URLSafeSerializer

from .config import Config, UserConfig
from .db import Database

COOKIE = "st_session"
# A year, in seconds: a table keeps meeting, and nobody should sign in every session.
COOKIE_MAX_AGE = 365 * 24 * 60 * 60
# WebSocket close codes the client understands.
WS_NOT_LOGGED_IN = 4401
WS_SIGNED_IN_ELSEWHERE = 4409


def serializer(cfg: Config) -> URLSafeSerializer:
    assert cfg.secret, "create_app() gives a config without a secret the campaign's own"
    return URLSafeSerializer(cfg.secret, salt="st_vtt.session")


def campaign_secret(db: Database) -> str:
    """The secret made for this campaign the first time it ran without one in the config.
    Kept in its database, so a restart signs nobody out and each campaign has its own."""
    secret = db.get_meta("secret")
    if not secret:
        secret = secrets.token_urlsafe(32)
        db.set_meta("secret", secret)
    return secret


def make_token(cfg: Config, user: UserConfig, sid: str) -> str:
    return serializer(cfg).dumps({"u": user.name, "s": sid})


def new_session_id() -> str:
    return uuid.uuid4().hex


def session_key(user: UserConfig) -> str:
    return f"session:{user.name}"


def session_from_token(cfg: Config, db: Database, token: str | None) -> tuple[UserConfig, str] | None:
    """(user, session id) for a valid cookie whose session is still the current one."""
    if not token:
        return None
    try:
        data = serializer(cfg).loads(token)
    except BadSignature:
        return None
    user = cfg.user(str(data.get("u", "")))
    sid = str(data.get("s", ""))
    if user is None or not sid:
        return None
    if cfg.single_session and db.get_meta(session_key(user)) != sid:
        return None
    return user, sid


def user_from_token(cfg: Config, db: Database, token: str | None) -> UserConfig | None:
    found = session_from_token(cfg, db, token)
    return found[0] if found else None


def authenticate(cfg: Config, name: str, password: str | None) -> UserConfig:
    user = cfg.user(name)
    if user is None:
        raise HTTPException(401, "unknown user")
    if user.has_password:
        if not password or not hmac.compare_digest(user.password or "", password):
            raise HTTPException(401, "wrong password")
    return user


def get_config(request: Request) -> Config:
    return request.app.state.config


def current_user(request: Request) -> UserConfig:
    user = user_from_token(request.app.state.config, request.app.state.db, request.cookies.get(COOKIE))
    if user is None:
        raise HTTPException(401, "not logged in")
    return user


def require_gm(user: UserConfig = Depends(current_user)) -> UserConfig:
    if not user.is_gm:
        raise HTTPException(403, "GM only")
    return user


def ws_session(ws: WebSocket) -> tuple[UserConfig, str] | None:
    return session_from_token(ws.app.state.config, ws.app.state.db, ws.cookies.get(COOKIE))
