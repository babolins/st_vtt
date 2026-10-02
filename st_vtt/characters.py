"""Character and shared-sheet document construction, import validation, level-up."""

from __future__ import annotations

import copy
import uuid
from typing import Any, Iterator

from .content import ContentPack, Playbook, Section, SharedSheetDef, level_up_cost


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def new_character(pack: ContentPack, playbook: Playbook, name: str) -> dict[str, Any]:
    stats = {s.id: 0 for s in pack.pack.stats}
    doc: dict[str, Any] = {
        "pack_id": pack.pack.id,
        "playbook": playbook.id,
        "name": name,
        "pronouns": "",
        "look": "",
        "stats": stats,
        "hp": {"current": playbook.hp_max, "max": playbook.hp_max},
        "armor": playbook.armor,
        "xp": 0,
        "level": pack.pack.xp.start_level,
        "debilities": {d.id: False for d in pack.pack.debilities},
        "moves": {
            "taken": list(playbook.starting_moves.fixed),
            "tracks": {},
            "hold": {},
            "options": {},
        },
        "inserts": list(playbook.inserts),
        "sections": {},
        "option_tracks": {},
        "option_text": {},
        "sub_choices": {},
        "gear": {"items": []},
        "followers": [],
        "arcana": [],
        "custom_moves": [],
        "notes": "",
        "gm_notes": "",
        "creation_done": False,
    }
    for iid in playbook.inserts:
        ins = pack.insert(iid)
        if ins:
            doc["moves"]["taken"].extend(m for m in ins.starting_moves.fixed if m not in doc["moves"]["taken"])
    for sec in pack.sections_for(playbook.id):
        doc["sections"][sec.id] = default_section_value(sec)
    return doc


def default_section_value(sec: Section) -> Any:
    """The value a freshly created sheet gets for `sec`: its `start`, else empty for its type."""
    if sec.start is not None:
        if sec.type == "table":  # rows are patched by id: /sections/<id>/@<row id>/<column>
            return [{"id": new_id(), **copy.deepcopy(row)} for row in sec.start]
        return copy.deepcopy(sec.start)
    if sec.type == "lines":
        return {line.id: None for line in sec.lines}
    return {
        "choose": None,
        "multichoose": [],
        "checklist": [],
        "pips": 0,
        "text": "",
        "table": [],
        "names": {"origin": "", "name": ""},
    }[sec.type]


def new_record(kind: str, name: str, *, by: str | None = None) -> dict[str, Any]:
    """A person (or faction, or place) the campaign wants to remember.

    Fields chosen from what a real session's notes carry: nearly every NPC there
    is pronouns, a role, a home, a standing, and above all *ties* — someone's
    deputy, someone's sidekick, the one who sold the town out. So ties are a
    typed list from the start rather than prose in `notes`, or nothing could
    ever read them back.

    `secret` is the GM's copy of the truth beside what the table believes;
    `visibility` hides the whole record, for the things the table should not
    know exists yet.
    """
    doc: dict[str, Any] = {
        "kind": kind,
        "name": name.strip(),
        "pronouns": "",
        "role": "",
        "home": "",
        "status": "",
        "tags": [],
        "ties": [],
        "notes": "",
        "secret": "",
        "visibility": "table",
        "created_by": by,
    }
    if kind == "event":
        # Not one date in thirteen pages of real notes: "nine years ago", "before
        # Glenys was born", "last spring". So an event says when in words, and
        # sorts by a number the table can nudge.
        doc["when"] = ""
        doc["order"] = 0
        doc["involves"] = []
    return doc


def new_shared_sheet(pack: ContentPack, tpl: SharedSheetDef, name: str | None = None) -> dict[str, Any]:
    return {
        "pack_id": pack.pack.id,
        "template": tpl.id,
        "name": (name or "").strip() or tpl.name,
        "stats": {s.id: s.start for s in tpl.stats},
        "size": tpl.size_start or (tpl.sizes[0] if tpl.sizes else ""),
        "debilities": {d.id: False for d in tpl.debilities},
        "sections": {sec.id: default_section_value(sec) for sec in tpl.sections},
        "option_tracks": {},
        "option_text": {},
        "sub_choices": {},
        "moves": {"tracks": {}, "hold": {}, "options": {}},
        "notes": "",
        "gm_notes": "",
    }


def level_cost(pack: ContentPack, level: int) -> int:
    return level_up_cost(pack.pack.xp.level_up_cost, level)


def table_section_ids(pack: ContentPack, entity: str) -> set[str]:
    """Ids of every table section in the pack a character (or shared sheet) could have."""
    owners = [*pack.playbooks, *pack.inserts] if entity == "character" else pack.shared_sheets
    return {sec.id for o in owners for sec in o.sections if sec.type == "table"}


def _fill_ids(items: Any) -> bool:
    """Give each object in a list a unique string id; True if any changed. Other elements are skipped."""
    if not isinstance(items, list):
        return False
    changed = False
    seen: set[str] = set()
    for el in items:
        if not isinstance(el, dict):
            continue
        iid = el.get("id")
        if not isinstance(iid, str) or not iid or iid in seen:
            el["id"] = iid = new_id()
            changed = True
        seen.add(iid)
    return changed


def ensure_list_ids(pack: ContentPack, doc: dict[str, Any], entity: str) -> bool:
    """Give an id to every item of the lists that patches address by id (`/gear/items/@<id>/name`).

    In place; True if anything changed. Sheets made before items were addressed by id, and imports,
    can lack them, and a copy-pasted item can share one. Table sections are looked up across the
    whole pack, not just this sheet's playbook and inserts: a dropped insert keeps its rows, and they
    need ids if it is taken again. A section id can name a table in one playbook and something else
    in another, which is harmless because only tables store lists of objects (the rest store option
    ids, scalars or objects), and only objects get ids.
    """
    lists: list[Any] = []
    if entity == "character":
        gear = doc.get("gear")
        followers = doc.get("followers")
        lists += [gear.get("items") if isinstance(gear, dict) else None, followers, doc.get("arcana"), doc.get("custom_moves")]
        if isinstance(followers, list):
            lists += [f.get("members") for f in followers if isinstance(f, dict)]
    elif entity == "record":
        lists.append(doc.get("ties"))
    if entity in ("character", "shared"):
        sections = doc.get("sections")
        if isinstance(sections, dict):
            lists += [sections.get(sid) for sid in table_section_ids(pack, entity)]
    changed = False
    for items in lists:
        changed = _fill_ids(items) or changed
    return changed


# The numbers a roll adds up or an outcome counts on, which have to be whole numbers.
# "*" is every key of that object.
WHOLE_NUMBERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "character": (("stats", "*"), ("hp", "current"), ("hp", "max"), ("xp",), ("level",), ("armor",), ("moves", "hold", "*")),
    "shared": (("stats", "*"), ("moves", "hold", "*")),
}


def is_whole_number(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _number_slots(entity: str, doc: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any] | None, str]]:
    """(path, object, key) for each number `doc` holds where WHOLE_NUMBERS names one; the
    object is None when what is at `path` should be an object of them and isn't. Paths
    that aren't there are skipped."""
    for pattern in WHOLE_NUMBERS.get(entity, ()):
        nodes: list[tuple[Any, str]] = [(doc, "")]
        for depth, tok in enumerate(pattern):
            found: list[tuple[Any, str]] = []
            for node, path in nodes:
                if not isinstance(node, dict):
                    yield path, None, ""
                    continue
                for key in (list(node) if tok == "*" else [tok] if tok in node else []):
                    if depth == len(pattern) - 1:
                        yield f"{path}/{key}", node, key
                    else:
                        found.append((node[key], f"{path}/{key}"))
            nodes = found


def bad_numbers(entity: str, doc: dict[str, Any]) -> list[str]:
    """What is wrong with `doc`'s numbers, one line each (none if nothing)."""
    problems = (
        f"{path} must be an object" if node is None else f"{path} must be a whole number"
        for path, node, key in _number_slots(entity, doc)
        if node is None or not is_whole_number(node[key])
    )
    return list(dict.fromkeys(problems))


def validate_import(pack: ContentPack, doc: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Coerce an imported character into a well-formed document.

    Returns (doc, warnings). Unknown playbooks/moves are warnings, not errors;
    missing keys are filled with defaults.
    """
    warnings: list[str] = []
    if not isinstance(doc, dict):
        raise ValueError("character must be a JSON object")
    pb_id = doc.get("playbook")
    playbook = pack.playbook(pb_id) if isinstance(pb_id, str) else None
    if not pack.playbooks:
        # Nothing to shape the sheet by, and nothing could create one here either.
        raise ValueError(f"pack {pack.pack.id!r} has no playbooks, so it can't hold a character")
    if playbook is None:
        warnings.append(f"unknown playbook {pb_id!r}; sheet will render with generic sections only")
        template = new_character(pack, pack.playbooks[0], "")
        template["playbook"] = pb_id or ""
        template["sections"] = {}
    else:
        template = new_character(pack, playbook, "")
    if doc.get("pack_id") and doc["pack_id"] != pack.pack.id:
        warnings.append(f"character was exported from pack {doc['pack_id']!r}, current pack is {pack.pack.id!r}")
    merged = deep_fill(doc, template)
    merged["pack_id"] = pack.pack.id
    known = set(pack.all_moves()) | {m.get("id") for m in merged.get("custom_moves", []) if isinstance(m, dict)}
    for mid in merged["moves"].get("taken", []):
        if mid not in known:
            warnings.append(f"unknown move {mid!r} kept as-is")
    for sid in list(merged["stats"]):
        if sid not in pack.stat_ids():
            warnings.append(f"unknown stat {sid!r} dropped")
            del merged["stats"][sid]
    merged.pop("id", None)
    merged.pop("owner", None)
    merged.pop("revision", None)
    ensure_list_ids(pack, merged, "character")
    return merged, warnings


def deep_fill(doc: Any, template: Any) -> Any:
    """Return doc with any keys missing (relative to template) filled in."""
    if isinstance(template, dict):
        if not isinstance(doc, dict):
            return template
        out = dict(doc)
        for k, v in template.items():
            out[k] = deep_fill(doc.get(k), v) if k in doc else v
        return out
    return template if doc is None else doc
