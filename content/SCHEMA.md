# Writing a content pack

A content pack tells st_vtt what game it is running: the stats, how rolls
work, the shared moves, each playbook, the village sheet, follower rules, and
a library of arcana. The engine renders sheets from it and never needs code
changes for new content.

`content/schema.json` is a JSON Schema generated from the server models; point
your editor at it for autocomplete and validation. `uv run st-vtt validate
<path>` checks a pack and reports errors with the file and field involved.
`content/example/` is a small pack that uses every feature.

## Files

A pack is a **directory** (recommended) or a single JSON file. In a directory,
every `*.json` file is merged:

- `pack` and `followers` are objects and may appear in exactly one file each.
- `playbooks`, `inserts`, `arcana` and `shared_sheets` are lists; lists from
  several files concatenate. A file placed directly inside a `playbooks/`,
  `inserts/`, `arcana/` or `shared_sheets/` sub-directory is a single entry.
- `moves` is an object of `group name -> list of moves`; groups from several
  files concatenate.

All text fields marked *markdown* support a small subset: paragraphs, `**bold**`,
`*italic*`, `` `code` `` and `- ` bullet lists.

The one-line fields a sheet displays take the same emphasis, minus the
paragraphs and lists: an option's `label` and `text`, a line's `label`, a
section's `help`, a playbook's or insert's `blurb`, a move's `trigger`, and an
arcanum's `prerequisites`. So a tag reads as `*far*`, not as bare asterisks.
Markup is escaped before it is rendered, so a pack can emphasise a word but
never inject HTML.

Unknown keys are errors, so typos are caught.

## `pack`

```json
{
  "pack": {
    "id": "mygame",
    "name": "My Game",
    "description": "optional",
    "stats": [{"id": "str", "label": "STR", "min": -1, "max": 3}, ...],
    "stat_array": [2, 1, 1, 0, 0, -1],
    "debilities": [{"id": "battered", "label": "Battered", "affects": ["str", "dex"], "text": "..."}],
    "roll": {
      "base": "2d6", "advantage": "3d6kh2", "disadvantage": "3d6kl2",
      "tiers": [{"label": "10+", "min": 10}, {"label": "7-9", "min": 7, "max": 9}, {"label": "6-", "max": 6}],
      "mark_xp_on": ["6-"]
    },
    "xp": {"level_up_cost": "6 + 2*level", "start_level": 1},
    "dice_presets": [{"label": "Damage", "expr": "{damage_die}"}, {"label": "d6", "expr": "1d6"}],
    "load": {"light": 3, "normal": 6, "heavy": 9},
    "gear_tags": ["hand", "close", "piercing"],
    "hold_names": ["Guard"]
  }
}
```

| field | meaning |
|---|---|
| `stats` | The stat blocks on every sheet. `id` is what moves refer to. |
| `stat_array` | Values to distribute at creation; the checklist compares the sheet against it. A playbook can override with its own `stat_array`. |
| `debilities` | Checkboxes on the sheet. `affects` lists stat ids that roll with disadvantage while marked; the roll dialog applies it automatically. |
| `roll` | Dice expressions for a normal / advantage / disadvantage roll, and the result tiers. Tier labels are the keys used in a move's `outcomes`. |
| `xp.level_up_cost` | Arithmetic in `level`, e.g. `6 + 2*level`. |
| `dice_presets` | Buttons in the dice bar. `{damage_die}` and `{<stat id>}` resolve against the rolling character. |
| `load` | Optional. Load thresholds. The Gear header sums every ◇ carried — gear item `bulk` plus any `bulk` box marked on a section option — and labels it light / normal / heavy. |
| `hold_names` | Hold counters shown on every sheet in addition to those introduced by moves. |

## Moves

Moves appear in `moves` (shared by everyone, grouped), in a playbook's
`moves`, in an arcanum's `moves`, and in a shared sheet's `moves`. Move ids must be
unique across the whole pack.

```json
{
  "id": "brawl",
  "name": "Brawl",
  "trigger": "When you trade blows with something up close...",
  "text": "...roll +STR.",
  "roll": {"stat": "str", "bonus": 0},
  "outcomes": {"10+": "...", "7-9": "...", "6-": "..."},
  "hold": {"name": "Guard", "note": "Spend 1 Guard to..."},
  "tracks": {"uses": 3},
  "requires": {"level": 2, "moves": ["other_move_id"]},
  "replaces": "other_move_id",
  "tags": ["starting"]
}
```

| field | meaning |
|---|---|
| `roll.stat` | A stat id; a list of stat ids the player chooses between; `"choose"` for any stat; or `null` for a "+nothing" roll. Omit `roll` for moves that do not roll. On a **shared-sheet move**, a stat id refers to that sheet's own stats (see below). |
| `roll.bonus` | Flat bonus added to the roll. |
| `roll.modifiers` | Bounded choices the roll dialog offers as dropdowns instead of free-form typing. See below. |
| `outcomes` | Per tier label: markdown, or `{text, apply, mark_xp}` — see **Outcomes that apply themselves**. |
| `hold` | Declares a hold currency; a counter for it appears in the sheet's Hold row. |
| `tracks` | Boxes tracked on the move — see **Boxes**. |
| `requires` | Level gate and/or prerequisite moves. Shown as a warning in the move picker, not enforced. |
| `replaces` | Taking this move removes the named one. |
| `themes` | Free-form groupings for browsing in the move finder (`"fighting"`, `"travel"`, …), in the pack's own words. Moves without any are grouped by where they come from. |
| `insert` | Taking this move adds the named insert to the sheet (and removing it takes it away). |
| `grants` | Taking this move lets you pick moves from other playbooks — see **Borrowing moves**. |
| `options` | A checklist the move carries, with `min`/`max` picks — see **Moves that carry a checklist**. |

### Boxes

Options and moves can carry boxes, and the kind says what the box *means*. Declare only the kinds
a thing actually has; a thing can have several (a crossbow takes one box of load and tracks its
ammo):

```json
{"id": "crossbow", "label": "Crossbow", "tracks": {"bulk": 1, "statuses": ["low ammo", "all out"]}}
{"id": "whisky",   "label": "Skins of fine whisky", "tracks": {"uses": 2}}
```

| kind | drawn as | meaning |
|---|---|---|
| `marks` | □ square | a plain tick: progress towards something, a requirement met |
| `bulk` | ◇ diamond | one box of carried load; the Gear header totals these against `pack.load` |
| `uses` | ○ circle | charges, doses, hours — spend them and they are gone |
| `statuses` | ○ circle, labelled | a named track marked left to right, e.g. `["low ammo", "all out"]` |

Because the app draws the boxes, never also spell them out in the text.

### Outcomes that apply themselves

A tier's value can be plain markdown, or an object that also says what the outcome *does*. The
roll card shows a button per action, which whoever may edit that sheet can click; each applies
once and the card records who applied it.

```json
"outcomes": {
  "7-9": {"text": "Hold 1 Focus (or 2 if you took your time).",
          "apply": [{"kind": "hold", "name": "Focus", "n": 1},
                    {"kind": "hold", "name": "Focus", "n": 2, "label": "Hold 2 (took your time)"}]},
  "6-": {"text": "Don't mark XP; you know there's a trap, but nothing bad happens yet.",
         "mark_xp": false}
}
```

Several actions on one tier are the alternatives the player picks between, which is how the book
writes them. `label` overrides the button text.

| kind | fields | applies to |
|---|---|---|
| `xp` | `n` | the character's XP |
| `hp` | `amount` — a signed number or dice, e.g. `-1d4`, `+3` | current HP, clamped to 0..max |
| `hold` | `name`, `n` | that hold counter |
| `debility` | `id` — omit to let the player choose | that debility |
| `stat` | `id`, `delta` | a shared sheet's stat, clamped to its min/max |
| `sheet_debility` | `id` | a shared sheet's debility |

**Marking XP needs no authoring**: any tier in `pack.roll.mark_xp_on` gets a Mark XP button for
free. Set `"mark_xp": false` on the outcome for the moves that say *don't* mark XP.

### Borrowing moves

Some moves let you take a move from another playbook. Tag the moves a grant may not pick — a
game usually bars the stat-raising moves, and these moves themselves:

```json
{"id": "well_travelled", "name": "Well Travelled", "tags": ["multiclass"],
 "grants": {"from_playbooks": ["scout", "healer"], "n": 1,
            "exclude_tags": ["stat", "multiclass"]}}
```

An empty `from_playbooks` means any playbook but your own. While the character holds an unspent
grant, the move picker offers those moves under **From other playbooks**; borrowed moves are extra,
so they do not count against the playbook's own move budget.

A move you can take more than once (the book prints `□□□` beside it) is simply several moves:
give each repeat its own id and point its `requires.moves` at the one before.

### Moves that carry a checklist

Some moves print a list you tick and keep ticked — *"each time you take this move, pick 1"*. Give
the move `options`, the same shape a section's options take, with `min`/`max` for how many to pick
(`"max": 1` makes it a single choice):

```json
{"id": "seasoned_band", "name": "Seasoned Band",
 "text": "Each time you take this move, pick 1. You can also reselect their Instinct.",
 "min": 1, "max": 1,
 "options": [
   {"id": "band_tags", "label": "Select 2 new tags for your band"},
   {"id": "band_damage", "label": "Increase their damage die from d6 to d8"},
   {"id": "band_hp", "label": "Increase their max HP by 2 each"}
 ]}
```

An option here may carry `tracks`, a `write_in` box, a `note` and a nested sub-choice, exactly as
a section's option does — but **not `effects`**: a move's picks do not add moves, inserts, armor
or HP. Put anything that changes the sheet on a section option instead.

A list the player chooses from *at the time they roll* is not this — it belongs in `text` or in the
outcome, because nothing about it is kept. ("Spend 1 Focus and pick 1" is prose; "each time you
take this move, pick 1" is options.)

Because the picks are stored under the move's id, alongside a section's under its own, a move
carrying options may not share its id with a section on the same sheet; `validate` says so if it does.

## Playbooks

```json
{
  "id": "wanderer",
  "name": "The Wanderer",
  "blurb": "Knows every road.",
  "hp_max": 18,
  "damage_die": "1d8",
  "armor": 0,
  "stat_array": null,
  "inserts": ["gear", "followers", "arcana"],
  "hold_names": [],
  "sections": [ ... ],
  "starting_moves": {"fixed": ["well_traveled"], "choose": [{"n": 1, "from": ["watchful", "iron_gut"]}]},
  "moves": [ ... ]
}
```

- `inserts` lists the half-sheets this playbook comes with: the core ones the
  engine draws (`gear`, `followers`, `arcana`) and/or ids from the pack's
  `inserts` (see below). Stats, moves and notes always appear.
- `starting_moves.fixed` are added on creation; each `choose` group shows up in
  the creation checklist until `n` of `from` are taken.
- The expected number of playbook moves is starting moves plus one per level
  above `start_level`; the Moves header hints when more can be picked.

### Sections

Everything playbook-specific that is not a move is a **section**. Sections
render in order, above the Moves section, and store their value in the
character document under `sections.<id>`.

| type | value stored | fields |
|---|---|---|
| `choose` | option id or null | `options` |
| `multichoose` | list of option ids | `options`, `min`, `max` |
| `checklist` | list of option ids | `options` |
| `lines` | `{line id: option id}` | `lines` — one row of options each, pick 1 per row |
| `pips` | number | `max` — a resource track (Stock, Omens), drawn as circles |
| `text` | string (markdown) | `placeholder` |
| `table` | list of row objects | `columns` |
| `names` | `{"origin": list label, "name": chosen name}` | `lists` — clicking a name also sets the character's name |

Common fields: `id`, `title`, `help` (shown under the title), `required`
(default `true`; unfilled required sections appear in the creation checklist),
`collapsed` (start folded shut — for long reference lists), and `start` (the
value a freshly created sheet gets instead of an empty one; it must be valid
for the section's type, so a `table` takes a list of rows and a `multichoose`
a list of option ids). `start` applies when a sheet is created, so adding one
does not backfill the sheets that already exist.

**Lines.** For the "choose 1 on each line, or make something up" blocks:

```json
{"id": "appearance", "title": "Appearance", "type": "lines",
 "help": "Choose 1 on each line, or make something up.",
 "lines": [
   {"id": "age", "write_in": "or make something up",
    "options": [{"id": "age_young", "label": "young & brash"},
                {"id": "age_old", "label": "old & leathery"}]},
   {"id": "voice", "options": [{"id": "voice_soft", "label": "soft-spoken"}]}
 ]}
```

Each line renders as one row of radio buttons with an optional write-in box at
the end; a line's options are plain labels (no boxes, write-ins, effects or
nesting of their own). Line ids share the option-id namespace, since the
write-in is stored as `option_text.<section>.<line>`.

Options: `{"id", "label", "text", "effects", "tracks", "write_in", "options", "note"}`.
`tracks` gives the option boxes on the sheet while it is selected (see **Boxes**
above). `effects` lets a choice change the sheet without engine support:

```json
{"id": "trailhand", "label": "Trailhand", "text": "You learned the roads by walking them.", "effects": {"moves": ["trailsense"], "inserts": ["crew"], "armor": 1, "hp": 2, "tags": ["respected"]}}
```

Selecting the option adds the moves and inserts and adds to armor / max HP;
deselecting reverses it. (`checklist` sections do not apply effects.)

**Notes.** `"note": true` makes an option prose instead of a pick: no checkbox,
never stored in the section's value, never applies effects. Use it for the
numbered instructions in a block of introductions, and for a plain labelled
tracker (a note with `tracks`). A note's nested options are **always** shown,
where a normal option reveals its children only while it is selected — which is
how a section can interleave instructions with bounded question lists:

```json
{"id": "intro_4", "label": "4-5. The folk of the village", "note": true, "min": 1, "max": 2,
 "text": "Answer one of these, then go around again and answer another, or pass.",
 "options": [{"id": "npc_kin", "label": "Who is your closest kin?", "write_in": "your answer"}]}
```

**Write-ins.** Set `"write_in": "placeholder text"` on an option and a
one-line input appears beneath it while it is selected, for the "or make
something up" cases. Use `""` for no placeholder. The value is stored per
option, so it survives deselecting and re-selecting.

**Nested sub-choices.** An option can carry its own `options`, revealed only
while the parent is selected, with `min` and `max` bounding the picks. A `max`
of 1 renders the children as radio buttons; anything else renders checkboxes
and disables the rest once the maximum is reached. Children can have their own
`tracks` and `write_in`, and can nest further.

```json
{
  "id": "weapons_of_war", "label": "Weapons of war", "text": "Choose up to 3.",
  "max": 3,
  "options": [
    {"id": "wow_sword", "label": "Sword, iron", "text": "*close*, +1 damage", "tracks": {"bulk": 1}},
    {"id": "wow_other", "label": "Something else", "tracks": {"bulk": 2}, "write_in": "what is it?"}
  ]
}
```

Option ids must be unique across a section's whole tree, since boxes, write-ins,
and sub-picks are all keyed by section and option id.

Table columns: `{"id", "label", "type"}` with type `text` (default), `number`,
`check`, `select` (with `options`), or `dice`. A `dice` cell holds a dice
expression such as `1d8+1` and gets a Roll button; the roll is labelled with
the row's first text column, so an NPC table rolls "Bandit · Damage".

## `inserts`

An insert is one of the half-sheets a PC slips inside their playbook: the warband
one playbook commands, the spellbook another carries, the ghost you become when
you die badly. It is a small playbook of its own — sections and moves that appear
on the sheet once it is taken.

```json
{
  "id": "ghost",
  "name": "Ghost",
  "kind": "fate",
  "blurb": "When you die but your soul lingers...",
  "description": "markdown",
  "sections": [ ...same section types as playbooks... ],
  "moves": [ ...moves... ],
  "starting_moves": {"fixed": ["unliving"], "choose": []},
  "hold_names": ["Fury"]
}
```

A sheet gets an insert three ways: the playbook lists it in `inserts`, an
option's `effects.inserts` grants it, or a move's `insert` field does. Players
can also add or drop one from the Inserts section — that is how the ones you are
not born with arrive, mid-campaign.

`starting_moves.fixed` are taken with the insert; the rest are offered under
"More from this insert". Because a character keeps all its sections in one map,
an insert's section ids must be unique across every insert **and** every
playbook it could join; `validate` checks this.

## `shared_sheets`

Shared sheets are edited by the whole table (or only by the GM). The village
is one; a GM screen is another. The pack defines **templates**; the GM creates
instances in the app.

```json
{
  "shared_sheets": [
    {
      "id": "village",
      "name": "The Village",
      "blurb": "The home everyone shares.",
      "auto_create": true,
      "visibility": "table",
      "stats": [{"id": "luck", "label": "Luck", "start": 1, "min": -3, "max": 3, "help": "..."}],
      "sizes": ["camp", "hamlet", "village", "town"],
      "size_start": "village",
      "debilities": [{"id": "hungry", "label": "Hungry", "text": "..."}],
      "sections": [ ...same section types as playbooks... ],
      "moves": [ ... ]
    },
    {
      "id": "gm_screen",
      "name": "GM Screen",
      "visibility": "gm",
      "sections": [{"id": "npcs", "title": "NPCs", "type": "table",
                    "columns": [{"id": "name", "label": "Name"}, {"id": "hp", "label": "HP", "type": "number"}, {"id": "damage", "label": "Damage", "type": "dice"}]}]
    }
  ]
}
```

| field | meaning |
|---|---|
| `auto_create` | Create one instance the first time the campaign starts (once; deleting it does not bring it back). |
| `visibility` | `table` (default): everyone sees and edits it. `gm`: only GMs see it, edit it, or receive its updates. |
| `stats`, `sizes`, `debilities` | Optional. Omit them for a sheet that is just sections. |

Shared-sheet moves get Roll buttons too, and they roll the sheet's **own** stats.
A move on the template above can say `"roll": {"stat": "defenses"}`; the dialog
reads the current value straight off the sheet, the way a character move reads
+STR. Character debilities never apply to a shared-sheet roll.

### Bounded modifiers

When a roll needs a number the player chooses (an item's Value, a situational
penalty), declare it as a `modifier` rather than asking them to type a bonus.
The dialog renders a dropdown limited to the options you list, and the roll card
shows which one was picked:

```json
"roll": {
  "stat": "prosperity",
  "modifiers": [{
    "id": "value",
    "label": "Item Value",
    "help": "Subtracted from the roll.",
    "default": 0,
    "options": [
      {"label": "Value 0", "value": 0},
      {"label": "Value 1", "value": -1},
      {"label": "Value 2", "value": -2}
    ]
  }]
}
```

`default` must be one of the option values, and the server refuses any value the
move did not declare. The free-form bonus field is still there for one-off
situational modifiers, bounded to -10..+10.

## `followers`

```json
{
  "followers": {
    "loyalty_max": 3,
    "tags": ["loyal", "brave", "cunning", "green"],
    "costs": ["coin", "respect"],
    "instincts": ["to look after their own"],
    "fields": [{"id": "origin", "label": "Origin"}]
  }
}
```

Followers are created on the sheet. `tags`, `costs` and `instincts` are
suggestions offered while typing; `fields` adds extra text fields to every
follower. Followers already carry name, tags, HP, armor, damage die, instinct,
cost, loyalty, moves, gear, notes, and optional group members.

## `arcana`

```json
{
  "id": "wayfinding_stone",
  "name": "The Wayfinding Stone",
  "kind": "minor",
  "tags": ["small", "fragile"],
  "description": "markdown",
  "questions": ["Who lost it before you?"],
  "prerequisites": "Spend a night meditating on what you have lost.",
  "moves": [ ...moves... ],
  "trackers": [{"id": "charges", "label": "Charges", "type": "pips", "max": 3}, {"id": "attuned", "label": "Attuned", "type": "toggle"}]
}
```

Library arcana are copied onto a sheet when added, so later edits to the pack
do not rewrite what a player already has. Players can also write custom arcana
directly on the sheet. Tracker types: `pips`, `counter`, `toggle`.

## Character JSON

An exported character is the raw document the server stores:

```json
{
  "pack_id": "mygame", "playbook": "wanderer", "name": "...", "pronouns": "", "look": "",
  "stats": {"str": 2}, "hp": {"current": 18, "max": 18}, "armor": 1, "xp": 0, "level": 1,
  "debilities": {"battered": false},
  "moves": {"taken": ["well_traveled"], "tracks": {"iron_gut": {"uses": 2}}, "hold": {"Focus": 1},
            "options": {"hardened": ["hardened_knack"]}},
  "inserts": ["gear", "followers", "arcana", "pack_mule"],
  "sections": {"background": "trailhand", "appearance": {"age": "age_young", "voice": null}},
  "option_tracks": {"possessions": {"kit": {"bulk": 1, "uses": 2}}},
  "gear": {"items": [{"id": "x", "name": "Walking staff", "tags": ["reach"], "bulk": 1, "uses": null, "statuses": [], "statuses_marked": 0, "notes": ""}]},
  "followers": [], "arcana": [], "custom_moves": [],
  "notes": "", "gm_notes": "", "creation_done": false
}
```

You can write one by hand and import it. Missing fields are filled with
defaults; unknown playbooks or move ids are reported as warnings and kept.

A sheet is built from the pack when it is created, and not revisited: editing a
pack does not migrate the sheets already made from it. While the game is in
development, the simplest course after a breaking pack change is to delete the
database and start the campaign again.
