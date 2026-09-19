"""Content pack models and loader.

A content pack describes a game (stats, moves, playbooks, shared sheets, ...)
and is supplied by the user as JSON. The pydantic models here are the source of
truth for the schema; `content/schema.json` is generated from them.
"""

from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Iterator
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from . import dice


class ContentError(Exception):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- pack meta


class Stat(Strict):
    id: str = Field(description="Short key used in moves, e.g. 'str'.")
    label: str = Field(description="Display label, e.g. 'STR'.")
    min: int = -3
    max: int = 3


class Debility(Strict):
    id: str
    label: str
    affects: list[str] = Field(default_factory=list, description="Stat ids that roll with disadvantage while marked.")
    text: str = ""


class Tier(Strict):
    label: str = Field(description="e.g. '10+', '7-9', '6-'. Used as the key in move outcomes.")
    min: int | None = None
    max: int | None = None

    def matches(self, total: int) -> bool:
        return (self.min is None or total >= self.min) and (self.max is None or total <= self.max)


DEFAULT_TIERS = [Tier(label="10+", min=10), Tier(label="7-9", min=7, max=9), Tier(label="6-", max=6)]


class RollRules(Strict):
    base: str = "2d6"
    advantage: str = "3d6kh2"
    disadvantage: str = "3d6kl2"
    tiers: list[Tier] = Field(default_factory=lambda: list(DEFAULT_TIERS))
    mark_xp_on: list[str] = Field(default_factory=lambda: ["6-"], description="Tier labels that suggest marking XP.")

    def tier_for(self, total: int) -> Tier | None:
        for t in self.tiers:
            if t.matches(total):
                return t
        return None


class XpRules(Strict):
    level_up_cost: str = Field(default="6 + 2*level", description="Arithmetic in `level`.")
    start_level: int = 1
    max_xp: int | None = None


class DicePreset(Strict):
    label: str
    expr: str = Field(description="Dice expression; may use {damage_die} or {<stat id>}.")


class LoadRules(Strict):
    light: int = 3
    normal: int = 6
    heavy: int = 9


class PackMeta(Strict):
    id: str
    name: str
    description: str = ""
    stats: list[Stat] = Field(min_length=1)
    stat_array: list[int] = Field(default_factory=list, description="Values to distribute at creation.")
    debilities: list[Debility] = Field(default_factory=list)
    roll: RollRules = Field(default_factory=RollRules)
    xp: XpRules = Field(default_factory=XpRules)
    dice_presets: list[DicePreset] = Field(default_factory=list)
    load: LoadRules | None = None
    gear_tags: list[str] = Field(default_factory=list)
    hold_names: list[str] = Field(default_factory=list, description="Extra hold currencies shown on every sheet.")


# --------------------------------------------------------------------------- moves


class Tracks(Strict):
    """The boxes the book prints, each drawn as its own glyph.

    The rulebook uses three: a square you tick to take a thing, a diamond for one box of carried
    load, and a circle for a use or an ammo status. `bulk` and `uses` are counts of boxes;
    `statuses` names them, and they are marked left to right (Book I, p94).
    """

    marks: int | None = Field(default=None, ge=1, le=20, description="Squares: plain ticks, e.g. progress towards a requirement.")
    bulk: int | None = Field(default=None, ge=1, le=20, description="Diamonds: boxes of carried load.")
    uses: int | None = Field(default=None, ge=1, le=20, description="Circles: charges, doses, hours.")
    statuses: list[str] = Field(default_factory=list, max_length=4, description="Named circles marked left to right, e.g. ['low ammo', 'all out'].")

    def any(self) -> bool:
        return bool(self.marks or self.bulk or self.uses or self.statuses)

    def kinds(self) -> dict[str, int]:
        """Track name -> number of boxes, for the kinds this thing actually declares."""
        out: dict[str, int] = {}
        if self.marks:
            out["marks"] = self.marks
        if self.bulk:
            out["bulk"] = self.bulk
        if self.uses:
            out["uses"] = self.uses
        if self.statuses:
            out["statuses"] = len(self.statuses)
        return out


class ModifierOption(Strict):
    label: str
    value: int


class Modifier(Strict):
    """A bounded, pack-declared choice the roll dialog offers instead of a free-form bonus."""

    id: str
    label: str
    options: list[ModifierOption] = Field(default_factory=list, min_length=1)
    default: int = 0
    help: str = ""

    @model_validator(mode="after")
    def _check(self) -> "Modifier":
        if all(o.value != self.default for o in self.options):
            raise ValueError(f"modifier {self.id!r}: default {self.default} is not one of its options")
        return self


class RollSpec(Strict):
    stat: str | list[str] | None = Field(
        default=None,
        description="A stat id, a list of stat ids the player chooses from, 'choose' for any stat, or null for +nothing. "
        "On a shared-sheet move, a stat id refers to that sheet's own stats.",
    )
    bonus: int = 0
    label: str | None = None
    modifiers: list[Modifier] = Field(default_factory=list, description="Bounded choices the roll dialog offers (e.g. an item's Value).")


class Hold(Strict):
    name: str
    note: str = ""


# --- what a roll's outcome can do to the sheet, so the chat card can offer it as a button


class XpAction(Strict):
    kind: Literal["xp"]
    n: int = 1
    label: str = ""


class HpAction(Strict):
    kind: Literal["hp"]
    amount: str = Field(description="Signed number or dice, e.g. '-3' or '-1d4' or '+1d8'.")
    label: str = ""


class HoldAction(Strict):
    kind: Literal["hold"]
    name: str
    n: int = 1
    label: str = ""


class DebilityAction(Strict):
    kind: Literal["debility"]
    id: str | None = Field(default=None, description="Omit to let the player choose which one to mark.")
    label: str = ""


class StatAction(Strict):
    kind: Literal["stat"]
    id: str
    delta: int
    label: str = ""


class SheetDebilityAction(Strict):
    kind: Literal["sheet_debility"]
    id: str
    label: str = ""


Action = Annotated[
    XpAction | HpAction | HoldAction | DebilityAction | StatAction | SheetDebilityAction,
    Field(discriminator="kind"),
]


class Outcome(Strict):
    """What a tier says, and optionally what it does."""

    text: str = ""
    apply: list[Action] = Field(default_factory=list, description="Offered as buttons on the roll card.")
    mark_xp: bool | None = Field(default=None, description="Override the tier's default; some outcomes say 'don't mark XP'.")

    @model_validator(mode="before")
    @classmethod
    def _plain_text(cls, value: Any) -> Any:
        return {"text": value} if isinstance(value, str) else value


class Requires(Strict):
    level: int | None = None
    moves: list[str] = Field(default_factory=list)


class Grant(Strict):
    """A move that lets you take moves from other playbooks (a "multiclass" move)."""

    from_playbooks: list[str] = Field(default_factory=list, description="Playbook ids; empty means any playbook but your own.")
    n: int = Field(default=1, ge=1, description="How many foreign moves this grant is worth.")
    exclude_tags: list[str] = Field(default_factory=list, description="Move tags this grant cannot pick, e.g. ['stat', 'multiclass'].")


class Move(Strict):
    id: str
    name: str
    trigger: str = ""
    text: str = Field(default="", description="Markdown body.")
    roll: RollSpec | None = None
    outcomes: dict[str, Outcome] = Field(default_factory=dict, description="Tier label -> markdown, or {text, apply}.")
    hold: Hold | None = None
    tracks: Tracks = Field(default_factory=Tracks, description="Boxes tracked on the move itself.")
    requires: Requires | None = None
    themes: list[str] = Field(
        default_factory=list,
        description="Free-form thematic grouping for browsing ('fighting', 'travel', 'talking'); the pack's own vocabulary, not the engine's.",
    )
    tags: list[str] = Field(default_factory=list)
    replaces: str | None = None
    insert: str | None = Field(default=None, description="Taking this move adds the named insert to the sheet.")
    grants: Grant | None = Field(default=None, description="Taking this move lets you pick moves from other playbooks.")
    options: list["Option"] = Field(
        default_factory=list,
        description="A checklist the move carries, e.g. \"each time you take this move, pick 1\". "
        "Picks are stored on the sheet under the move, and stay picked; a choice made at roll time belongs in `text`.",
    )
    min: int | None = Field(default=None, description="options: minimum picks required.")
    max: int | None = Field(default=None, description="options: maximum picks allowed. 1 makes it a single choice.")

    @model_validator(mode="after")
    def _check(self) -> "Move":
        if (self.min is not None or self.max is not None) and not self.options:
            raise ValueError(f"move {self.id!r}: min/max only apply to the move's own options")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"move {self.id!r}: min exceeds max")
        if self.max is not None and self.max > len(self.options):
            raise ValueError(f"move {self.id!r}: max exceeds the number of options")
        seen: set[str] = set()
        for o in walk_options(self.options):
            if o.id in seen:
                raise ValueError(f"move {self.id!r}: duplicate option id {o.id!r} (ids must be unique across nested options too)")
            seen.add(o.id)
            if o.effects:
                raise ValueError(f"move {self.id!r}: option {o.id!r} — a move's options cannot carry effects; put them on a section option")
        return self


# --------------------------------------------------------------------------- generic sections


class Effects(Strict):
    moves: list[str] = Field(default_factory=list)
    inserts: list[str] = Field(default_factory=list, description="Insert ids the sheet gains while this option is selected.")
    armor: int | None = None
    hp: int | None = None
    tags: list[str] = Field(default_factory=list)


class Option(Strict):
    id: str
    label: str
    text: str = ""
    effects: Effects | None = None
    tracks: Tracks = Field(default_factory=Tracks, description="Boxes tracked on the sheet while the option is selected.")
    write_in: str | None = Field(
        default=None,
        description="Show a one-line write-in box when this option is selected. The value is the input's placeholder; use \"\" for none.",
    )
    options: list["Option"] = Field(default_factory=list, description="A nested sub-choice, revealed only when this option is selected.")
    min: int | None = Field(default=None, description="Nested sub-choice: minimum picks required.")
    max: int | None = Field(default=None, description="Nested sub-choice: maximum picks allowed. 1 makes it a single choice.")
    note: bool = Field(
        default=False,
        description="Render as prose with no checkbox: a heading, an instruction, or (with tracks) a plain tracker. "
        "A note is never stored in the section's value and never applies effects; its nested options are always shown.",
    )

    @model_validator(mode="after")
    def _check(self) -> "Option":
        if (self.min is not None or self.max is not None) and not self.options:
            raise ValueError(f"option {self.id!r}: min/max only apply to a nested sub-choice")
        if self.note and self.effects:
            raise ValueError(f"option {self.id!r}: a note cannot be selected, so it cannot have effects")
        if self.note and self.write_in is not None:
            raise ValueError(f"option {self.id!r}: a note cannot be selected, so it cannot have a write-in")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"option {self.id!r}: min exceeds max")
        if self.max is not None and self.max > len(self.options):
            raise ValueError(f"option {self.id!r}: max exceeds the number of nested options")
        return self


Option.model_rebuild()
Move.model_rebuild()  # `Move.options` is declared before `Option` exists.


def walk_options(options: list[Option]) -> Iterator[Option]:
    """Every option in a tree, parents before children."""
    for o in options:
        yield o
        yield from walk_options(o.options)


class Column(Strict):
    id: str
    label: str
    type: Literal["text", "number", "check", "select", "dice"] = "text"
    options: list[str] = Field(default_factory=list)


class NameList(Strict):
    label: str
    names: list[str] = Field(default_factory=list, description="May be empty for a 'pick a name from any list' entry.")


class Line(Strict):
    """One row of a `lines` section: a set of options you pick exactly one of."""

    id: str
    label: str = ""
    options: list[Option] = Field(default_factory=list, min_length=1)
    write_in: str | None = Field(
        default=None,
        description="Show a write-in box at the end of the row for the \"or make something up\" case. "
        "The value is the input's placeholder; use \"\" for none.",
    )

    @model_validator(mode="after")
    def _check(self) -> "Line":
        for o in self.options:
            if o.options or o.tracks.any() or o.write_in is not None or o.effects or o.note:
                raise ValueError(
                    f"line {self.id!r}: option {o.id!r} — a line's options are plain labels "
                    "(no nesting, tracks, write-ins, effects or notes)"
                )
        return self


SectionType = Literal["choose", "multichoose", "checklist", "lines", "pips", "text", "table", "names"]


class Section(Strict):
    id: str
    title: str
    type: SectionType
    help: str = ""
    options: list[Option] = Field(default_factory=list, description="For choose/multichoose/checklist.")
    lines: list[Line] = Field(default_factory=list, description="For lines: one row of options each, pick 1 per row.")
    min: int | None = Field(default=None, description="multichoose: minimum picks required (creation checklist).")
    max: int | None = Field(default=None, description="multichoose: maximum picks. pips: number of pips.")
    columns: list[Column] = Field(default_factory=list, description="For table.")
    lists: list[NameList] = Field(default_factory=list, description="For names.")
    placeholder: str = ""
    required: bool = Field(default=True, description="Shown in the creation checklist when unfilled.")
    collapsed: bool = Field(default=False, description="Start folded shut on the sheet; for long reference lists.")
    start: Any = Field(default=None, description="Value a freshly created sheet gets, instead of the empty default for its type.")

    def all_options(self) -> Iterator[Option]:
        """Every option in the section, whether it hangs off `options` or off a line."""
        yield from walk_options(self.options)
        for line in self.lines:
            yield from walk_options(line.options)

    def line(self, lid: str) -> Line | None:
        return next((ln for ln in self.lines if ln.id == lid), None)

    @model_validator(mode="after")
    def _check(self) -> "Section":
        if self.type in ("choose", "multichoose", "checklist") and not self.options:
            raise ValueError(f"section {self.id!r} of type {self.type} needs options")
        if self.type == "lines" and not self.lines:
            raise ValueError(f"lines section {self.id!r} needs lines")
        if self.lines and self.type != "lines":
            raise ValueError(f"section {self.id!r}: lines only apply to a section of type 'lines'")
        # Line ids share a namespace with option ids: pips, write-ins and sub-picks are all keyed by them.
        seen: set[str] = set()
        for oid in [ln.id for ln in self.lines] + [o.id for o in self.all_options()]:
            if oid in seen:
                raise ValueError(f"section {self.id!r}: duplicate option id {oid!r} (ids must be unique across lines and nested options too)")
            seen.add(oid)
        if self.type == "table" and not self.columns:
            raise ValueError(f"table section {self.id!r} needs columns")
        if self.type == "names" and not self.lists:
            raise ValueError(f"names section {self.id!r} needs lists")
        if self.type == "pips" and not self.max:
            raise ValueError(f"pips section {self.id!r} needs max")
        self._check_start()
        return self

    def _check_start(self) -> None:
        """`start` must be a valid value for this section's type, so a new sheet is born well-formed."""
        v = self.start
        if v is None:
            return
        where = f"section {self.id!r}: start"
        pickable = {o.id for o in self.all_options() if not o.note}

        def known(oid: str) -> None:
            if oid not in pickable:
                raise ValueError(f"{where}: unknown option {oid!r}")

        if self.type in ("multichoose", "checklist"):
            if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
                raise ValueError(f"{where} must be a list of option ids")
            for x in v:
                known(x)
        elif self.type == "choose":
            if not isinstance(v, str):
                raise ValueError(f"{where} must be an option id")
            known(v)
        elif self.type == "lines":
            if not isinstance(v, dict):
                raise ValueError(f"{where} must be an object of line id -> option id")
            for lid, oid in v.items():
                line = self.line(lid)
                if line is None:
                    raise ValueError(f"{where}: unknown line {lid!r}")
                if oid is not None and oid not in {o.id for o in walk_options(line.options) if not o.note}:
                    raise ValueError(f"{where}: {oid!r} is not an option on line {lid!r}")
        elif self.type == "table":
            if not isinstance(v, list) or any(not isinstance(r, dict) for r in v):
                raise ValueError(f"{where} must be a list of row objects")
            cols = {c.id for c in self.columns}
            for row in v:
                for key in row:
                    if key not in cols:
                        raise ValueError(f"{where}: unknown column {key!r} (columns are {sorted(cols)})")
        elif self.type == "pips":
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= (self.max or 0):
                raise ValueError(f"{where} must be a number between 0 and {self.max}")
        elif self.type == "text":
            if not isinstance(v, str):
                raise ValueError(f"{where} must be a string")
        elif self.type == "names":
            if not isinstance(v, dict) or set(v) - {"origin", "name"}:
                raise ValueError(f"{where} must be an object with 'origin' and/or 'name'")


# --------------------------------------------------------------------------- playbooks


class ChooseN(Strict):
    n: int = Field(ge=1)
    from_: list[str] = Field(alias="from", min_length=1)
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StartingMoves(Strict):
    fixed: list[str] = Field(default_factory=list)
    choose: list[ChooseN] = Field(default_factory=list)


CORE_INSERTS = ("gear", "followers", "arcana")


class InsertDef(Strict):
    """A sheet insert: one of the half-sheets a game slips inside a playbook.

    `gear`, `followers` and `arcana` are built into the engine (the Inventory sheet and the
    generic follower sheet); everything else a pack wants — a warband, a spellbook, an animal
    companion, the ghost you become — is declared here. An insert is a small playbook:
    sections and moves that live on the sheet once it is taken.
    """

    id: str
    name: str
    kind: str = Field(default="playbook", description="Free-form grouping, e.g. 'playbook' or 'fate'.")
    blurb: str = ""
    description: str = Field(default="", description="Markdown shown at the top of the insert.")
    sections: list[Section] = Field(default_factory=list)
    moves: list[Move] = Field(default_factory=list)
    starting_moves: StartingMoves = Field(default_factory=StartingMoves, description="Moves gained with the insert; the rest are picked.")
    hold_names: list[str] = Field(default_factory=list)


class Playbook(Strict):
    id: str
    name: str
    blurb: str = ""
    hp_max: int = Field(ge=1)
    damage_die: str = "1d6"
    armor: int = 0
    stat_array: list[int] | None = None
    sections: list[Section] = Field(default_factory=list)
    moves: list[Move] = Field(default_factory=list)
    starting_moves: StartingMoves = Field(default_factory=StartingMoves)
    inserts: list[str] = Field(
        default_factory=lambda: ["gear"],
        description="Core sections ('gear', 'followers', 'arcana') and/or ids from the pack's `inserts`.",
    )
    hold_names: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- followers / arcana


class FollowerRules(Strict):
    loyalty_max: int = 3
    tags: list[str] = Field(default_factory=list)
    costs: list[str] = Field(default_factory=list)
    instincts: list[str] = Field(default_factory=list)
    fields: list[Column] = Field(default_factory=list, description="Extra per-follower fields.")


class Tracker(Strict):
    id: str
    label: str
    type: Literal["pips", "counter", "toggle"] = "pips"
    max: int | None = None


class Arcanum(Strict):
    id: str
    name: str
    kind: str = Field(default="minor", description="Free-form, e.g. 'major' or 'minor'.")
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    questions: list[str] = Field(default_factory=list)
    prerequisites: str = ""
    moves: list[Move] = Field(default_factory=list)
    trackers: list[Tracker] = Field(default_factory=list)


# --------------------------------------------------------------------------- shared sheets


class SheetStat(Strict):
    id: str
    label: str
    start: int = 0
    min: int = -3
    max: int = 3
    help: str = ""


class SharedSheetDef(Strict):
    """A template for a sheet the whole table (or only the GM) edits together: the village, a GM screen, ..."""

    id: str
    name: str = "Shared sheet"
    blurb: str = ""
    auto_create: bool = Field(default=False, description="Create one instance the first time the campaign runs.")
    visibility: Literal["table", "gm"] = Field(default="table", description="'gm' sheets are only visible to GMs.")
    stats: list[SheetStat] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)
    size_start: str | None = None
    debilities: list[Debility] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    moves: list[Move] = Field(default_factory=list)


# --------------------------------------------------------------------------- pack


class ContentPack(Strict):
    pack: PackMeta
    moves: dict[str, list[Move]] = Field(default_factory=dict, description="Move groups shared by all PCs, e.g. basic/special.")
    playbooks: list[Playbook] = Field(default_factory=list)
    inserts: list[InsertDef] = Field(default_factory=list)
    followers: FollowerRules = Field(default_factory=FollowerRules)
    arcana: list[Arcanum] = Field(default_factory=list)
    shared_sheets: list[SharedSheetDef] = Field(default_factory=list)

    # ---- lookups
    def shared_sheet(self, tid: str) -> SharedSheetDef | None:
        return next((t for t in self.shared_sheets if t.id == tid), None)

    def stat_ids(self) -> list[str]:
        return [s.id for s in self.pack.stats]

    def playbook(self, pid: str) -> Playbook | None:
        return next((p for p in self.playbooks if p.id == pid), None)

    def insert(self, iid: str) -> InsertDef | None:
        return next((i for i in self.inserts if i.id == iid), None)

    def sections_for(self, playbook_id: str | None, insert_ids: list[str] | None = None) -> list[Section]:
        """Every section on a character sheet: the playbook's, then each taken insert's."""
        pb = self.playbook(playbook_id) if playbook_id else None
        out = list(pb.sections) if pb else []
        for iid in insert_ids if insert_ids is not None else (pb.inserts if pb else []):
            ins = self.insert(iid)
            if ins:
                out.extend(ins.sections)
        return out

    def shared_moves(self) -> dict[str, Move]:
        return {m.id: m for group in self.moves.values() for m in group}

    def all_moves(self) -> dict[str, Move]:
        out = self.shared_moves()
        for p in self.playbooks:
            for m in p.moves:
                out[m.id] = m
        for i in self.inserts:
            for m in i.moves:
                out[m.id] = m
        for a in self.arcana:
            for m in a.moves:
                out[m.id] = m
        for t in self.shared_sheets:
            for m in t.moves:
                out[m.id] = m
        return out

    def find_move(self, move_id: str, playbook_id: str | None = None) -> Move | None:
        if playbook_id:
            pb = self.playbook(playbook_id)
            if pb:
                for m in pb.moves:
                    if m.id == move_id:
                        return m
        return self.all_moves().get(move_id)

    # ---- validation
    @model_validator(mode="after")
    def _cross_check(self) -> "ContentPack":
        errors: list[str] = []
        stat_ids = set(self.stat_ids())
        pack_debility_ids = {d.id for d in self.pack.debilities}
        if len(stat_ids) != len(self.pack.stats):
            errors.append("pack.stats: duplicate stat ids")
        for d in self.pack.debilities:
            for s in d.affects:
                if s not in stat_ids:
                    errors.append(f"pack.debilities[{d.id}].affects: unknown stat {s!r}")
        for i, preset in enumerate(self.pack.dice_presets):
            try:
                dice.parse(preset.expr, {"damage_die": "1d6", **{s: 0 for s in stat_ids}})
            except dice.DiceError as e:
                errors.append(f"pack.dice_presets[{i}] ({preset.label}): {e}")
        for expr_name, expr in (("base", self.pack.roll.base), ("advantage", self.pack.roll.advantage), ("disadvantage", self.pack.roll.disadvantage)):
            try:
                dice.parse(expr)
            except dice.DiceError as e:
                errors.append(f"pack.roll.{expr_name}: {e}")
        try:
            level_up_cost(self.pack.xp.level_up_cost, 1)
        except Exception as e:  # noqa: BLE001
            errors.append(f"pack.xp.level_up_cost: {e}")

        insert_ids = {i.id for i in self.inserts}

        def check_move(where: str, m: Move, own_stats: set[str] | None = None, own_debilities: set[str] | None = None) -> None:
            if m.insert and m.insert not in insert_ids:
                errors.append(f"{where}.insert: unknown insert {m.insert!r}")
            allowed = own_stats if own_stats is not None else stat_ids
            if m.roll and m.roll.stat is not None and m.roll.stat != "choose":
                stats = [m.roll.stat] if isinstance(m.roll.stat, str) else m.roll.stat
                for s in stats:
                    if s not in allowed:
                        errors.append(f"{where}.roll.stat: unknown stat {s!r} (available: {sorted(allowed)})")
            if m.roll:
                seen_mods: set[str] = set()
                for mod in m.roll.modifiers:
                    if mod.id in seen_mods:
                        errors.append(f"{where}.roll.modifiers: duplicate modifier id {mod.id!r}")
                    seen_mods.add(mod.id)
            tier_labels = {t.label for t in self.pack.roll.tiers}
            debility_ids = pack_debility_ids if own_debilities is None else own_debilities
            for label, outcome in m.outcomes.items():
                if label not in tier_labels:
                    errors.append(f"{where}.outcomes: unknown tier {label!r} (tiers are {sorted(tier_labels)})")
                for i, action in enumerate(outcome.apply):
                    aw = f"{where}.outcomes[{label}].apply[{i}]"
                    if isinstance(action, HpAction):
                        try:
                            dice.parse(action.amount)
                        except dice.DiceError as e:
                            errors.append(f"{aw}.amount: {e}")
                    elif isinstance(action, DebilityAction):
                        if action.id is not None and action.id not in debility_ids:
                            errors.append(f"{aw}.id: unknown debility {action.id!r}")
                    elif isinstance(action, StatAction):
                        if action.id not in allowed:
                            errors.append(f"{aw}.id: unknown stat {action.id!r} (available: {sorted(allowed)})")
                    elif isinstance(action, SheetDebilityAction):
                        if own_stats is None:
                            errors.append(f"{aw}: sheet_debility only applies to a shared-sheet move")
                        elif action.id not in debility_ids:
                            errors.append(f"{aw}.id: unknown debility {action.id!r}")

        seen_moves: dict[str, str] = {}
        for group, moves in self.moves.items():
            for m in moves:
                where = f"moves.{group}[{m.id}]"
                if m.id in seen_moves:
                    errors.append(f"{where}: duplicate move id (also in {seen_moves[m.id]})")
                seen_moves[m.id] = where
                check_move(where, m)
        if len(insert_ids) != len(self.inserts):
            errors.append("inserts: duplicate insert ids")
        for iid in sorted(insert_ids & set(CORE_INSERTS)):
            errors.append(f"inserts[{iid}]: {iid!r} is a built-in insert name, pick another id")

        def check_sheet(where: str, own_moves: list[Move], sections: list[Section], starting: StartingMoves) -> None:
            """Validate the moves and sections of a playbook or an insert."""
            own_ids = {m.id for m in own_moves}
            for m in own_moves:
                mw = f"{where}.moves[{m.id}]"
                if m.id in seen_moves:
                    errors.append(f"{mw}: duplicate move id (also in {seen_moves[m.id]})")
                seen_moves[m.id] = mw
                check_move(mw, m)
                if m.requires:
                    for r in m.requires.moves:
                        if r not in own_ids and r not in self.shared_moves():
                            errors.append(f"{mw}.requires.moves: unknown move {r!r}")
                if m.replaces and m.replaces not in own_ids:
                    errors.append(f"{mw}.replaces: unknown move {m.replaces!r}")
            known = own_ids | set(self.shared_moves())
            for r in starting.fixed:
                if r not in known:
                    errors.append(f"{where}.starting_moves.fixed: unknown move {r!r}")
            for c in starting.choose:
                for r in c.from_:
                    if r not in known:
                        errors.append(f"{where}.starting_moves.choose: unknown move {r!r}")
                if c.n > len(c.from_):
                    errors.append(f"{where}.starting_moves.choose: n={c.n} exceeds options")
            sec_ids: set[str] = set()
            for sec in sections:
                if sec.id in sec_ids:
                    errors.append(f"{where}.sections: duplicate section id {sec.id!r}")
                sec_ids.add(sec.id)
                for opt in sec.all_options():
                    if not opt.effects:
                        continue
                    ow = f"{where}.sections[{sec.id}].options[{opt.id}].effects"
                    for r in opt.effects.moves:
                        if r not in known:
                            errors.append(f"{ow}.moves: unknown move {r!r}")
                    for r in opt.effects.inserts:
                        if r not in insert_ids:
                            errors.append(f"{ow}.inserts: unknown insert {r!r}")

        for ins in self.inserts:
            check_sheet(f"inserts[{ins.id}]", ins.moves, ins.sections, ins.starting_moves)
        # A character keeps every section in one map, so an insert's ids must not collide with
        # another insert's or with a playbook it can be slipped into.
        insert_section_ids: dict[str, str] = {}
        for ins in self.inserts:
            for sec in ins.sections:
                if sec.id in insert_section_ids:
                    errors.append(f"inserts[{ins.id}].sections: section id {sec.id!r} is already used by inserts[{insert_section_ids[sec.id]}]")
                insert_section_ids[sec.id] = ins.id
        playbook_ids = {p.id for p in self.playbooks}
        for pb in self.playbooks:
            check_sheet(f"playbooks[{pb.id}]", pb.moves, pb.sections, pb.starting_moves)
            for m in pb.moves:
                if not m.grants:
                    continue
                where = f"playbooks[{pb.id}].moves[{m.id}].grants.from_playbooks"
                for other in m.grants.from_playbooks:
                    if other not in playbook_ids:
                        errors.append(f"{where}: unknown playbook {other!r}")
                    elif other == pb.id:
                        errors.append(f"{where}: {other!r} is this move's own playbook")
            if pb.stat_array is not None and len(pb.stat_array) != len(self.pack.stats):
                errors.append(f"playbooks[{pb.id}].stat_array: expected {len(self.pack.stats)} values")
            for iid in pb.inserts:
                if iid not in CORE_INSERTS and iid not in insert_ids:
                    errors.append(f"playbooks[{pb.id}].inserts: unknown insert {iid!r} (built-ins are {sorted(CORE_INSERTS)})")
            for sec in pb.sections:
                if sec.id in insert_section_ids:
                    errors.append(f"playbooks[{pb.id}].sections: section id {sec.id!r} clashes with inserts[{insert_section_ids[sec.id]}]")
        if self.pack.stat_array and len(self.pack.stat_array) != len(self.pack.stats):
            errors.append(f"pack.stat_array: expected {len(self.pack.stats)} values")
        pb_ids = [p.id for p in self.playbooks]
        if len(set(pb_ids)) != len(pb_ids):
            errors.append("playbooks: duplicate playbook ids")
        arc_ids = [a.id for a in self.arcana]
        if len(set(arc_ids)) != len(arc_ids):
            errors.append("arcana: duplicate arcanum ids")
        for a in self.arcana:
            for m in a.moves:
                check_move(f"arcana[{a.id}].moves[{m.id}]", m)
        tids = [t.id for t in self.shared_sheets]
        if len(set(tids)) != len(tids):
            errors.append("shared_sheets: duplicate template ids")
        for t in self.shared_sheets:
            own = {st.id for st in t.stats}
            for m in t.moves:
                check_move(f"shared_sheets[{t.id}].moves[{m.id}]", m, own_stats=own, own_debilities={d.id for d in t.debilities})
            if t.size_start and t.size_start not in t.sizes:
                errors.append(f"shared_sheets[{t.id}].size_start: not in sizes")
            sec_ids = set()
            for sec in t.sections:
                if sec.id in sec_ids:
                    errors.append(f"shared_sheets[{t.id}].sections: duplicate section id {sec.id!r}")
                sec_ids.add(sec.id)

        # A move's own options are stored beside a section's, keyed by the id of whatever owns
        # them — so a move that carries options must not be named after a section on the same sheet.
        def check_option_owners(where: str, moves: list[Move], section_ids: dict[str, str]) -> None:
            for m in moves:
                if m.options and m.id in section_ids:
                    errors.append(f"{where}[{m.id}].options: this move's id is already a section id ({section_ids[m.id]}), pick another")

        char_sections: dict[str, str] = {}
        for pb in self.playbooks:
            for sec in pb.sections:
                char_sections.setdefault(sec.id, f"playbooks[{pb.id}].sections")
        for ins in self.inserts:
            for sec in ins.sections:
                char_sections.setdefault(sec.id, f"inserts[{ins.id}].sections")
        for group, moves in self.moves.items():
            check_option_owners(f"moves.{group}", moves, char_sections)
        for pb in self.playbooks:
            check_option_owners(f"playbooks[{pb.id}].moves", pb.moves, char_sections)
        for ins in self.inserts:
            check_option_owners(f"inserts[{ins.id}].moves", ins.moves, char_sections)
        for a in self.arcana:
            check_option_owners(f"arcana[{a.id}].moves", a.moves, char_sections)
        for t in self.shared_sheets:
            own_sections = {sec.id: f"shared_sheets[{t.id}].sections" for sec in t.sections}
            check_option_owners(f"shared_sheets[{t.id}].moves", t.moves, own_sections)

        if errors:
            raise ValueError("\n".join(errors))
        return self


def level_up_cost(formula: str, level: int) -> int:
    """Evaluate a tiny arithmetic formula in `level` (digits, + - * / ( ) only)."""
    allowed = set("0123456789+-*/() level")
    if not set(formula) <= allowed:
        raise ValueError(f"illegal characters in formula {formula!r}")
    return int(eval(formula, {"__builtins__": {}}, {"level": level}))  # noqa: S307


# --------------------------------------------------------------------------- loading


LIST_KEYS = {"playbooks", "inserts", "arcana", "shared_sheets"}
OBJECT_KEYS = {"pack", "followers"}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContentError(f"{path}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}") from e


def merge_pack_files(root: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    """Merge every *.json under `root` into one raw pack dict.

    Files directly inside a `playbooks/` or `arcana/` directory are single
    entries. Other files contribute top-level keys: list keys concatenate,
    `moves` groups concatenate, object keys must appear in exactly one file.
    Returns (raw, origins) where origins maps "key" -> file for error messages.
    """
    raw: dict[str, Any] = {}
    origins: dict[str, Path] = {}
    files = sorted(p for p in root.rglob("*.json") if not p.name.startswith("."))
    if not files:
        raise ContentError(f"no .json files found under {root}")
    for f in files:
        data = _read_json(f)
        parent = f.parent.name
        if parent in LIST_KEYS and f.parent != root:
            if not isinstance(data, dict):
                raise ContentError(f"{f}: expected a single object")
            raw.setdefault(parent, []).append(data)
            origins[f"{parent}[{data.get('id', len(raw[parent]) - 1)}]"] = f
            continue
        if not isinstance(data, dict):
            raise ContentError(f"{f}: top level must be an object")
        for key, val in data.items():
            if key in LIST_KEYS:
                if not isinstance(val, list):
                    raise ContentError(f"{f}: {key} must be a list")
                raw.setdefault(key, []).extend(val)
                for item in val:
                    if isinstance(item, dict):
                        origins[f"{key}[{item.get('id')}]"] = f
            elif key == "moves":
                if not isinstance(val, dict):
                    raise ContentError(f"{f}: moves must be an object of group -> list")
                groups = raw.setdefault("moves", {})
                for g, moves in val.items():
                    if not isinstance(moves, list):
                        raise ContentError(f"{f}: moves.{g} must be a list")
                    groups.setdefault(g, []).extend(moves)
                    origins[f"moves.{g}"] = f
            elif key in OBJECT_KEYS:
                if key in raw:
                    raise ContentError(f"{f}: {key!r} already defined in {origins[key]}")
                raw[key] = val
                origins[key] = f
            else:
                raise ContentError(f"{f}: unknown top-level key {key!r}")
    return raw, origins


def _format_validation_error(e: ValidationError, source: str, origins: dict[str, Path]) -> str:
    lines = [f"{source}: content pack is invalid"]
    for err in e.errors():
        loc_parts = [str(x) for x in err["loc"]]
        loc = ".".join(loc_parts) or "<root>"
        origin = ""
        if loc_parts:
            head = loc_parts[0]
            if head in LIST_KEYS and len(loc_parts) > 1:
                # try to name the entry by id via origins
                for k, f in origins.items():
                    if k.startswith(head + "["):
                        origin = ""  # ambiguous by index; keep loc only
                        break
            elif head == "moves" and len(loc_parts) > 1:
                origin = f" (in {origins.get(f'moves.{loc_parts[1]}', '')})"
            elif head in origins:
                origin = f" (in {origins[head]})"
        msg = err["msg"]
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        for line in msg.splitlines():
            lines.append(f"  {loc}: {line}{origin}")
    return "\n".join(lines)


def load_content(path: str | Path) -> ContentPack:
    path = Path(path)
    if not path.exists():
        raise ContentError(f"content pack not found: {path}")
    origins: dict[str, Path] = {}
    if path.is_dir():
        raw, origins = merge_pack_files(path)
    else:
        raw = _read_json(path)
    try:
        return ContentPack.model_validate(raw)
    except ValidationError as e:
        raise ContentError(_format_validation_error(e, str(path), origins)) from e


def json_schema() -> dict[str, Any]:
    return ContentPack.model_json_schema()
