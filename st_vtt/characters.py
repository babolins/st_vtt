"""Character and shared-sheet document construction, import validation, level-up."""

from __future__ import annotations

import copy
import uuid
from typing import Any

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
    return {
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


def new_follower(pack: ContentPack) -> dict[str, Any]:
    return {
        "id": new_id(),
        "name": "",
        "tags": [],
        "hp": {"current": 3, "max": 3},
        "armor": 0,
        "damage_die": "1d4",
        "instinct": "",
        "cost": "",
        "loyalty": 0,
        "moves": "",
        "gear": "",
        "notes": "",
        "is_group": False,
        "members": [],
        "fields": {},
    }


def arcanum_instance(pack: ContentPack, arcanum_id: str | None) -> dict[str, Any]:
    """A per-sheet copy of a library arcanum (or a blank custom one)."""
    inst: dict[str, Any] = {
        "id": new_id(),
        "ref": arcanum_id,
        "name": "",
        "kind": "minor",
        "tags": [],
        "description": "",
        "questions": [],
        "answers": {},
        "prerequisites": "",
        "moves": [],
        "trackers": [],
        "state": {},
        "notes": "",
    }
    if arcanum_id:
        src = next((a for a in pack.arcana if a.id == arcanum_id), None)
        if src:
            inst.update(src.model_dump(mode="json", exclude={"id"}))
            inst["state"] = {t.id: (False if t.type == "toggle" else 0) for t in src.trackers}
    return inst


def level_cost(pack: ContentPack, level: int) -> int:
    return level_up_cost(pack.pack.xp.level_up_cost, level)


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
    if playbook is None:
        warnings.append(f"unknown playbook {pb_id!r}; sheet will render with generic sections only")
        template = new_character(pack, pack.playbooks[0], "") if pack.playbooks else {}
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
