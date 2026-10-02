"""Who may do what, and what a request for something that isn't there gets.

Each row calls the service directly: the routes and the socket both turn a ServiceError into
its status, and the tests over HTTP and the socket already check that part.
"""

import copy
import re
from types import SimpleNamespace

import pytest
from test_api import app  # noqa: F401

from st_vtt import service
from st_vtt.config import UserConfig

GM = UserConfig(name="Gm", role="gm")
ALICE = UserConfig(name="Alice")
BOB = UserConfig(name="Bob")


@pytest.fixture
def world(app):  # noqa: F811
    """Alice's character and record, the village, a GM screen, a hidden record and a chat line."""
    db = app.state.db
    char, _ = service.create_character(app, ALICE, "wanderer", "Wren", None)
    screen, _ = service.create_shared(app, GM, "gm_screen", None)
    note, _ = service.create_record(app, ALICE, "npc", "Urgben")
    spy, _ = service.create_record(app, GM, "npc", "Spy")
    service.patch_entity(app, GM, "record", spy["id"], "/visibility", "gm")

    def roll(*actions, **payload):
        """A roll card offering `actions`, tied to whatever sheet `payload` names."""
        return db.add_message("Alice", "roll", {"actions": list(actions), **payload})["id"]

    return SimpleNamespace(
        cid=char["id"],
        doc=char["data"],
        sid=next(r["id"] for r in db.list_shared() if r["template"] == "village"),
        gm_sid=screen["id"],
        rid=note["id"],
        hidden_rid=spy["id"],
        chat_id=db.add_message("Alice", "chat", {"text": "hi"})["id"],
        roll=roll,
        request=lambda **extra: db.add_message(
            "Gm", "request", {"to": "Alice", "label": "Brawl", "stat": None, **extra}
        )["id"],
    )


def _check(app, world, caller, call, expected):  # noqa: F811
    if expected is None:
        call(app, caller, world)
        return
    status, message = expected
    with pytest.raises(service.ServiceError, match=re.escape(message)) as ei:
        call(app, caller, world)
    assert ei.value.status == status


GM_ONLY = (403, "GM only")

# (caller, call, None if allowed else (status, message))
_WHO_MAY = {
    "a player creates their own character": (
        BOB,
        lambda a, u, w: service.create_character(a, u, "wanderer", "", "Bob"),
        None,
    ),
    "a player creates one for someone else": (
        BOB,
        lambda a, u, w: service.create_character(a, u, "wanderer", "", "Alice"),
        (403, "only the GM can assign owners"),
    ),
    "the GM creates one for someone else": (
        GM,
        lambda a, u, w: service.create_character(a, u, "wanderer", "", "Alice"),
        None,
    ),
    "a player imports one for someone else": (
        BOB,
        lambda a, u, w: service.import_character(a, u, copy.deepcopy(w.doc), "Alice"),
        (403, "only the GM can assign owners"),
    ),
    "the GM imports one for someone else": (
        GM,
        lambda a, u, w: service.import_character(a, u, copy.deepcopy(w.doc), "Alice"),
        None,
    ),
    "the owner deletes a character": (ALICE, lambda a, u, w: service.delete_character(a, u, w.cid), None),
    "the GM deletes a character": (GM, lambda a, u, w: service.delete_character(a, u, w.cid), None),
    "someone else deletes a character": (
        BOB,
        lambda a, u, w: service.delete_character(a, u, w.cid),
        (403, "only the owner or GM can delete"),
    ),
    "someone else edits a character": (
        BOB,
        lambda a, u, w: service.patch_entity(a, u, "character", w.cid, "/name", "Mud"),
        (403, "you do not own this character"),
    ),
    "the GM sets an owner": (GM, lambda a, u, w: service.set_owner(a, u, w.cid, "Bob"), None),
    "a player sets an owner": (ALICE, lambda a, u, w: service.set_owner(a, u, w.cid, "Alice"), GM_ONLY),
    "the author deletes a record": (ALICE, lambda a, u, w: service.delete_record(a, u, w.rid), None),
    "the GM deletes a record": (GM, lambda a, u, w: service.delete_record(a, u, w.rid), None),
    "someone else deletes a record": (
        BOB,
        lambda a, u, w: service.delete_record(a, u, w.rid),
        (403, "only the GM, or whoever wrote it down, can delete this"),
    ),
    "the GM adds a shared sheet": (GM, lambda a, u, w: service.create_shared(a, u, "village", "Elsewhere"), None),
    "a player adds a shared sheet": (
        ALICE,
        lambda a, u, w: service.create_shared(a, u, "village", "Elsewhere"),
        GM_ONLY,
    ),
    "the GM deletes a shared sheet": (GM, lambda a, u, w: service.delete_shared(a, u, w.sid), None),
    "a player deletes a shared sheet": (ALICE, lambda a, u, w: service.delete_shared(a, u, w.sid), GM_ONLY),
    "the GM imports a shared sheet": (GM, lambda a, u, w: service.import_shared(a, u, w.sid, {}), None),
    "a player imports a shared sheet": (ALICE, lambda a, u, w: service.import_shared(a, u, w.sid, {}), GM_ONLY),
    "a player edits the GM's sheet": (
        ALICE,
        lambda a, u, w: service.patch_entity(a, u, "shared", w.gm_sid, "/notes", "x"),
        GM_ONLY,
    ),
    "the GM requests a roll": (GM, lambda a, u, w: service.request_roll(a, u, "Alice", "Brawl", "str"), None),
    "a player requests a roll": (ALICE, lambda a, u, w: service.request_roll(a, u, "Bob", "Brawl", "str"), GM_ONLY),
    "the GM clears the chat": (GM, lambda a, u, w: service.clear_chat(a, u), None),
    "a player clears the chat": (ALICE, lambda a, u, w: service.clear_chat(a, u), GM_ONLY),
}


@pytest.mark.parametrize(("caller", "call", "expected"), _WHO_MAY.values(), ids=_WHO_MAY.keys())
def test_who_may_do_what(app, world, caller, call, expected):  # noqa: F811
    _check(app, world, caller, call, expected)


# Asked by someone allowed to, so what refuses it is the request itself.
_BAD_REQUESTS = {
    # characters
    "unknown playbook": (
        GM,
        lambda a, u, w: service.create_character(a, u, "nope", "", None),
        (400, "unknown playbook 'nope'"),
    ),
    "create for an unknown user": (
        GM,
        lambda a, u, w: service.create_character(a, u, "wanderer", "", "Nobody"),
        (400, "unknown user 'Nobody'"),
    ),
    "import something that isn't a sheet": (
        GM,
        lambda a, u, w: service.import_character(a, u, [], None),
        (400, "character must be a JSON object"),
    ),
    "import for an unknown user": (
        GM,
        lambda a, u, w: service.import_character(a, u, copy.deepcopy(w.doc), "Nobody"),
        (400, "unknown user 'Nobody'"),
    ),
    "delete a missing character": (
        GM,
        lambda a, u, w: service.delete_character(a, u, "nope"),
        (404, "no such character"),
    ),
    "own a missing character": (
        GM,
        lambda a, u, w: service.set_owner(a, u, "nope", "Alice"),
        (404, "no such character"),
    ),
    "give a character to an unknown user": (
        GM,
        lambda a, u, w: service.set_owner(a, u, w.cid, "Nobody"),
        (400, "unknown user 'Nobody'"),
    ),
    # records and shared sheets
    "delete a missing record": (GM, lambda a, u, w: service.delete_record(a, u, "nope"), (404, "no such record")),
    "delete a record a player can't see": (
        ALICE,
        lambda a, u, w: service.delete_record(a, u, w.hidden_rid),
        (404, "no such record"),
    ),
    "unknown shared sheet template": (
        GM,
        lambda a, u, w: service.create_shared(a, u, "nope", None),
        (400, "unknown shared sheet template 'nope'"),
    ),
    "delete a missing shared sheet": (
        GM,
        lambda a, u, w: service.delete_shared(a, u, "nope"),
        (404, "no such shared sheet"),
    ),
    "import over a missing shared sheet": (
        GM,
        lambda a, u, w: service.import_shared(a, u, "nope", {}),
        (404, "no such shared sheet"),
    ),
    "import a shared sheet that isn't an object": (
        GM,
        lambda a, u, w: service.import_shared(a, u, w.sid, []),
        (400, "shared sheet must be a JSON object"),
    ),
    # patches
    "patch a character with no id": (
        GM,
        lambda a, u, w: service.patch_entity(a, u, "character", None, "/name", "x"),
        (400, "missing character id"),
    ),
    "patch a missing character": (
        GM,
        lambda a, u, w: service.patch_entity(a, u, "character", "nope", "/name", "x"),
        (404, "no such character"),
    ),
    "patch a shared sheet with no id": (
        GM,
        lambda a, u, w: service.patch_entity(a, u, "shared", None, "/name", "x"),
        (400, "missing shared sheet id"),
    ),
    "patch a missing shared sheet": (
        GM,
        lambda a, u, w: service.patch_entity(a, u, "shared", "nope", "/name", "x"),
        (404, "no such shared sheet"),
    ),
    "patch a record with no id": (
        GM,
        lambda a, u, w: service.patch_entity(a, u, "record", None, "/name", "x"),
        (400, "missing record id"),
    ),
    "patch a missing record": (
        GM,
        lambda a, u, w: service.patch_entity(a, u, "record", "nope", "/name", "x"),
        (404, "no such record"),
    ),
    "patch an unknown kind of thing": (
        GM,
        lambda a, u, w: service.patch_entity(a, u, "map", "x", "/name", "x"),
        (400, "unknown entity 'map'"),
    ),
    # numbers the dice add up have to stay whole numbers
    "a stat that isn't a number": (
        ALICE,
        lambda a, u, w: service.patch_entity(a, u, "character", w.cid, "/stats/str", "abc"),
        (400, "/stats/str must be a whole number"),
    ),
    "a stat that's a fraction": (
        ALICE,
        lambda a, u, w: service.patch_entity(a, u, "character", w.cid, "/stats/str", 1.5),
        (400, "/stats/str must be a whole number"),
    ),
    "a stat that's true": (
        ALICE,
        lambda a, u, w: service.patch_entity(a, u, "character", w.cid, "/stats/str", True),
        (400, "/stats/str must be a whole number"),
    ),
    "stats set whole, one not a number": (
        ALICE,
        lambda a, u, w: service.patch_entity(a, u, "character", w.cid, "/stats", {**w.doc["stats"], "dex": "2"}),
        (400, "/stats/dex must be a whole number"),
    ),
    "hp that isn't an object": (
        ALICE,
        lambda a, u, w: service.patch_entity(a, u, "character", w.cid, "/hp", "full"),
        (400, "/hp must be an object"),
    ),
    **{
        f"{path} that isn't a number": (
            ALICE,
            lambda a, u, w, path=path: service.patch_entity(a, u, "character", w.cid, path, "x"),
            (400, f"{path} must be a whole number"),
        )
        for path in ("/hp/current", "/hp/max", "/xp", "/level", "/armor", "/moves/hold/readiness")
    },
    "a shared sheet's stat that isn't a number": (
        GM,
        lambda a, u, w: service.patch_entity(a, u, "shared", w.sid, "/stats/luck", "abc"),
        (400, "/stats/luck must be a whole number"),
    ),
    "a shared sheet's hold that isn't a number": (
        GM,
        lambda a, u, w: service.patch_entity(a, u, "shared", w.sid, "/moves/hold/x", None),
        (400, "/moves/hold/x must be a whole number"),
    ),
    # chat
    "an empty message": (ALICE, lambda a, u, w: service.post_chat(a, u, "   "), (400, "empty message")),
    "a whisper with no message": (
        ALICE,
        lambda a, u, w: service.post_chat(a, u, "/w Bob"),
        (400, "usage: /w <name> <message>"),
    ),
    "a whisper to nobody": (
        ALICE,
        lambda a, u, w: service.post_chat(a, u, "/w Nobody hi"),
        (400, "unknown user 'Nobody'"),
    ),
    "a whisper to a list naming nobody": (
        ALICE,
        lambda a, u, w: service.post_chat(a, u, "hi", ["Bob", "Nobody"]),
        (400, "unknown user 'Nobody'"),
    ),
    "an unknown command": (ALICE, lambda a, u, w: service.post_chat(a, u, "/dance"), (400, "unknown command /dance")),
    # rolls
    "roll against two sheets": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "shared_id": w.sid}),
        (400, "not both"),
    ),
    "roll for a missing character": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"character_id": "nope"}),
        (404, "no such character"),
    ),
    "roll on a missing shared sheet": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"shared_id": "nope"}),
        (404, "no such shared sheet"),
    ),
    "roll on a sheet a player can't see": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"shared_id": w.gm_sid}),
        (404, "no such shared sheet"),
    ),
    "bad dice": (ALICE, lambda a, u, w: service.do_roll(a, u, {"expr": "2dx"}), (400, "bad dice expression")),
    "an unknown stat": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "stat": "luck"}),
        (400, "unknown stat 'luck'"),
    ),
    "a move rolling a stat the sheet lacks": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"shared_id": w.sid, "move_id": "brawl"}),
        (400, "move 'brawl' rolls +str, which this sheet does not have"),
    ),
    "a bonus that isn't a number": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "stat": "str", "bonus": "lots"}),
        (400, "bonus must be a whole number"),
    ),
    "modifiers that aren't an object": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "move_id": "brawl", "modifiers": [1]}),
        (400, "modifiers must be an object of {id: value}"),
    ),
    "the GM requests a roll from nobody": (
        GM,
        lambda a, u, w: service.request_roll(a, u, "Nobody", "Brawl", None),
        (400, "unknown user 'Nobody'"),
    ),
    "the GM requests an unknown stat": (
        GM,
        lambda a, u, w: service.request_roll(a, u, "Alice", "Brawl", "luck"),
        (400, "unknown stat 'luck'"),
    ),
    "the GM requests a roll without saying what for": (
        GM,
        lambda a, u, w: service.request_roll(a, u, "Alice", "", "str"),
        (400, "say what the roll is for"),
    ),
    "the GM requests a roll for nothing but spaces": (
        GM,
        lambda a, u, w: service.request_roll(a, u, "Alice", "   ", None),
        (400, "say what the roll is for"),
    ),
    "the GM requests an unknown move": (
        GM,
        lambda a, u, w: service.request_roll(a, u, "Alice", "Punch", None, "punch"),
        (400, "unknown move 'punch'"),
    ),
    "the GM requests a move with nothing to roll": (
        GM,
        lambda a, u, w: service.request_roll(a, u, "Alice", "Wrap Up", None, "wrap_up"),
        (400, "move 'wrap_up' has nothing to roll"),
    ),
    # answering a roll request
    "answer a missing request": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "stat": "str", "request_id": 9999}),
        (404, "no such request"),
    ),
    "answer a chat line as a request": (
        ALICE,
        lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "stat": "str", "request_id": w.chat_id}),
        (404, "no such request"),
    ),
    "answer someone else's request": (
        BOB,
        lambda a, u, w: service.do_roll(a, u, {"expr": "2d6", "request_id": w.request()}),
        (403, "that request is for Alice"),
    ),
    "answer a request twice": (
        ALICE,
        lambda a, u, w: service.do_roll(
            a, u, {"character_id": w.cid, "stat": "str", "request_id": w.request(answered={"by": "Alice", "roll": 1})}
        ),
        (400, "already answered by Alice"),
    ),
    # applying a roll card's outcome
    "apply a missing roll": (ALICE, lambda a, u, w: service.apply_outcome(a, u, 9999, 0), (404, "no such roll")),
    "apply a chat line": (ALICE, lambda a, u, w: service.apply_outcome(a, u, w.chat_id, 0), (404, "no such roll")),
    "apply an outcome the card lacks": (
        ALICE,
        lambda a, u, w: service.apply_outcome(a, u, w.roll(character_id=w.cid), 0),
        (400, "no such outcome"),
    ),
    "apply a roll tied to no sheet": (
        ALICE,
        lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "xp"}), 0),
        (400, "this roll is not tied to a sheet"),
    ),
    "apply a roll whose sheet is gone": (
        ALICE,
        lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "xp"}, character_id="nope"), 0),
        (404, "that sheet is gone"),
    ),
    "hp that isn't dice": (
        ALICE,
        lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "hp", "amount": "lots"}, character_id=w.cid), 0),
        (400, "bad hp amount"),
    ),
    "a debility nobody picked": (
        ALICE,
        lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "debility"}, character_id=w.cid), 0),
        (400, "pick a debility to mark (battered, drained, rattled)"),
    ),
    "a stat the sheet lacks": (
        ALICE,
        lambda a, u, w: service.apply_outcome(
            a, u, w.roll({"kind": "stat", "id": "luck", "delta": 1}, character_id=w.cid), 0
        ),
        (400, "unknown stat 'luck' on this sheet"),
    ),
    "an unknown action": (
        ALICE,
        lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "dance"}, character_id=w.cid), 0),
        (400, "unknown outcome action 'dance'"),
    ),
}


@pytest.mark.parametrize(("caller", "call", "expected"), _BAD_REQUESTS.values(), ids=_BAD_REQUESTS.keys())
def test_a_bad_request_is_refused(app, world, caller, call, expected):  # noqa: F811
    _check(app, world, caller, call, expected)


def test_a_request_for_a_move_is_answered_once(app, world):  # noqa: F811
    """The request names the move, and the roll that answers it marks it answered, like an applied outcome."""
    db = app.state.db
    service.request_roll(app, GM, "Alice", "Brawl", None, "brawl")
    request = db.list_messages(limit=1)[-1]
    assert request["payload"]["move_id"] == "brawl"

    renders = service.do_roll(app, ALICE, {"character_id": world.cid, "move_id": "brawl", "request_id": request["id"]})
    roll = db.list_messages(limit=1)[-1]
    assert roll["kind"] == "roll" and roll["payload"]["move_id"] == "brawl"
    assert db.get_message(request["id"])["payload"]["answered"] == {"by": "Alice", "roll": roll["id"]}
    events = [r(GM) for r in renders]
    assert {"type": "message_updated", "message": db.get_message(request["id"])} in events

    # Refused before any dice are thrown: a second answer leaves no stray roll in the chat.
    with pytest.raises(service.ServiceError, match="already answered by Alice"):
        service.do_roll(app, ALICE, {"character_id": world.cid, "move_id": "brawl", "request_id": request["id"]})
    assert db.list_messages(limit=1)[-1]["id"] == roll["id"]


def test_a_generic_request_names_no_move(app, world):  # noqa: F811
    service.request_roll(app, GM, "Alice", "climbing the wall", "dex")
    assert app.state.db.list_messages(limit=1)[-1]["payload"]["move_id"] is None


def test_a_roll_you_cannot_see_is_not_there(app, world):  # noqa: F811
    """A GM-only roll is hidden from players: they can't apply its outcomes, and the refusal
    must not confirm it exists, not even by saying who already applied one."""
    secret = app.state.db.add_message("Gm", "roll", {"actions": [{"kind": "xp"}], "character_id": world.cid}, ["Gm"])[
        "id"
    ]

    def refused():
        with pytest.raises(service.ServiceError) as ei:
            service.apply_outcome(app, ALICE, secret, 0)
        return ei.value.status, str(ei.value)

    assert refused() == (404, "no such roll")
    service.apply_outcome(app, GM, secret, 0)
    assert refused() == (404, "no such roll")  # not "already applied by Gm"
    assert app.state.db.get_character(world.cid)["data"]["xp"] == world.doc["xp"] + 1


def test_a_refused_number_leaves_the_sheet_as_it_was(app, world):  # noqa: F811
    before = app.state.db.get_character(world.cid)
    with pytest.raises(service.ServiceError):
        service.patch_entity(app, ALICE, "character", world.cid, "/stats/str", "abc")
    after = app.state.db.get_character(world.cid)
    assert (after["data"], after["revision"]) == (before["data"], before["revision"])
    # and whole numbers still go in, negative ones included
    service.patch_entity(app, ALICE, "character", world.cid, "/stats/str", -1)
    assert app.state.db.get_character(world.cid)["data"]["stats"]["str"] == -1


def test_a_sheet_saved_with_a_bad_number_can_still_be_edited_and_mended(app, world):  # noqa: F811
    """Sheets saved before numbers were checked may hold anything. Only what a patch breaks is refused."""
    db = app.state.db
    db.save_character(world.cid, {**world.doc, "stats": {**world.doc["stats"], "str": "abc"}}, None)
    service.patch_entity(app, ALICE, "character", world.cid, "/name", "Wren the Bold")
    service.patch_entity(app, ALICE, "character", world.cid, "/stats/str", 1)
    assert db.get_character(world.cid)["data"]["stats"]["str"] == 1


def test_a_shared_sheet_imported_with_a_bad_number_gets_the_templates(app, world):  # noqa: F811
    service.import_shared(app, GM, world.sid, {"stats": {"luck": "abc", "stores": 4}})
    assert app.state.db.get_shared(world.sid)["data"]["stats"] == {
        "luck": 1,
        "stores": 4,
        "wealth": 0,
        "folk": 0,
        "walls": 0,
    }


def _spoil(app, world, entity, path, value):
    """Save a bad value straight to the database, as a sheet from before numbers were checked may hold."""
    db = app.state.db
    row = db.get_character(world.cid) if entity == "character" else db.get_shared(world.sid)
    node = row["data"]
    *parents, last = path.strip("/").split("/")
    for key in parents:
        node = node.setdefault(key, {})
    node[last] = value
    (db.save_character if entity == "character" else db.save_shared)(row["id"], row["data"], None)


# (what to spoil, then what to do with the spoiled sheet)
_SPOILED = {
    "roll a move's stat": (
        ("character", "/stats/str", "abc"),
        lambda a, w: service.do_roll(a, ALICE, {"character_id": w.cid, "stat": "str"}),
    ),
    "roll dice naming a stat": (
        ("character", "/stats/str", "abc"),
        lambda a, w: service.do_roll(a, ALICE, {"character_id": w.cid, "expr": "1d6+{str}"}),
    ),
    "roll with stats that aren't an object": (
        ("character", "/stats", "none"),
        lambda a, w: service.do_roll(a, ALICE, {"character_id": w.cid, "stat": "str"}),
    ),
    "roll a shared sheet's stat": (
        ("shared", "/stats/luck", "abc"),
        lambda a, w: service.do_roll(a, GM, {"shared_id": w.sid, "stat": "luck"}),
    ),
    "mark xp": (
        ("character", "/xp", "lots"),
        lambda a, w: service.apply_outcome(a, ALICE, w.roll({"kind": "xp"}, character_id=w.cid), 0),
    ),
    "heal hp that isn't an object": (
        ("character", "/hp", "full"),
        lambda a, w: service.apply_outcome(a, ALICE, w.roll({"kind": "hp", "amount": "1"}, character_id=w.cid), 0),
    ),
    "add hold": (
        ("character", "/moves/hold/Guard", "x"),
        lambda a, w: service.apply_outcome(a, ALICE, w.roll({"kind": "hold", "name": "Guard"}, character_id=w.cid), 0),
    ),
    "change a shared sheet's stat": (
        ("shared", "/stats/luck", "abc"),
        lambda a, w: service.apply_outcome(
            a, GM, w.roll({"kind": "stat", "id": "luck", "delta": 1}, shared_id=w.sid), 0
        ),
    ),
}


@pytest.mark.parametrize(("spoil", "call"), _SPOILED.values(), ids=_SPOILED.keys())
def test_a_sheet_saved_with_a_bad_number_is_reported_not_crashed_on(app, world, spoil, call):  # noqa: F811
    _spoil(app, world, *spoil)
    with pytest.raises(service.ServiceError, match="not a whole number|must be an object") as ei:
        call(app, world)
    assert ei.value.status == 400
