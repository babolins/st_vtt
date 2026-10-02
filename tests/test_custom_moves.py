"""Custom moves: a move written on one character's sheet, rolled and shared like a pack's.

The server reads them with the pack's strict `Move` model, so a field the frontend adds
and the model doesn't know turns every new custom move into "unknown move".
"""

import pytest

from test_api import alice, app, bob, gm  # noqa: F401


def custom_move(stat, **overrides):
    """What `addCustom` in frontend/src/sheet/sections/Moves.svelte writes; keep the two alike."""
    move = {
        "id": "custom_abc",
        "name": "Read the Stars",
        "trigger": "When you read the stars",
        "text": "Ask the GM.",
        "roll": None
        if stat == ""
        else {"stat": None if stat == "nothing" else stat, "bonus": 0, "label": None, "modifiers": []},
        "outcomes": {},
        "hold": None,
        "tracks": {"marks": None, "bulk": None, "uses": None, "statuses": []},
        "requires": None,
        "themes": [],
        "tags": ["custom"],
        "replaces": None,
        "insert": None,
        "grants": None,
        "options": [],
        "min": None,
        "max": None,
    }
    move.update(overrides)
    return move


def character_with(client, move, name="Bryn"):
    cid = client.post("/api/characters", json={"playbook": "wanderer", "name": name}).json()["id"]
    client.post(f"/api/characters/{cid}/patch", json={"path": "/stats/wis", "value": 2})
    assert (
        client.post(f"/api/characters/{cid}/patch", json={"path": "/custom_moves/-", "value": move}).status_code == 200
    )
    assert (
        client.post(
            f"/api/characters/{cid}/patch", json={"path": "/moves/taken", "value": move["id"], "op": "list_add"}
        ).status_code
        == 200
    )
    return cid


def roll(client, **spec):
    r = client.post("/api/roll", json=spec)
    assert r.status_code == 200, r.text
    return client.get("/api/messages").json()[-1]["payload"]


def test_a_custom_move_rolls_with_its_stat(alice):
    cid = character_with(alice, custom_move("wis"))
    p = roll(alice, character_id=cid, move_id="custom_abc")
    assert p["move_id"] == "custom_abc" and p["label"] == "Read the Stars" and p["character"] == "Bryn"
    assert p["stat"] == "wis" and p["stat_mod"] == 2
    assert p["tier"] in ("10+", "7-9", "6-")


def test_a_custom_moves_own_bonus_is_added(alice):
    move = custom_move("wis")
    move["roll"]["bonus"] = 1
    cid = character_with(alice, move)
    p = roll(alice, character_id=cid, move_id="custom_abc")
    assert p["bonus"] == 1 and p["total"] == p["roll"]["total"] + 2 + 1


def test_a_custom_move_that_rolls_plus_nothing(alice):
    cid = character_with(alice, custom_move("nothing"))
    p = roll(alice, character_id=cid, move_id="custom_abc")
    assert p["stat"] is None and p["stat_mod"] == 0


def test_a_custom_move_that_lets_you_choose_the_stat(alice):
    cid = character_with(alice, custom_move("choose"))
    assert roll(alice, character_id=cid, move_id="custom_abc", stat="wis")["stat_mod"] == 2
    # Without a choice it rolls +nothing; the sheet asks for one before it gets here.
    assert roll(alice, character_id=cid, move_id="custom_abc")["stat"] is None


def test_a_custom_move_is_shared_to_chat(alice, bob):
    cid = character_with(alice, custom_move("wis"))
    assert alice.post("/api/share_move", json={"character_id": cid, "move_id": "custom_abc"}).status_code == 200
    m = bob.get("/api/messages").json()[-1]
    assert m["kind"] == "move" and m["author"] == "Alice"
    p = m["payload"]
    assert (p["move_id"], p["name"], p["trigger"], p["text"]) == (
        "custom_abc",
        "Read the Stars",
        "When you read the stars",
        "Ask the GM.",
    )
    assert p["character"] == "Bryn" and p["character_id"] == cid
    assert p["roll"]["stat"] == "wis" and p["outcomes"] == {}


def test_a_custom_move_without_a_roll_can_be_shared_but_not_rolled_as_a_move(alice):
    cid = character_with(alice, custom_move(""))
    assert alice.post("/api/share_move", json={"character_id": cid, "move_id": "custom_abc"}).status_code == 200
    assert alice.get("/api/messages").json()[-1]["payload"]["roll"] is None
    # Rolling it anyway is a plain 2d6, as for a pack move with no roll.
    p = roll(alice, character_id=cid, move_id="custom_abc")
    assert p["move_id"] == "custom_abc" and p["stat"] is None


def test_a_custom_move_belongs_to_its_own_sheet(alice, bob):
    cid = character_with(alice, custom_move("wis"))
    other = bob.post("/api/characters", json={"playbook": "wanderer", "name": "Pedr"}).json()["id"]
    for spec in ({}, {"character_id": other}):
        r = alice.post("/api/roll", json={**spec, "move_id": "custom_abc"})
        assert r.status_code == 400 and r.json()["detail"] == "unknown move 'custom_abc'"
        assert alice.post("/api/share_move", json={**spec, "move_id": "custom_abc"}).status_code == 400
    assert alice.post("/api/share_move", json={"character_id": "nope", "move_id": "custom_abc"}).status_code == 404
    # The move is looked up on the sheet, not on whoever rolls against it.
    assert bob.post("/api/roll", json={"character_id": cid, "move_id": "custom_abc"}).status_code == 200


@pytest.mark.parametrize(
    "bad",
    [
        {"colour": "red"},  # a field the server's Move doesn't have
        {"name": None},  # a required field gone
        {"roll": {"stat": "wis", "bonus": "lots"}},  # a value of the wrong type
    ],
)
def test_a_custom_move_the_server_cannot_read_is_an_unknown_move(alice, bad):
    cid = character_with(alice, custom_move("wis", **bad))
    r = alice.post("/api/roll", json={"character_id": cid, "move_id": "custom_abc"})
    assert r.status_code == 400 and r.json()["detail"] == "unknown move 'custom_abc'"
    assert alice.post("/api/share_move", json={"character_id": cid, "move_id": "custom_abc"}).status_code == 400


@pytest.mark.parametrize(
    "op, value",
    [
        ("remove", None),
        ("set", 5),
        ("set", "custom_abc"),
        ("set", ["custom_abc", {"id": "custom_other", "name": "Other"}]),
    ],
)
def test_a_sheet_without_a_list_of_custom_moves_has_none_of_them(alice, op, value):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    assert (
        alice.post(f"/api/characters/{cid}/patch", json={"path": "/custom_moves", "op": op, "value": value}).status_code
        == 200
    )
    r = alice.post("/api/roll", json={"character_id": cid, "move_id": "custom_abc"})
    assert r.status_code == 400 and r.json()["detail"] == "unknown move 'custom_abc'"
    assert alice.post("/api/share_move", json={"character_id": cid, "move_id": "custom_abc"}).status_code == 400
    # The sheet's pack moves are unaffected.
    assert alice.post("/api/share_move", json={"character_id": cid, "move_id": "brawl"}).status_code == 200
