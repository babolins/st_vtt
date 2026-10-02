"""Move rolls: base dice + stat + bonus, advantage/disadvantage, tier resolution."""

from __future__ import annotations

from typing import Any, Callable

from . import dice
from .content import ContentPack, Move

# Free-form bonus range accepted from clients, so a stray keystroke can't produce a nonsense roll.
MIN_BONUS = -10
MAX_BONUS = 10


class SheetError(ValueError):
    """A sheet holds something a roll can't count with."""


def sheet_number(doc: dict[str, Any], *path: str, default: int = 0) -> int:
    """The number at `path` in a sheet, or `default` when it isn't there.

    Patches and imports keep these whole numbers, but a sheet saved before they did may
    hold anything; that is reported, not crashed on.
    """
    node: Any = doc
    for depth, key in enumerate(path):
        if not isinstance(node, dict):
            raise SheetError(f"this sheet's /{'/'.join(path[:depth])} must be an object")
        if key not in node:
            return default
        node = node[key]
    try:
        return int(node)
    except (TypeError, ValueError):
        raise SheetError(f"this sheet's /{'/'.join(path)} is {node!r}, not a whole number") from None


def debility_disadvantage(pack: ContentPack, doc: dict[str, Any], stat: str | None) -> list[str]:
    """Labels of marked debilities that affect `stat`."""
    if stat is None:
        return []
    marked = doc.get("debilities") or {}
    return [d.label for d in pack.pack.debilities if marked.get(d.id) and stat in d.affects]


def roll_move(
    pack: ContentPack,
    *,
    doc: dict[str, Any] | None,
    move: Move | None,
    stat: str | None,
    advantage: bool = False,
    disadvantage: bool = False,
    bonus: int = 0,
    label: str | None = None,
    stat_source: dict[str, str] | None = None,
    modifiers: list[dict[str, Any]] | None = None,
    rng: Callable[[int, int], int] | None = None,
) -> dict[str, Any]:
    """Roll the pack's base dice for a move. Returns a chat payload dict.

    `stat_source` maps stat id -> display label; when given (a shared sheet's own
    stats) it replaces the pack's character stats and debilities never apply.
    """
    rules = pack.pack.roll
    auto = debility_disadvantage(pack, doc or {}, stat) if (doc and stat_source is None) else []
    if auto:
        disadvantage = True
    if advantage and disadvantage:
        expr, mode = rules.base, "both"
    elif advantage:
        expr, mode = rules.advantage, "advantage"
    elif disadvantage:
        expr, mode = rules.disadvantage, "disadvantage"
    else:
        expr, mode = rules.base, "normal"
    stat_mod = 0
    stat_label = None
    if stat is not None:
        stat_mod = sheet_number(doc or {}, "stats", stat)
        if stat_source is not None:
            stat_label = stat_source.get(stat, stat)
        else:
            stat_def = next((s for s in pack.pack.stats if s.id == stat), None)
            stat_label = stat_def.label if stat_def else stat
    if move and move.roll:
        bonus += move.roll.bonus
    chosen: list[dict[str, Any]] = list(modifiers or [])
    bonus += sum(int(m["value"]) for m in chosen)
    result = dice.roll(expr, rng=rng)
    total = result.total + stat_mod + bonus
    tier = rules.tier_for(total)
    outcome = move.outcomes.get(tier.label) if (move and tier) else None
    mark_xp = bool(tier and tier.label in rules.mark_xp_on)
    if outcome is not None and outcome.mark_xp is not None:
        mark_xp = outcome.mark_xp
    actions = outcome_actions(outcome, mark_xp)
    return {
        "type": "move",
        "label": label or (move.name if move else "Roll"),
        "move_id": move.id if move else None,
        "character": (doc or {}).get("name"),
        "stat": stat,
        "stat_label": stat_label,
        "stat_mod": stat_mod,
        "bonus": bonus,
        "modifiers": chosen,
        "mode": mode,
        "auto_disadvantage": auto,
        "roll": result.to_dict(),
        "total": total,
        "tier": tier.label if tier else None,
        "outcome": outcome.text if outcome else None,
        "mark_xp": mark_xp,
        "actions": actions,
    }


def outcome_actions(outcome: Any, mark_xp: bool) -> list[dict[str, Any]]:
    """What the roll card can offer to apply. Marking XP is implied by the tier, not authored."""
    out: list[dict[str, Any]] = []
    if mark_xp:
        out.append({"kind": "xp", "n": 1, "label": "Mark XP"})
    for action in outcome.apply if outcome else []:
        out.append(action.model_dump(mode="json"))
    for action in out:
        action.setdefault("label", "")
        if not action["label"]:
            action["label"] = describe_action(action)
    return out


def describe_action(action: dict[str, Any]) -> str:
    """A button label, when the pack does not give one."""
    kind = action["kind"]
    if kind == "xp":
        return f"Mark {action['n']} XP" if action["n"] != 1 else "Mark XP"
    if kind == "hp":
        amount = str(action["amount"])
        return f"{'Lose' if amount.startswith('-') else 'Regain'} {amount.lstrip('+-')} HP"
    if kind == "hold":
        return f"Hold {action['n']} {action['name']}"
    if kind == "debility":
        return "Mark a debility" if action.get("id") is None else f"Mark {action['id']}"
    if kind == "stat":
        return f"{action['delta']:+d} {action['id'].title()}"
    if kind == "sheet_debility":
        return f"Mark {action['id']}"
    return kind


def roll_expr(
    pack: ContentPack,
    expr: str,
    doc: dict[str, Any] | None = None,
    label: str | None = None,
    rng: Callable[[int, int], int] | None = None,
) -> dict[str, Any]:
    """Roll a free-form expression; {damage_die} and {stat} refs resolve against `doc`."""
    refs: dict[str, str | int] = {}
    if doc:
        pb = pack.playbook(doc.get("playbook", ""))
        refs["damage_die"] = pb.damage_die if pb else "1d6"
        for sid in pack.stat_ids():
            refs[sid] = sheet_number(doc, "stats", sid)
    else:
        refs["damage_die"] = "1d6"
        for s in pack.pack.stats:
            refs[s.id] = 0
    result = dice.roll(expr, refs=refs, rng=rng)
    return {
        "type": "dice",
        "label": label or expr,
        "character": (doc or {}).get("name"),
        "roll": result.to_dict(),
        "total": result.total,
    }
