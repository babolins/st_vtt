"""Who may see or change what. Deliberately simple."""

from __future__ import annotations

from typing import Any

from .config import UserConfig

GM_ONLY_PATHS = ("/gm_notes", "/secret", "/visibility")
IMMUTABLE_PATHS = ("/pack_id", "/playbook")


class Forbidden(Exception):
    pass


def can_edit_character(user: UserConfig, char_owner: str | None) -> bool:
    return user.is_gm or (char_owner is not None and char_owner == user.name)


def check_patch(user: UserConfig, entity: str, owner: str | None, path: str, gm_only: bool = False) -> None:
    """Raise Forbidden if `user` may not patch `path` on this entity."""
    if entity == "character":
        if not can_edit_character(user, owner):
            raise Forbidden("you do not own this character")
    elif entity == "shared":
        if gm_only and not user.is_gm:
            raise Forbidden("GM only")
    elif entity == "record":
        # Collaborative by default: anyone at the table may write down what they
        # know about a person. A record the GM has hidden is theirs alone, and
        # `secret` and `visibility` are GM-only paths on every record.
        if gm_only and not user.is_gm:
            raise Forbidden("GM only")
    else:
        raise Forbidden(f"unknown entity {entity!r}")
    if any(path == p or path.startswith(p + "/") for p in IMMUTABLE_PATHS):
        raise Forbidden(f"{path} cannot be changed")
    if not user.is_gm and any(path == p or path.startswith(p + "/") for p in GM_ONLY_PATHS):
        raise Forbidden("GM only")
    if path == "":
        raise Forbidden("cannot replace the whole document")


def visible_to(user: UserConfig, visibility: list[str] | None) -> bool:
    """Chat visibility: None = public; otherwise a list of user names (GMs always see)."""
    if visibility is None:
        return True
    return user.is_gm or user.name in visibility


def strip_for_user(user: UserConfig, doc: dict[str, Any]) -> dict[str, Any]:
    """Remove GM-only fields for non-GM viewers."""
    if user.is_gm:
        return doc
    out = dict(doc)
    out.pop("gm_notes", None)
    out.pop("secret", None)
    return out
