"""Who may see or change what. Deliberately simple."""

from __future__ import annotations

from typing import Any

from .config import UserConfig

# Per entity, the fields the table never sees. A hidden field is GM-only to write,
# stripped from every document a player is sent, and neither its patches nor anyone's
# presence on it reach the table. Top-level names only: stripping removes keys.
HIDDEN_FIELDS: dict[str, tuple[str, ...]] = {
    "character": ("gm_notes",),
    "shared": ("gm_notes",),
    "record": ("secret",),
}
# Per entity, fields only the GM may write but everyone may read.
GM_WRITE_FIELDS: dict[str, tuple[str, ...]] = {
    "record": ("visibility",),
}
IMMUTABLE_PATHS = ("/pack_id", "/playbook")
# `kind` mirrors the records table's own column, and `created_by` decides who may
# delete a record; both are fixed at creation, for the GM too.
RECORD_IMMUTABLE_PATHS = ("/kind", "/created_by")
# `template` mirrors the shared_sheets table's own column, which import keeps it equal to.
SHARED_IMMUTABLE_PATHS = ("/template",)


class Forbidden(Exception):
    pass


def _under(path: str, fields: tuple[str, ...]) -> bool:
    return any(path == f"/{f}" or path.startswith(f"/{f}/") for f in fields)


def is_hidden_path(entity: str | None, path: str | None) -> bool:
    """Whether `path` is, or lies inside, one of this entity's hidden fields."""
    return isinstance(path, str) and _under(path, HIDDEN_FIELDS.get(entity or "", ()))


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
        # its `secret` and `visibility` are the GM's on every record.
        if gm_only and not user.is_gm:
            raise Forbidden("GM only")
    else:
        raise Forbidden(f"unknown entity {entity!r}")
    immutable = IMMUTABLE_PATHS + {"record": RECORD_IMMUTABLE_PATHS, "shared": SHARED_IMMUTABLE_PATHS}.get(entity, ())
    if any(path == p or path.startswith(p + "/") for p in immutable):
        raise Forbidden(f"{path} cannot be changed")
    if not user.is_gm and (is_hidden_path(entity, path) or _under(path, GM_WRITE_FIELDS.get(entity, ()))):
        raise Forbidden("GM only")
    if path == "":
        raise Forbidden("cannot replace the whole document")


def visible_to(user: UserConfig, visibility: list[str] | None) -> bool:
    """Chat visibility: None = public; otherwise a list of user names (GMs always see)."""
    if visibility is None:
        return True
    return user.is_gm or user.name in visibility


def strip_for_user(user: UserConfig, entity: str, doc: dict[str, Any]) -> dict[str, Any]:
    """Remove this entity's hidden fields for non-GM viewers."""
    if user.is_gm:
        return doc
    out = dict(doc)
    for field in HIDDEN_FIELDS.get(entity, ()):
        out.pop(field, None)
    return out
