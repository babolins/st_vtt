"""Records: who may write one, and what never reaches a player.

The visibility rules here are the load-bearing part — a leak is invisible on
screen, because the client that must not know is the one nobody is looking at.
Two of these tests exist because the first implementation failed them: a
`/secret` patch went out over the socket to everyone, and hiding a record left
the copy players already held in place.
"""

import pytest
from fastapi.testclient import TestClient

from st_vtt.config import UserConfig
from st_vtt.perms import Forbidden, check_patch, strip_for_user
from test_api import app, alice, bob, client_for, gm  # noqa: F401


def make(client: TestClient, name: str, kind: str = "npc") -> str:
    r = client.post("/api/records", json={"kind": kind, "name": name})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def patch(client: TestClient, rid: str, path: str, value, op: str = "set"):
    return client.post(f"/api/records/{rid}/patch", json={"path": path, "value": value, "op": op})


# ------------------------------------------------------------------ anyone writes


def test_a_player_may_write_someone_down(alice):
    rid = make(alice, "Cerys")
    assert patch(alice, rid, "/role", "Sheriff").status_code == 200
    assert alice.get(f"/api/records/{rid}").json()["data"]["role"] == "Sheriff"


def test_a_record_needs_a_name(alice):
    assert alice.post("/api/records", json={"kind": "npc", "name": "  "}).status_code == 400
    assert alice.post("/api/records", json={"kind": "dragon", "name": "Smaug"}).status_code == 400


def test_ties_are_a_list_anyone_may_add_to(alice, bob):
    rid = make(alice, "Dilwen")
    tie = {"type": "sidekick-of", "to": "glenys", "note": "best friend"}
    assert patch(bob, rid, "/ties", tie, op="list_add").status_code == 200
    assert alice.get(f"/api/records/{rid}").json()["data"]["ties"] == [tie]


def test_author_or_gm_may_delete(alice, bob, gm):
    mine = make(alice, "Meirion")
    assert bob.delete(f"/api/records/{mine}").status_code == 403
    assert alice.delete(f"/api/records/{mine}").status_code == 200

    theirs = make(bob, "Braith")
    assert gm.delete(f"/api/records/{theirs}").status_code == 200


# ------------------------------------------------------------------ the GM's half


def test_players_cannot_write_the_secret_or_hide_a_record(alice):
    rid = make(alice, "Urgben")
    assert patch(alice, rid, "/secret", "took Brennan's coin").status_code == 403
    assert patch(alice, rid, "/visibility", "gm").status_code == 403


def test_the_secret_never_reaches_a_player(alice, gm):
    rid = make(alice, "Urgben")
    assert patch(gm, rid, "/secret", "took Brennan's coin").status_code == 200

    assert "secret" not in alice.get(f"/api/records/{rid}").json()["data"]
    assert "secret" not in alice.get("/api/state").json()["records"][0]["data"]
    assert gm.get(f"/api/records/{rid}").json()["data"]["secret"] == "took Brennan's coin"


def test_a_hidden_record_does_not_exist_for_players(alice, gm):
    rid = make(gm, "Brennan")
    assert patch(gm, rid, "/visibility", "gm").status_code == 200

    assert alice.get(f"/api/records/{rid}").status_code == 404
    assert patch(alice, rid, "/role", "bandit").status_code == 404
    assert [r["data"]["name"] for r in alice.get("/api/records").json()] == []
    assert [r["data"]["name"] for r in gm.get("/api/records").json()] == ["Brennan"]
    assert alice.get("/api/state").json()["records"] == []


def test_revealing_a_record_gives_it_back(alice, gm):
    rid = make(gm, "Brennan")
    patch(gm, rid, "/visibility", "gm")
    assert alice.get(f"/api/records/{rid}").status_code == 404

    patch(gm, rid, "/visibility", "table")
    assert alice.get(f"/api/records/{rid}").status_code == 200


# ------------------------------------------------------------------ over the wire


def broadcast_to(app, user: UserConfig, renders):
    """What this user's socket would actually be sent."""
    return [msg for msg in (render(user) for render in renders) if msg is not None]


def test_a_secret_patch_is_not_broadcast_to_the_table(app, alice, gm):
    from st_vtt import service

    rid = make(alice, "Urgben")
    player = UserConfig(name="Alice")

    renders = service.patch_entity(app, UserConfig(name="Gm", role="gm"), "record", rid, "/secret", "the truth")
    assert broadcast_to(app, player, renders) == []
    assert broadcast_to(app, UserConfig(name="Gm", role="gm"), renders)[0]["value"] == "the truth"

    renders = service.patch_entity(app, player, "record", rid, "/role", "farmer")
    assert broadcast_to(app, player, renders)[0]["path"] == "/role"


def test_hiding_withdraws_the_record_from_players(app, alice, gm):
    from st_vtt import service

    rid = make(alice, "Brennan")
    player = UserConfig(name="Alice")
    master = UserConfig(name="Gm", role="gm")

    renders = service.patch_entity(app, master, "record", rid, "/visibility", "gm")
    assert broadcast_to(app, player, renders) == [{"type": "record_deleted", "id": rid}]

    renders = service.patch_entity(app, master, "record", rid, "/role", "bandit")
    assert broadcast_to(app, player, renders) == []

    renders = service.patch_entity(app, master, "record", rid, "/visibility", "table")
    back = broadcast_to(app, player, renders)
    assert back[0]["type"] == "record_created"
    assert back[0]["record"]["data"]["name"] == "Brennan"
    assert "secret" not in back[0]["record"]["data"]


# ------------------------------------------------------------------ the rules themselves


def test_check_patch_knows_records():
    player = UserConfig(name="Alice")
    master = UserConfig(name="Gm", role="gm")

    check_patch(player, "record", None, "/role")
    with pytest.raises(Forbidden):
        check_patch(player, "record", None, "/secret")
    with pytest.raises(Forbidden):
        check_patch(player, "record", None, "/visibility")
    with pytest.raises(Forbidden):
        check_patch(player, "record", None, "/notes", gm_only=True)
    check_patch(master, "record", None, "/secret")


def test_strip_for_user_drops_the_secret():
    doc = {"name": "Urgben", "secret": "took the coin", "gm_notes": "x"}
    assert strip_for_user(UserConfig(name="Alice"), doc) == {"name": "Urgben"}
    assert strip_for_user(UserConfig(name="Gm", role="gm"), doc) == doc


# ------------------------------------------------------------------ events


def test_events_are_records_with_a_when_and_an_order(alice):
    rid = make(alice, "The Forest Folk disappeared", kind="event")
    doc = alice.get(f"/api/records/{rid}").json()["data"]
    assert doc["when"] == "" and doc["order"] == 0 and doc["involves"] == []

    assert patch(alice, rid, "/when", "ten years ago").status_code == 200
    assert patch(alice, rid, "/order", 20).status_code == 200
    assert patch(alice, rid, "/involves", "someone", op="list_add").status_code == 200

    doc = alice.get(f"/api/records/{rid}").json()["data"]
    assert (doc["when"], doc["order"], doc["involves"]) == ("ten years ago", 20, ["someone"])


def test_a_person_has_no_event_fields(alice):
    rid = make(alice, "Cerys")
    assert "when" not in alice.get(f"/api/records/{rid}").json()["data"]


def test_an_event_can_be_the_gms_alone(alice, gm):
    rid = make(alice, "Urgben let Brennan in", kind="event")
    patch(gm, rid, "/visibility", "gm")
    assert alice.get(f"/api/records/{rid}").status_code == 404
    assert [r["data"]["name"] for r in gm.get("/api/records").json()] == ["Urgben let Brennan in"]
