"""Who may do what, and what a request for something that isn't there gets.

Each row calls the service directly: the routes and the socket both turn a ServiceError into
its status, and the tests over HTTP and the socket already check that part.
"""

import copy
import re
from types import SimpleNamespace

import pytest

from st_vtt import service
from st_vtt.config import UserConfig
from test_api import app  # noqa: F401

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
    "a player creates their own character": (BOB, lambda a, u, w: service.create_character(a, u, "wanderer", "", "Bob"), None),
    "a player creates one for someone else": (BOB, lambda a, u, w: service.create_character(a, u, "wanderer", "", "Alice"), (403, "only the GM can assign owners")),
    "the GM creates one for someone else": (GM, lambda a, u, w: service.create_character(a, u, "wanderer", "", "Alice"), None),
    "a player imports one for someone else": (BOB, lambda a, u, w: service.import_character(a, u, copy.deepcopy(w.doc), "Alice"), (403, "only the GM can assign owners")),
    "the GM imports one for someone else": (GM, lambda a, u, w: service.import_character(a, u, copy.deepcopy(w.doc), "Alice"), None),
    "the owner deletes a character": (ALICE, lambda a, u, w: service.delete_character(a, u, w.cid), None),
    "the GM deletes a character": (GM, lambda a, u, w: service.delete_character(a, u, w.cid), None),
    "someone else deletes a character": (BOB, lambda a, u, w: service.delete_character(a, u, w.cid), (403, "only the owner or GM can delete")),
    "someone else edits a character": (BOB, lambda a, u, w: service.patch_entity(a, u, "character", w.cid, "/name", "Mud"), (403, "you do not own this character")),
    "the GM sets an owner": (GM, lambda a, u, w: service.set_owner(a, u, w.cid, "Bob"), None),
    "a player sets an owner": (ALICE, lambda a, u, w: service.set_owner(a, u, w.cid, "Alice"), GM_ONLY),
    "the author deletes a record": (ALICE, lambda a, u, w: service.delete_record(a, u, w.rid), None),
    "the GM deletes a record": (GM, lambda a, u, w: service.delete_record(a, u, w.rid), None),
    "someone else deletes a record": (BOB, lambda a, u, w: service.delete_record(a, u, w.rid), (403, "only the GM, or whoever wrote it down, can delete this")),
    "the GM adds a shared sheet": (GM, lambda a, u, w: service.create_shared(a, u, "village", "Elsewhere"), None),
    "a player adds a shared sheet": (ALICE, lambda a, u, w: service.create_shared(a, u, "village", "Elsewhere"), GM_ONLY),
    "the GM deletes a shared sheet": (GM, lambda a, u, w: service.delete_shared(a, u, w.sid), None),
    "a player deletes a shared sheet": (ALICE, lambda a, u, w: service.delete_shared(a, u, w.sid), GM_ONLY),
    "the GM imports a shared sheet": (GM, lambda a, u, w: service.import_shared(a, u, w.sid, {}), None),
    "a player imports a shared sheet": (ALICE, lambda a, u, w: service.import_shared(a, u, w.sid, {}), GM_ONLY),
    "a player edits the GM's sheet": (ALICE, lambda a, u, w: service.patch_entity(a, u, "shared", w.gm_sid, "/notes", "x"), GM_ONLY),
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
    "unknown playbook": (GM, lambda a, u, w: service.create_character(a, u, "nope", "", None), (400, "unknown playbook 'nope'")),
    "create for an unknown user": (GM, lambda a, u, w: service.create_character(a, u, "wanderer", "", "Nobody"), (400, "unknown user 'Nobody'")),
    "import something that isn't a sheet": (GM, lambda a, u, w: service.import_character(a, u, [], None), (400, "character must be a JSON object")),
    "import for an unknown user": (GM, lambda a, u, w: service.import_character(a, u, copy.deepcopy(w.doc), "Nobody"), (400, "unknown user 'Nobody'")),
    "delete a missing character": (GM, lambda a, u, w: service.delete_character(a, u, "nope"), (404, "no such character")),
    "own a missing character": (GM, lambda a, u, w: service.set_owner(a, u, "nope", "Alice"), (404, "no such character")),
    "give a character to an unknown user": (GM, lambda a, u, w: service.set_owner(a, u, w.cid, "Nobody"), (400, "unknown user 'Nobody'")),
    # records and shared sheets
    "delete a missing record": (GM, lambda a, u, w: service.delete_record(a, u, "nope"), (404, "no such record")),
    "delete a record a player can't see": (ALICE, lambda a, u, w: service.delete_record(a, u, w.hidden_rid), (404, "no such record")),
    "unknown shared sheet template": (GM, lambda a, u, w: service.create_shared(a, u, "nope", None), (400, "unknown shared sheet template 'nope'")),
    "delete a missing shared sheet": (GM, lambda a, u, w: service.delete_shared(a, u, "nope"), (404, "no such shared sheet")),
    "import over a missing shared sheet": (GM, lambda a, u, w: service.import_shared(a, u, "nope", {}), (404, "no such shared sheet")),
    "import a shared sheet that isn't an object": (GM, lambda a, u, w: service.import_shared(a, u, w.sid, []), (400, "shared sheet must be a JSON object")),
    # patches
    "patch a character with no id": (GM, lambda a, u, w: service.patch_entity(a, u, "character", None, "/name", "x"), (400, "missing character id")),
    "patch a missing character": (GM, lambda a, u, w: service.patch_entity(a, u, "character", "nope", "/name", "x"), (404, "no such character")),
    "patch a shared sheet with no id": (GM, lambda a, u, w: service.patch_entity(a, u, "shared", None, "/name", "x"), (400, "missing shared sheet id")),
    "patch a missing shared sheet": (GM, lambda a, u, w: service.patch_entity(a, u, "shared", "nope", "/name", "x"), (404, "no such shared sheet")),
    "patch a record with no id": (GM, lambda a, u, w: service.patch_entity(a, u, "record", None, "/name", "x"), (400, "missing record id")),
    "patch a missing record": (GM, lambda a, u, w: service.patch_entity(a, u, "record", "nope", "/name", "x"), (404, "no such record")),
    "patch an unknown kind of thing": (GM, lambda a, u, w: service.patch_entity(a, u, "map", "x", "/name", "x"), (400, "unknown entity 'map'")),
    # chat
    "an empty message": (ALICE, lambda a, u, w: service.post_chat(a, u, "   "), (400, "empty message")),
    "a whisper with no message": (ALICE, lambda a, u, w: service.post_chat(a, u, "/w Bob"), (400, "usage: /w <name> <message>")),
    "a whisper to nobody": (ALICE, lambda a, u, w: service.post_chat(a, u, "/w Nobody hi"), (400, "unknown user 'Nobody'")),
    "an unknown command": (ALICE, lambda a, u, w: service.post_chat(a, u, "/dance"), (400, "unknown command /dance")),
    # rolls
    "roll against two sheets": (ALICE, lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "shared_id": w.sid}), (400, "not both")),
    "roll for a missing character": (ALICE, lambda a, u, w: service.do_roll(a, u, {"character_id": "nope"}), (404, "no such character")),
    "roll on a missing shared sheet": (ALICE, lambda a, u, w: service.do_roll(a, u, {"shared_id": "nope"}), (404, "no such shared sheet")),
    "roll on a sheet a player can't see": (ALICE, lambda a, u, w: service.do_roll(a, u, {"shared_id": w.gm_sid}), (404, "no such shared sheet")),
    "bad dice": (ALICE, lambda a, u, w: service.do_roll(a, u, {"expr": "2dx"}), (400, "bad dice expression")),
    "an unknown stat": (ALICE, lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "stat": "luck"}), (400, "unknown stat 'luck'")),
    "a move rolling a stat the sheet lacks": (ALICE, lambda a, u, w: service.do_roll(a, u, {"shared_id": w.sid, "move_id": "brawl"}),
                                              (400, "move 'brawl' rolls +str, which this sheet does not have")),
    "a bonus that isn't a number": (ALICE, lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "stat": "str", "bonus": "lots"}), (400, "bonus must be a whole number")),
    "modifiers that aren't an object": (ALICE, lambda a, u, w: service.do_roll(a, u, {"character_id": w.cid, "move_id": "brawl", "modifiers": [1]}),
                                        (400, "modifiers must be an object of {id: value}")),
    "the GM requests a roll from nobody": (GM, lambda a, u, w: service.request_roll(a, u, "Nobody", "", None), (400, "unknown user 'Nobody'")),
    "the GM requests an unknown stat": (GM, lambda a, u, w: service.request_roll(a, u, "Alice", "", "luck"), (400, "unknown stat 'luck'")),
    # applying a roll card's outcome
    "apply a missing roll": (ALICE, lambda a, u, w: service.apply_outcome(a, u, 9999, 0), (404, "no such roll")),
    "apply a chat line": (ALICE, lambda a, u, w: service.apply_outcome(a, u, w.chat_id, 0), (404, "no such roll")),
    "apply an outcome the card lacks": (ALICE, lambda a, u, w: service.apply_outcome(a, u, w.roll(character_id=w.cid), 0), (400, "no such outcome")),
    "apply a roll tied to no sheet": (ALICE, lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "xp"}), 0), (400, "this roll is not tied to a sheet")),
    "apply a roll whose sheet is gone": (ALICE, lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "xp"}, character_id="nope"), 0), (404, "that sheet is gone")),
    "hp that isn't dice": (ALICE, lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "hp", "amount": "lots"}, character_id=w.cid), 0), (400, "bad hp amount")),
    "a debility nobody picked": (ALICE, lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "debility"}, character_id=w.cid), 0),
                                 (400, "pick a debility to mark (battered, drained, rattled)")),
    "a stat the sheet lacks": (ALICE, lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "stat", "id": "luck", "delta": 1}, character_id=w.cid), 0),
                               (400, "unknown stat 'luck' on this sheet")),
    "an unknown action": (ALICE, lambda a, u, w: service.apply_outcome(a, u, w.roll({"kind": "dance"}, character_id=w.cid), 0), (400, "unknown outcome action 'dance'")),
}


@pytest.mark.parametrize(("caller", "call", "expected"), _BAD_REQUESTS.values(), ids=_BAD_REQUESTS.keys())
def test_a_bad_request_is_refused(app, world, caller, call, expected):  # noqa: F811
    _check(app, world, caller, call, expected)


def test_a_roll_you_cannot_see_is_not_there(app, world):  # noqa: F811
    """A GM-only roll is hidden from players: they can't apply its outcomes, and the refusal
    must not confirm it exists, not even by saying who already applied one."""
    secret = app.state.db.add_message("Gm", "roll", {"actions": [{"kind": "xp"}], "character_id": world.cid}, ["Gm"])["id"]
    def refused():
        with pytest.raises(service.ServiceError) as ei:
            service.apply_outcome(app, ALICE, secret, 0)
        return ei.value.status, str(ei.value)

    assert refused() == (404, "no such roll")
    service.apply_outcome(app, GM, secret, 0)
    assert refused() == (404, "no such roll")  # not "already applied by Gm"
    assert app.state.db.get_character(world.cid)["data"]["xp"] == world.doc["xp"] + 1
