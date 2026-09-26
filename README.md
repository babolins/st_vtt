# st_vtt — Shared Table

**st** for *Shared Table*: a small, self-hosted, **sheet-first** virtual tabletop
for Stonetop and other Powered-by-the-Apocalypse games. There is no battle map: the play space is the
character sheets, shared sheets such as the town everyone lives in, and a chat with dice rolls.

- Multiple players and a GM edit sheets at the same time; changes appear live,
  simultaneous edits to the same text are merged, and you can see who is
  editing which field.
- Everything persists in a single SQLite file.
- Users and roles come from a config file. Optional passwords, nothing fancier.
- The game content (playbooks, moves, shared sheets such as the village, followers, arcana) is
  **not** built in. You supply it as a JSON content pack. See
  [content/SCHEMA.md](content/SCHEMA.md).
- Characters and shared sheets import/export as JSON.
- Light and dark themes.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node 20+ (only to build the frontend once)

## Setup

```bash
uv sync
cd frontend && npm install && npm run build && cd ..
cp config.example.json config.json   # then edit users, secret, content_pack
```

## Run

```bash
uv run st-vtt serve
```

Open `http://<your-machine>:8000/`. Players on the same LAN, VPN, or Tailscale
network use the same URL. Pick your name on the login page; enter a password
only if your user has one in the config.

### Behind a reverse proxy

To serve the app under a sub-path rather than at the root, build the frontend
with `VITE_BASE` set to that path:

```bash
cd frontend && VITE_BASE=/stonetop/ npm run build
```

Every asset, `/api` and `/ws` URL the page requests then carries that prefix, so
the proxy has to be mounted at exactly the same path. The server keeps its
ordinary root-mounted routes, so the proxy must strip the prefix again before
forwarding — `tailscale serve --set-path=/stonetop http://127.0.0.1:8000` does
that, as does nginx's `location /stonetop/ { proxy_pass http://127.0.0.1:8000/; }`
(mind the trailing slash). It must forward WebSocket upgrades too, or sheets
stop updating live.

Other commands:

```bash
uv run st-vtt validate content/example        # check a content pack
uv run st-vtt schema -o content/schema.json   # regenerate the JSON Schema
uv run st-vtt serve --reload                  # auto-reload while hacking
```

## Config

`config.json`:

```json
{
  "campaign_name": "My Campaign",
  "content_pack": "content/example",
  "database": "data/campaign.db",
  "host": "0.0.0.0",
  "port": 8000,
  "secret": "change-me-to-something-random",
  "users": [
    {"name": "Brendan", "role": "gm"},
    {"name": "Alice", "role": "player"},
    {"name": "Bob", "role": "player", "password": "optional-password"}
  ]
}
```

- `role` is `gm` or `player`. Any number of GMs is fine.
- `secret` signs the login cookie. Change it once; changing it again logs
  everyone out.
- `content_pack` is a directory of JSON files (merged) or a single JSON file.
- `single_session` (default `true`): each user can be signed in from one
  browser at a time. Signing in elsewhere is refused while the first browser
  is connected, with an option to take over that signs the other one out.
  Set it to `false` to allow the same user on several devices at once.
- Relative paths are resolved from the config file's directory.

### Running more than one game

Every campaign is a config file. To host different groups, keep one config
per group, each with its own `users`, `database`, `campaign_name`, and, if the
groups play different games, `content_pack`:

```bash
uv run st-vtt serve -c groups/tuesday.json
```

Relative paths inside a config are resolved from that config file's
directory, so a layout like `groups/tuesday.json` with
`"database": "tuesday.db"` keeps each group's data beside its config. Only one
server runs per config; start the one for tonight's group.

Who can do what:

| action                              | owner | other player | GM |
|-------------------------------------|:-----:|:------------:|:--:|
| view any character / table shared sheets |  yes  |     yes      | yes|
| edit own character                  |  yes  |      no      | yes|
| edit a table shared sheet (e.g. the village) | yes | yes    | yes|
| see or edit a GM-only shared sheet  |  no   |      no      | yes|
| GM notes on a sheet                 |  no   |      no      | yes|
| create / import a character         |  yes  |     yes      | yes|
| delete a character                  |  yes  |      no      | yes|
| reassign a character's owner        |  no   |      no      | yes|
| create / delete / import a shared sheet | no |     no      | yes|
| request a roll, clear chat, export campaign | no | no | yes|

Characters are created in the app; ownership is stored in the database, so you
never edit the config to hand out characters.

## Shared sheets

The content pack defines **shared-sheet templates** (see
[content/SCHEMA.md](content/SCHEMA.md)). The village is one of them. A
template with `auto_create` is created once when the campaign first starts;
the GM adds more from **GM tools → New shared sheet** and can delete, export,
or replace any of them. A template with `"visibility": "gm"` is only visible
to GMs, which is how you get a private GM screen for NPCs and threats without
any special engine feature.

## Playing

- **Sheets** are collapsible; the open/closed state is remembered per browser.
- **Editing together**: any field someone else is editing shows an outline and
  a badge with their name. Text fields merge simultaneous edits instead of
  overwriting each other, so two people can write in the village notes at
  once. Table cells and option checkboxes are updated individually.
- **Character creation** is done on the sheet itself. A checklist at the top
  lists the choices the playbook still needs (stats, backgrounds, starting
  moves, and so on). Hide it when you are done.
- **Moves** with a roll have a **Roll** button. The dialog picks the stat,
  applies advantage/disadvantage, and automatically applies disadvantage from
  marked debilities. The result card shows the dice, the tier (10+ / 7-9 / 6-)
  and the move's outcome text.
- **Share** on any move card (or **Share text** in the roll dialog) posts the
  move's trigger, text and outcomes to the chat as a card, for everyone to read.
- The chat shows who is typing.
- **Chat commands**: `/roll 2d6+1` (or `/r`), `/gmroll 1d20` (only you and the
  GM see it), `/w Name text` to whisper, `/gm text` to whisper all GMs.
  Dice expressions support `NdM`, `+`/`-`, `khN`/`klN` (keep highest/lowest),
  and `{damage_die}` / `{str}` references that resolve against your character.
- **Level up** appears when XP reaches the pack's level-up cost. It spends the
  XP and bumps the level; then pick a new move from **+ Move**.
- **Followers**, **arcana**, and **gear** live in their own sections when the
  playbook enables those inserts. Arcana can be added from the pack's library or
  written on the spot. Options with uses (a healer's kit, say) show ◇ pips.
- **Inserts** are the half-sheets a playbook comes with (a warband, a book of
  spells) plus any the pack defines for later — the ones you gain by dying badly,
  say. Each brings its own sections and moves; a playbook, a choice, or a move can
  hand you one, and you can add or drop them yourself.
- A choice can open a **sub-choice** when you pick it (choose up to three
  weapons, each with its own boxes) and can reveal a **write-in box** for the
  "or make something up" options. **Lines** are the "choose 1 on each line"
  blocks: one row of options each, with room to write your own.
- **Boxes mean what their shape says**, as in the book: a ◇ diamond is one box of
  carried load and counts towards your load; a ○ circle is a use or a named ammo
  status (*low ammo*, *all out*) marked left to right; a □ square is a plain tick.
- **Roll cards apply their own outcomes.** Mark XP, lose 1d4 HP, hold 3 of a move's
  currency, mark a debility, drop a shared sheet's stat — each is a button on the
  card in chat, for whoever may edit that sheet. Clicking it patches the sheet, rolls
  any dice involved, and records on the card who applied it; each one applies once.
- Some moves let you **take a move from another playbook**; while you hold an
  unspent pick the move picker offers those under "From other playbooks".
- **A move can carry its own checklist** — "each time you take this move, pick 1".
  The list sits on the move's card with boxes and write-ins of its own, and what
  you tick stays ticked.
- Table columns of type `dice` (an NPC's damage, for example) have a Roll button.
- **Shared-sheet moves roll that sheet's own stats.** A village move that rolls
  +Walls reads the value off the sheet, so there is nothing to type. Where a
  move needs a player choice, the pack can declare a dropdown of allowed values
  (an item's Value, say) instead of a free-form number.
- **GM tools** (header button): ask a player to roll something, create shared
  sheets, export the whole campaign, clear the chat.

## Import / export

- Each character has an export button (⇩) that downloads its JSON. Import via
  **+ Character → Import JSON…**. Unknown moves or playbooks are kept and
  reported as warnings, not errors.
- Shared sheets export the same way (⇩ in their header). The GM can replace one
  from a file (⇧).
- **Export campaign** dumps every character, every shared sheet, and the chat log.

## Backups

Everything is in the SQLite file named by `database`. Copy it while the server
is stopped, or use `Export campaign`.

## Development

```bash
uv run pytest                    # backend tests
cd frontend && npm run dev       # Vite dev server on :5173 proxying to :8000
cd frontend && npm run check     # svelte-check
```

Layout:

```
st_vtt/          FastAPI backend (config, content models, dice, patches, ws, api/)
frontend/        Svelte 5 + Vite SPA, built into frontend/dist
content/         schema.json, SCHEMA.md, example/ pack
tests/           pytest suite
```

The backend is small and document-oriented: characters and shared sheets are
JSON documents in SQLite. Clients send JSON-Pointer patches over one WebSocket;
the server checks permissions, applies, persists, and broadcasts. Scalar fields
are last-write-wins; text fields send diff-match-patch patches that the server
merges; list membership uses idempotent `list_add` / `list_remove` ops.
Focus, blur, and typing events are broadcast but never stored.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
