"""Server configuration loaded from a JSON file (users, roles, paths)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator


class ConfigError(Exception):
    pass


# Secrets config.example.json has shipped with. Anyone who has read it could sign a login
# cookie with one, as any user, the GM included.
PLACEHOLDER_SECRETS = frozenset({"change-me", "change-me-to-something-random"})


class UserConfig(BaseModel):
    name: str
    role: Literal["gm", "player"] = "player"
    password: str | None = None

    @property
    def is_gm(self) -> bool:
        return self.role == "gm"

    @property
    def has_password(self) -> bool:
        return bool(self.password)


class Config(BaseModel):
    campaign_name: str = "My Campaign"
    content_pack: str = "content/example"
    database: str = "data/campaign.db"
    host: str = "0.0.0.0"
    port: int = 8000
    # Signs the login cookie. Left out, one is made for the campaign and kept in its database.
    secret: str | None = None
    users: list[UserConfig] = Field(min_length=1)
    # One active browser per user: a new login replaces (or is refused by) an existing one.
    single_session: bool = True
    # Directory containing the built frontend (index.html + assets/).
    static_dir: str = "frontend/dist"
    # Resolved at load time; base for relative paths above.
    base_dir: Path = Field(default_factory=Path.cwd, exclude=True)

    @field_validator("users")
    @classmethod
    def _unique_names(cls, users: list[UserConfig]) -> list[UserConfig]:
        seen: set[str] = set()
        for u in users:
            key = u.name.strip().lower()
            if not key:
                raise ValueError("user name must not be empty")
            if key in seen:
                raise ValueError(f"duplicate user name: {u.name!r}")
            seen.add(key)
        return users

    @field_validator("secret")
    @classmethod
    def _not_a_placeholder(cls, secret: str | None) -> str | None:
        if secret in PLACEHOLDER_SECRETS:
            raise ValueError(
                "is still the example's placeholder, so anyone could sign in as anyone. "
                "Delete the line to have one made for you, or set it to a long random string."
            )
        return secret

    def user(self, name: str) -> UserConfig | None:
        for u in self.users:
            if u.name == name:
                return u
        return None

    def resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else self.base_dir / p

    @property
    def content_path(self) -> Path:
        return self.resolve(self.content_pack)

    @property
    def database_path(self) -> Path:
        return self.resolve(self.database)

    @property
    def static_path(self) -> Path:
        return self.resolve(self.static_dir)


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"config file not found: {path}\n"
            f"Copy config.example.json to {path.name} and edit it."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: invalid JSON at line {e.lineno}: {e.msg}") from e
    try:
        cfg = Config.model_validate({**raw, "base_dir": path.resolve().parent})
    except ValidationError as e:
        lines = [f"{path}: invalid config"]
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"]) or "<root>"
            lines.append(f"  {loc}: {err['msg'].removeprefix('Value error, ')}")
        raise ConfigError("\n".join(lines)) from e
    return cfg
