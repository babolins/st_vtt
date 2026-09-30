"""JSON Pointer (RFC 6901) based patching of JSON documents.

Ops:
  set          {"path", "value"}   replace; creates intermediates; "-" appends to lists
  remove       {"path"}
  list_add     {"path", "value"}   idempotent membership add on a list (created if missing)
  list_remove  {"path", "value"}   idempotent membership remove
  text_patch   {"path", "patch"}   apply a diff-match-patch patch to the string at path

Inside a list, a token `@<id>` selects the element whose "id" is <id>, so an edit still lands on
the right item after someone else inserts or deletes one above it. A missing id is an error,
except that removing an item that is already gone, or anything inside one, does nothing (so two
people deleting the same row delete one row).
"""

from __future__ import annotations

from typing import Any

from diff_match_patch import diff_match_patch

OPS = ("set", "remove", "list_add", "list_remove", "text_patch")
_dmp = diff_match_patch()


class PatchError(ValueError):
    pass


def split_pointer(path: str) -> list[str]:
    if path == "":
        return []
    if not path.startswith("/"):
        raise PatchError(f"pointer must start with '/': {path!r}")
    return [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]


def _by_id(container: list[Any], token: str) -> int | None:
    """Position of the element an `@<id>` token names, or None if there is none."""
    want = token[1:]
    return next((i for i, el in enumerate(container) if isinstance(el, dict) and el.get("id") == want), None)


def _index(container: Any, token: str, *, for_set: bool) -> int:
    if not isinstance(container, list):
        raise PatchError("expected list")
    if token.startswith("@"):
        i = _by_id(container, token)
        if i is None:
            raise PatchError(f"no list item with id {token[1:]!r}")
        return i
    if token == "-":
        if not for_set:
            raise PatchError("'-' only valid when appending")
        return len(container)
    try:
        i = int(token)
    except ValueError:
        raise PatchError(f"bad list index {token!r}") from None
    if i < 0 or i > len(container) or (not for_set and i == len(container)):
        raise PatchError(f"list index out of range: {i}")
    return i


def get_pointer(doc: Any, path: str) -> Any:
    node = doc
    for tok in split_pointer(path):
        if isinstance(node, dict):
            if tok not in node:
                raise PatchError(f"missing key {tok!r}")
            node = node[tok]
        elif isinstance(node, list):
            node = node[_index(node, tok, for_set=False)]
        else:
            raise PatchError(f"cannot descend into scalar at {tok!r}")
    return node


def apply_patch(doc: Any, path: str, value: Any = None, op: str = "set", patch: str | None = None) -> Any:
    """Apply in place and return the resulting value at `path` (None for remove). Raises PatchError."""
    tokens = split_pointer(path)
    if op not in OPS:
        raise PatchError(f"unknown op {op!r}")
    if op in ("list_add", "list_remove", "text_patch"):
        return _apply_merge_op(doc, path, value, op, patch)
    if not tokens:
        if op == "remove":
            raise PatchError("cannot remove root")
        if not isinstance(value, dict):
            raise PatchError("root replacement must be an object")
        doc.clear()
        doc.update(value)
        return doc
    node = doc
    for i, tok in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        if isinstance(node, dict):
            if tok not in node or node[tok] is None:
                if op == "remove":
                    raise PatchError(f"missing key {tok!r}")
                if nxt.startswith("@"):
                    raise PatchError(f"no list item with id {nxt[1:]!r}")
                node[tok] = [] if nxt == "-" or nxt.isdigit() else {}
            node = node[tok]
        elif isinstance(node, list):
            if op == "remove" and tok.startswith("@") and _by_id(node, tok) is None:
                return None  # what it would have removed went with the item
            node = node[_index(node, tok, for_set=False)]
        else:
            raise PatchError(f"cannot descend into scalar at {tok!r}")
    last = tokens[-1]
    if isinstance(node, dict):
        if op == "set":
            node[last] = value
        else:
            if last not in node:
                raise PatchError(f"missing key {last!r}")
            del node[last]
    elif isinstance(node, list):
        if op == "set":
            i = _index(node, last, for_set=True)
            if i == len(node):
                node.append(value)
            else:
                node[i] = value
        elif last.startswith("@") and _by_id(node, last) is None:
            return None  # already gone
        else:
            del node[_index(node, last, for_set=False)]
    else:
        raise PatchError(f"cannot set {last!r} on a scalar")
    return value if op == "set" else None


def _apply_merge_op(doc: Any, path: str, value: Any, op: str, patch: str | None) -> Any:
    """list_add / list_remove / text_patch: read-modify-write at `path`."""
    try:
        current = get_pointer(doc, path)
    except PatchError:
        current = None
    if op == "text_patch":
        if patch is None:
            raise PatchError("text_patch needs a patch")
        if current is None:
            current = ""
        if not isinstance(current, str):
            raise PatchError("text_patch target is not a string")
        try:
            patches = _dmp.patch_fromText(patch)
        except ValueError as e:
            raise PatchError(f"bad text patch: {e}") from e
        merged, _results = _dmp.patch_apply(patches, current)
        apply_patch(doc, path, merged, "set")
        return merged
    if current is None:
        current = []
    if not isinstance(current, list):
        raise PatchError(f"{op} target is not a list")
    if op == "list_add":
        if value not in current:
            current = [*current, value]
    else:
        current = [x for x in current if x != value]
    apply_patch(doc, path, current, "set")
    return current
