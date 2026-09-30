import json

import anyio
import pytest
from fastapi.testclient import TestClient

from conftest import ROOT
from st_vtt.main import create_app


@pytest.fixture
def app(config):
    # One event loop for every client. Starlette's TestClient otherwise gives each
    # WebSocket its own loop/thread, and cross-loop broadcasts can miss wakeups;
    # a real uvicorn server runs a single loop, which this mirrors.
    with anyio.from_thread.start_blocking_portal("asyncio") as portal:
        a = create_app(config)
        a.state.test_portal = portal
        yield a
        a.state.db.close()


def raw_client(app):
    c = TestClient(app)
    c.portal = getattr(app.state, "test_portal", None)
    return c


def client_for(app, name, password=None):
    c = raw_client(app)
    r = c.post("/api/login", json={"name": name, "password": password})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def gm(app):
    return client_for(app, "Gm")


@pytest.fixture
def alice(app):
    return client_for(app, "Alice")


@pytest.fixture
def bob(app):
    return client_for(app, "Bob", "pw")


def test_login_rules(app):
    c = raw_client(app)
    assert c.post("/api/login", json={"name": "Nobody"}).status_code == 401
    assert c.post("/api/login", json={"name": "Bob"}).status_code == 401
    assert c.post("/api/login", json={"name": "Bob", "password": "wrong"}).status_code == 401
    assert c.get("/api/me").json() is None
    users = c.get("/api/users").json()
    assert {u["name"]: u["has_password"] for u in users} == {"Gm": False, "Alice": False, "Bob": True}


def test_state_and_content(alice):
    st = alice.get("/api/state").json()
    assert st["me"] == {"name": "Alice", "role": "player"}
    assert [x["template"] for x in st["shared"]] == ["village"]
    assert st["shared"][0]["data"]["stats"]["luck"] == 1
    assert "gm_notes" not in st["shared"][0]["data"]
    content = alice.get("/api/content").json()
    assert content["pack"]["id"] == "example"
    assert content["playbooks"][0]["starting_moves"]["choose"][0]["from"] == ["watchful", "iron_gut"]


def test_character_lifecycle_and_perms(gm, alice, bob):
    r = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert r.json()["owner"] == "Alice"
    # the playbook's starting move, plus the fixed move from the insert it carries
    assert r.json()["data"]["moves"]["taken"] == ["well_traveled", "stubborn"]
    assert r.json()["data"]["inserts"] == ["gear", "followers", "arcana", "pack_mule"]
    assert r.json()["data"]["hp"] == {"current": 18, "max": 18}

    # players cannot assign owners; gm can
    assert alice.post("/api/characters", json={"playbook": "wanderer", "owner": "Bob"}).status_code == 403
    assert gm.post(f"/api/characters/{cid}/owner", json={"owner": "Bob"}).status_code == 200
    assert alice.post(f"/api/characters/{cid}/owner", json={"owner": "Alice"}).status_code == 403
    assert gm.post(f"/api/characters/{cid}/owner", json={"owner": "Alice"}).status_code == 200

    # patch perms
    assert alice.post(f"/api/characters/{cid}/patch", json={"path": "/hp/current", "value": 10}).status_code == 200
    assert bob.post(f"/api/characters/{cid}/patch", json={"path": "/hp/current", "value": 1}).status_code == 403
    assert alice.post(f"/api/characters/{cid}/patch", json={"path": "/gm_notes", "value": "x"}).status_code == 403
    assert gm.post(f"/api/characters/{cid}/patch", json={"path": "/gm_notes", "value": "secret"}).status_code == 200
    assert alice.post(f"/api/characters/{cid}/patch", json={"path": "/playbook", "value": "x"}).status_code == 403
    assert alice.post(f"/api/characters/{cid}/patch", json={"path": "/followers/-", "value": {"name": "Dog"}}).status_code == 200

    row = alice.get(f"/api/characters/{cid}").json()
    assert row["data"]["hp"]["current"] == 10
    assert row["data"]["followers"][0]["name"] == "Dog"
    assert "gm_notes" not in row["data"]
    assert gm.get(f"/api/characters/{cid}").json()["data"]["gm_notes"] == "secret"
    assert row["revision"] == 3  # hp, gm_notes, followers

    # export -> delete -> import round trip
    exported = alice.get(f"/api/characters/{cid}/export").json()
    assert "gm_notes" not in exported
    assert bob.delete(f"/api/characters/{cid}").status_code == 403
    assert alice.delete(f"/api/characters/{cid}").status_code == 200
    exported["moves"]["taken"].append("made_up_move")
    r = alice.post("/api/characters/import", json={"character": exported})
    assert r.status_code == 200
    assert r.json()["character"]["data"]["name"] == "Bryn"
    assert any("made_up_move" in w for w in r.json()["warnings"])


def sheet_id(c, template="village"):
    return next(x["id"] for x in c.get("/api/shared").json() if x["template"] == template)


def test_shared_patch_by_anyone(alice, bob, gm):
    sid = sheet_id(alice)
    assert alice.post(f"/api/shared/{sid}/patch", json={"path": "/stats/stores", "value": 3}).status_code == 200
    assert bob.post(f"/api/shared/{sid}/patch", json={"path": "/sections/residents/-", "value": {"name": "Old Mab"}}).status_code == 200
    assert bob.post(f"/api/shared/{sid}/patch", json={"path": "/gm_notes", "value": "no"}).status_code == 403
    st = gm.get(f"/api/shared/{sid}").json()
    assert st["data"]["stats"]["stores"] == 3
    assert st["data"]["sections"]["residents"][0]["name"] == "Old Mab"
    exported = alice.get(f"/api/shared/{sid}/export").json()
    assert alice.post(f"/api/shared/{sid}/import", json=exported).status_code == 403
    assert gm.post(f"/api/shared/{sid}/import", json=exported).status_code == 200
    assert gm.get(f"/api/shared/{sid}").json()["data"]["stats"]["stores"] == 3


def test_gm_only_shared_sheet(app, gm, alice, bob):
    assert alice.post("/api/shared", json={"template": "gm_screen"}).status_code == 403
    r = gm.post("/api/shared", json={"template": "gm_screen", "name": "Behind the screen"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert [x["template"] for x in gm.get("/api/shared").json()] == ["village", "gm_screen"]
    assert [x["template"] for x in alice.get("/api/shared").json()] == ["village"]
    assert alice.get(f"/api/shared/{sid}").status_code == 404
    assert alice.post(f"/api/shared/{sid}/patch", json={"path": "/notes", "value": "x"}).status_code == 403
    assert gm.post(f"/api/shared/{sid}/patch", json={"path": "/sections/npcs/-", "value": {"name": "Bandit", "damage": "1d6"}}).status_code == 200
    # ws: the gm-only patch reaches the gm but not alice
    with alice.websocket_connect("/ws") as wa, gm.websocket_connect("/ws") as wg:
        json.loads(wa.receive_text()); json.loads(wa.receive_text()); json.loads(wg.receive_text())
        wg.send_text(json.dumps({"type": "patch", "entity": "shared", "id": sid, "path": "/notes", "value": "secret"}))
        assert json.loads(wg.receive_text())["type"] == "patch"
        wg.send_text(json.dumps({"type": "chat", "text": "hi"}))
        assert json.loads(wa.receive_text())["type"] == "message"
    assert alice.delete(f"/api/shared/{sid}").status_code == 403
    assert gm.delete(f"/api/shared/{sid}").status_code == 200
    assert [x["template"] for x in gm.get("/api/shared").json()] == ["village"]
    assert gm.get("/api/export/campaign").json()["shared"][0]["template"] == "village"


def test_auto_create_once(config):
    app1 = create_app(config)
    c = client_for(app1, "Gm")
    rows = c.get("/api/shared").json()
    assert [r["template"] for r in rows] == ["village"]
    assert c.delete(f"/api/shared/{rows[0]['id']}").status_code == 200
    app1.state.db.close()
    app2 = create_app(config)  # same database: the deleted auto sheet must not come back
    c2 = client_for(app2, "Gm")
    assert c2.get("/api/shared").json() == []
    app2.state.db.close()


def test_old_documents_gain_list_ids_once(config, pack):
    from st_vtt import characters as chars
    from st_vtt.db import Database

    def without_ids(doc):
        if isinstance(doc, dict):
            return {k: without_ids(v) for k, v in doc.items() if k != "id"}
        return [without_ids(x) for x in doc] if isinstance(doc, list) else doc

    # Documents as they were before list items had ids, written before the app first starts.
    char = chars.new_character(pack, pack.playbooks[0], "Old")
    char["gear"]["items"] = [{"name": "rope", "bulk": 1}, {"name": "lamp", "bulk": 1}]
    char["followers"] = [{"name": "Hob", "is_group": True, "members": [{"name": "a", "hp": 3}]}]
    char["sections"]["relationships"] = [{"who": "Mab", "what": "owes me", "close": False}]
    village = pack.shared_sheets[0]
    sheet = without_ids(chars.new_shared_sheet(pack, village))
    record = chars.new_record("npc", "Mab")
    record["ties"] = [{"type": "kin-of", "to": "x", "note": ""}]
    db = Database(config.database_path)
    db.insert_character("c1", "Alice", without_ids(char))
    db.insert_shared("s1", village.id, sheet)
    db.insert_record("r1", "npc", record)
    db.set_meta(f"auto_created:{village.id}", "1")
    db.close()

    app1 = create_app(config)
    rows = {"c": app1.state.db.get_character("c1"), "s": app1.state.db.get_shared("s1"), "r": app1.state.db.get_record("r1")}
    c = rows["c"]["data"]
    assert all(i["id"] for i in c["gear"]["items"]) and c["followers"][0]["id"] and c["followers"][0]["members"][0]["id"]
    assert c["sections"]["relationships"][0]["id"]
    assert all(r["id"] for r in rows["s"]["data"]["sections"]["resources"])
    assert rows["r"]["data"]["ties"][0]["id"]
    # and nothing else changed
    assert without_ids(c) == without_ids(char)
    assert without_ids(rows["s"]["data"]) == sheet
    assert without_ids(rows["r"]["data"]) == without_ids(record)
    app1.state.db.close()

    app2 = create_app(config)  # a second start leaves them alone
    assert app2.state.db.get_character("c1") == rows["c"]
    assert app2.state.db.get_shared("s1") == rows["s"]
    assert app2.state.db.get_record("r1") == rows["r"]
    app2.state.db.close()


def test_chat_commands_and_visibility(gm, alice, bob):
    assert alice.post("/api/chat", json={"text": "hello"}).status_code == 200
    assert alice.post("/api/chat", json={"text": "/roll 2d6+1"}).status_code == 200
    assert alice.post("/api/chat", json={"text": "/roll 2d"}).status_code == 400
    assert alice.post("/api/chat", json={"text": "/w bob psst"}).status_code == 200
    assert alice.post("/api/chat", json={"text": "/gmroll 1d20"}).status_code == 200
    assert alice.post("/api/chat", json={"text": "/nope"}).status_code == 400

    def kinds(c):
        return [(m["kind"], m["author"]) for m in c.get("/api/messages").json()]

    assert kinds(alice) == [("chat", "Alice"), ("roll", "Alice"), ("whisper", "Alice"), ("roll", "Alice")]
    assert kinds(bob) == [("chat", "Alice"), ("roll", "Alice"), ("whisper", "Alice")]
    assert kinds(gm) == kinds(alice)
    assert bob.delete("/api/messages").status_code == 403
    assert gm.delete("/api/messages").status_code == 200
    assert [m["kind"] for m in alice.get("/api/messages").json()] == ["system"]


def test_move_roll_with_debility(alice):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    alice.post(f"/api/characters/{cid}/patch", json={"path": "/stats/str", "value": 2})
    alice.post(f"/api/characters/{cid}/patch", json={"path": "/debilities/battered", "value": True})
    r = alice.post("/api/roll", json={"character_id": cid, "move_id": "brawl", "advantage": False})
    assert r.status_code == 200, r.text
    msg = alice.get("/api/messages").json()[-1]
    p = msg["payload"]
    assert p["mode"] == "disadvantage" and p["auto_disadvantage"] == ["Battered"]
    assert p["roll"]["dice"][0]["die"] == "3d6kl2"
    assert p["stat_mod"] == 2 and p["tier"] in ("10+", "7-9", "6-")
    assert p["outcome"]
    # damage die preset resolves against the character
    r = alice.post("/api/roll", json={"character_id": cid, "expr": "{damage_die}+{str}", "label": "Damage"})
    assert r.status_code == 200
    p = alice.get("/api/messages").json()[-1]["payload"]
    assert p["roll"]["dice"][0]["die"] == "1d8" and p["roll"]["modifier"] == 2
    # +nothing move
    r = alice.post("/api/roll", json={"character_id": cid, "move_id": "last_breath"})
    assert alice.get("/api/messages").json()[-1]["payload"]["stat"] is None


def test_request_roll_gm_only(gm, alice):
    assert alice.post("/api/request_roll", json={"user": "Gm", "label": "x"}).status_code == 403
    assert gm.post("/api/request_roll", json={"user": "Alice", "label": "Take a Risk", "stat": "wis"}).status_code == 200
    m = alice.get("/api/messages").json()[-1]
    assert m["kind"] == "request" and m["payload"]["to"] == "Alice"


def test_websocket_roundtrip(app, gm, alice, bob):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]

    def recv(ws):
        return json.loads(ws.receive_text())

    with alice.websocket_connect("/ws") as wa:
        assert recv(wa) == {"type": "presence", "users": ["Alice"]}
        with bob.websocket_connect("/ws") as wb:
            assert recv(wa)["users"] == ["Alice", "Bob"]
            assert recv(wb)["users"] == ["Alice", "Bob"]
            with gm.websocket_connect("/ws") as wg:
                for ws in (wa, wb, wg):
                    assert recv(ws)["users"] == ["Alice", "Bob", "Gm"]

                # alice patches her own character: everyone sees it, alice gets an ack
                wa.send_text(json.dumps({"type": "patch", "entity": "character", "id": cid, "path": "/hp/current", "value": 7, "ref": 1}))
                for ws in (wa, wb, wg):
                    ev = recv(ws)
                    assert ev["type"] == "patch" and ev["value"] == 7 and ev["by"] == "Alice" and ev["revision"] == 1
                assert recv(wa) == {"type": "ack", "ref": 1}
                assert alice.get(f"/api/characters/{cid}").json()["data"]["hp"]["current"] == 7

                # bob may not edit alice's character: error only to bob
                wb.send_text(json.dumps({"type": "patch", "entity": "character", "id": cid, "path": "/hp/current", "value": 0, "ref": 2}))
                err = recv(wb)
                assert err["type"] == "error" and err["ref"] == 2

                # gm_notes patch reaches the gm only
                wg.send_text(json.dumps({"type": "patch", "entity": "character", "id": cid, "path": "/gm_notes", "value": "shh"}))
                assert recv(wg)["path"] == "/gm_notes"

                # a public chat reaches everyone (and proves alice/bob did not get the gm_notes patch)
                wb.send_text(json.dumps({"type": "chat", "text": "hi"}))
                for ws in (wa, wb, wg):
                    ev = recv(ws)
                    assert ev["type"] == "message" and ev["message"]["payload"]["text"] == "hi"

                # whisper to gm: alice and gm see it, bob does not
                wa.send_text(json.dumps({"type": "chat", "text": "/w Gm secret"}))
                assert recv(wa)["message"]["kind"] == "whisper"
                assert recv(wg)["message"]["kind"] == "whisper"
                wb.send_text(json.dumps({"type": "roll", "expr": "1d6"}))
                for ws in (wa, wb, wg):
                    ev = recv(ws)
                    assert ev["type"] == "message" and ev["message"]["kind"] == "roll"

                # bad roll expression: error only to sender
                wb.send_text(json.dumps({"type": "roll", "expr": "2d", "ref": 3}))
                assert recv(wb)["type"] == "error"
            # gm left
            assert recv(wa)["users"] == ["Alice", "Bob"]
            assert recv(wb)["users"] == ["Alice", "Bob"]
        assert recv(wa)["users"] == ["Alice"]


def _recv_until(ws, n):
    """The next n events, skipping presence."""
    out = []
    while len(out) < n:
        ev = json.loads(ws.receive_text())
        if ev["type"] != "presence":
            out.append(ev)
    return out


def test_conflicting_sets_reach_everyone_in_server_order(gm, alice, bob):
    sid = sheet_id(alice)
    with alice.websocket_connect("/ws") as wa, bob.websocket_connect("/ws") as wb:
        wa.send_text(json.dumps({"type": "patch", "entity": "shared", "id": sid, "path": "/stats/stores", "value": 1, "ref": 1, "client": "a"}))
        wb.send_text(json.dumps({"type": "patch", "entity": "shared", "id": sid, "path": "/stats/stores", "value": 2, "ref": 1, "client": "b"}))
        seen_a = [e for e in _recv_until(wa, 3) if e["type"] == "patch"]
        seen_b = [e for e in _recv_until(wb, 3) if e["type"] == "patch"]
    # both clients see the same order, with the sender's ref, and the last is what was stored
    order = [(e["client"], e["ref"], e["value"]) for e in seen_a]
    assert order == [(e["client"], e["ref"], e["value"]) for e in seen_b]
    assert sorted(order) == [("a", 1, 1), ("b", 1, 2)]
    assert gm.get(f"/api/shared/{sid}").json()["data"]["stats"]["stores"] == order[-1][2]


def test_resent_patch_is_acked_not_reapplied(gm, alice, bob):
    sid = sheet_id(alice)
    npc = {"type": "patch", "entity": "shared", "id": sid, "path": "/sections/npcs/-", "value": {"name": "Bandit"}, "client": "a"}

    def npcs():
        return [n["name"] for n in gm.get(f"/api/shared/{sid}").json()["data"]["sections"].get("npcs", [])]

    assert alice.get("/api/state?client=a").json()["applied_ref"] == 0
    with alice.websocket_connect("/ws") as wa:
        wa.send_text(json.dumps({**npc, "ref": 3}))
        assert [e["type"] for e in _recv_until(wa, 2)] == ["patch", "ack"]
    assert npcs() == ["Bandit"]
    assert alice.get("/api/state?client=a").json()["applied_ref"] == 3
    # reconnected: the patch that was in flight is resent, and a new one follows
    with alice.websocket_connect("/ws") as wa:
        wa.send_text(json.dumps({**npc, "ref": 3}))
        assert _recv_until(wa, 1) == [{"type": "ack", "ref": 3}]
        wa.send_text(json.dumps({**npc, "ref": 4, "value": {"name": "Wolf"}}))
        assert [e["type"] for e in _recv_until(wa, 2)] == ["patch", "ack"]
    assert npcs() == ["Bandit", "Wolf"]
    # refs are per user: another player cannot block this client by reusing its id
    assert bob.get("/api/state?client=a").json()["applied_ref"] == 0
    with bob.websocket_connect("/ws") as wb:
        wb.send_text(json.dumps({**npc, "ref": 1, "value": {"name": "Crow"}}))
        assert [e["type"] for e in _recv_until(wb, 2)] == ["patch", "ack"]
    assert npcs() == ["Bandit", "Wolf", "Crow"]


def test_applied_refs_survive_a_restart(config):
    # The patch was saved, but the server went down before the ack reached the browser,
    # so after the restart the browser resends it.
    npc = {"type": "patch", "entity": "shared", "path": "/sections/npcs/-", "value": {"name": "Bandit"}, "ref": 7, "client": "a"}
    app1 = create_app(config)
    c1 = client_for(app1, "Alice")
    sid = sheet_id(c1)
    with c1.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({**npc, "id": sid}))
        assert [e["type"] for e in _recv_until(ws, 2)] == ["patch", "ack"]
    app1.state.db.close()

    app2 = create_app(config)
    c2 = client_for(app2, "Alice")
    assert c2.get("/api/state?client=a").json()["applied_ref"] == 7
    with c2.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({**npc, "id": sid}))
        assert _recv_until(ws, 1) == [{"type": "ack", "ref": 7}]
    assert [n["name"] for n in c2.get(f"/api/shared/{sid}").json()["data"]["sections"]["npcs"]] == ["Bandit"]
    app2.state.db.close()


def test_stale_applied_refs_are_forgotten(tmp_path):
    from st_vtt.db import APPLIED_REFS_TTL, Database

    db = Database(tmp_path / "t.db")
    sid = db.insert_shared("s", "village", {})["id"]
    db.save_shared(sid, {"n": 1}, ("Alice", "old", 3))
    db.save_shared(sid, {"n": 2}, ("Alice", "new", 5))
    db.save_shared(sid, {"n": 3}, ("Alice", "new", 4))  # never lowers it
    with db._lock:
        db._conn.execute("UPDATE applied_refs SET updated_at=updated_at-? WHERE client='old'", (APPLIED_REFS_TTL + 1,))
        db._conn.commit()
    db.close()
    db = Database(tmp_path / "t.db")
    assert (db.applied_ref("Alice", "old"), db.applied_ref("Alice", "new"), db.applied_ref("Bob", "new")) == (0, 5, 0)
    db.close()


def test_refused_patch_is_not_counted_as_applied(alice):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    with alice.websocket_connect("/ws") as wa:
        wa.send_text(json.dumps({"type": "patch", "entity": "character", "id": cid, "path": "", "op": "remove", "ref": 1, "client": "a"}))
        assert _recv_until(wa, 1)[0]["type"] == "error"
    assert alice.get("/api/state?client=a").json()["applied_ref"] == 0


def test_unauthenticated_ws_rejected(app):
    c = raw_client(app)
    with pytest.raises(Exception):
        with c.websocket_connect("/ws"):
            pass


def test_text_patch_via_api_keeps_both_edits(gm, alice, bob):
    from diff_match_patch import diff_match_patch

    dmp = diff_match_patch()
    sid = sheet_id(gm)
    base = "Season log:\n"
    assert gm.post(f"/api/shared/{sid}/patch", json={"path": "/notes", "value": base}).status_code == 200
    pa = dmp.patch_toText(dmp.patch_make(base, base + "- Alice fixed the roof\n"))
    pb = dmp.patch_toText(dmp.patch_make(base, "Bob was here. " + base))
    assert alice.post(f"/api/shared/{sid}/patch", json={"path": "/notes", "op": "text_patch", "patch": pa}).status_code == 200
    assert bob.post(f"/api/shared/{sid}/patch", json={"path": "/notes", "op": "text_patch", "patch": pb}).status_code == 200
    notes = gm.get(f"/api/shared/{sid}").json()["data"]["notes"]
    assert notes == "Bob was here. Season log:\n- Alice fixed the roof\n"
    assert bob.post(f"/api/shared/{sid}/patch", json={"path": "/notes", "op": "text_patch", "patch": "garbage"}).status_code == 400


def test_ephemeral_focus_and_typing(app, gm, alice, bob):
    def recv(ws):
        return json.loads(ws.receive_text())

    with alice.websocket_connect("/ws") as wa:
        recv(wa)  # presence
        with bob.websocket_connect("/ws") as wb:
            recv(wa); recv(wb)
            wa.send_text(json.dumps({"type": "focus", "entity": "shared", "id": "main", "path": "/notes", "client": "ca"}))
            ev = recv(wb)
            assert ev == {"type": "field_presence", "user": "Alice", "client": "ca", "entity": "shared", "id": "main", "path": "/notes"}
            wa.send_text(json.dumps({"type": "typing", "active": True}))
            assert recv(wb) == {"type": "typing", "user": "Alice", "active": True}
            # a late joiner asks for the current focus snapshot
            with gm.websocket_connect("/ws") as wg:
                recv(wg); recv(wa); recv(wb)  # presence x3
                wg.send_text(json.dumps({"type": "presence_sync", "client": "cg"}))
                ev = recv(wg)
                assert ev["type"] == "field_presence" and ev["user"] == "Alice" and ev["path"] == "/notes"
            recv(wa); recv(wb)  # gm left
            wa.send_text(json.dumps({"type": "blur", "client": "ca"}))
            assert recv(wb)["path"] is None
            # alice never receives her own ephemeral events: a chat proves the next event is the chat
            wb.send_text(json.dumps({"type": "chat", "text": "ping"}))
            assert recv(wa)["type"] == "message"


def test_share_move_to_chat(alice, bob):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    assert alice.post("/api/share_move", json={"character_id": cid, "move_id": "brawl"}).status_code == 200
    m = bob.get("/api/messages").json()[-1]
    assert m["kind"] == "move" and m["author"] == "Alice"
    assert m["payload"]["name"] == "Brawl" and m["payload"]["character"] == "Bryn" and "10+" in m["payload"]["outcomes"]
    # shared-sheet move without a character, and an unknown move
    assert bob.post("/api/share_move", json={"move_id": "muster"}).status_code == 200
    assert bob.get("/api/messages").json()[-1]["payload"]["character"] is None
    assert bob.post("/api/share_move", json={"move_id": "nope"}).status_code == 400


def test_single_session_lock(app):
    a1 = client_for(app, "Alice")
    assert a1.get("/api/me").json()["name"] == "Alice"
    # nobody connected: a second browser simply takes over and the first cookie dies
    a2 = client_for(app, "Alice")
    assert a1.get("/api/me").json() is None
    assert a1.get("/api/state").status_code == 401
    assert a2.get("/api/me").json()["name"] == "Alice"
    # same browser logging in again keeps its session
    assert a2.post("/api/login", json={"name": "Alice"}).status_code == 200
    assert a2.get("/api/me").json()["name"] == "Alice"
    with a2.websocket_connect("/ws") as ws2:
        json.loads(ws2.receive_text())
        # a live connection locks the user out elsewhere...
        a3 = raw_client(app)
        r = a3.post("/api/login", json={"name": "Alice"})
        assert r.status_code == 409 and "another device" in r.json()["detail"]
        assert a2.get("/api/me").json()["name"] == "Alice"
        # ...unless forced, which kicks the old connection with 4409 and invalidates its cookie
        r = a3.post("/api/login", json={"name": "Alice", "force": True})
        assert r.status_code == 200
        with pytest.raises(Exception) as ei:
            ws2.receive_text()
        assert "4409" in str(ei.value) or getattr(ei.value, "code", None) == 4409
        assert a2.get("/api/me").json() is None
        assert a3.get("/api/me").json()["name"] == "Alice"
    # password still required when forcing
    assert raw_client(app).post("/api/login", json={"name": "Bob", "force": True}).status_code == 401
    # logout invalidates the session for every copy of the cookie
    assert a3.post("/api/logout").status_code == 200
    assert a3.get("/api/me").json() is None


def test_multiple_sessions_when_disabled(config):
    config.single_session = False
    app = create_app(config)
    a1 = client_for(app, "Alice")
    a2 = client_for(app, "Alice")
    assert a1.get("/api/me").json()["name"] == "Alice" and a2.get("/api/me").json()["name"] == "Alice"
    app.state.db.close()


def test_shared_sheet_stat_rolls(gm, alice):
    """A shared-sheet move can roll one of that sheet's own stats."""
    sid = sheet_id(gm)
    assert gm.post(f"/api/shared/{sid}/patch", json={"path": "/stats/walls", "value": 2}).status_code == 200
    r = alice.post("/api/roll", json={"shared_id": sid, "move_id": "muster", "stat": "walls"})
    assert r.status_code == 200, r.text
    p = alice.get("/api/messages").json()[-1]["payload"]
    assert p["stat"] == "walls" and p["stat_label"] == "Walls" and p["stat_mod"] == 2
    assert p["shared_id"] == sid and p["character_id"] is None
    assert p["total"] == p["roll"]["total"] + 2

    # character stats are not in scope for a shared sheet, and vice versa
    assert alice.post("/api/roll", json={"shared_id": sid, "stat": "str"}).status_code == 400
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    assert alice.post("/api/roll", json={"character_id": cid, "stat": "walls"}).status_code == 400
    assert alice.post("/api/roll", json={"character_id": cid, "shared_id": sid}).status_code == 400

    # a marked character debility must not bleed into a shared-sheet roll
    alice.post(f"/api/characters/{cid}/patch", json={"path": "/debilities/battered", "value": True})
    alice.post("/api/roll", json={"shared_id": sid, "stat": "walls"})
    p = alice.get("/api/messages").json()[-1]["payload"]
    assert p["mode"] == "normal" and p["auto_disadvantage"] == []

    # gm-only sheets are not rollable by players
    gsid = gm.post("/api/shared", json={"template": "gm_screen"}).json()["id"]
    assert alice.post("/api/roll", json={"shared_id": gsid}).status_code == 404
    assert gm.post("/api/roll", json={"shared_id": gsid}).status_code == 200


def test_roll_modifiers_and_bonus_bounds(alice):
    sid = sheet_id(alice)
    # the example pack's Muster move declares no modifiers
    assert alice.post("/api/roll", json={"shared_id": sid, "move_id": "muster", "modifiers": {"value": 1}}).status_code == 400
    # free-form bonus is clamped to a sane range
    assert alice.post("/api/roll", json={"shared_id": sid, "bonus": 3}).status_code == 200
    assert alice.get("/api/messages").json()[-1]["payload"]["bonus"] == 3
    assert alice.post("/api/roll", json={"shared_id": sid, "bonus": 99}).status_code == 400
    assert alice.post("/api/roll", json={"shared_id": sid, "bonus": -99}).status_code == 400


def test_declared_modifier_options(config):
    """A move's `modifiers` give the dialog a bounded picker instead of free text."""
    import json as _json
    import shutil

    src = ROOT / "content" / "example"
    tmp = config.database_path.parent / "pack"
    shutil.copytree(src, tmp)
    sheets = _json.loads((tmp / "shared_sheets.json").read_text())
    muster = next(m for m in sheets["shared_sheets"][0]["moves"] if m["id"] == "muster")
    muster["roll"]["modifiers"] = [{
        "id": "value", "label": "Item Value", "default": 0,
        "options": [{"label": f"Value {v}", "value": -v} for v in range(4)],
    }]
    (tmp / "shared_sheets.json").write_text(_json.dumps(sheets))
    config.content_pack = str(tmp)
    app = create_app(config)
    c = client_for(app, "Alice")
    sid = sheet_id(c)
    content_move = next(m for m in c.get("/api/content").json()["shared_sheets"][0]["moves"] if m["id"] == "muster")
    assert [o["label"] for o in content_move["roll"]["modifiers"][0]["options"]] == ["Value 0", "Value 1", "Value 2", "Value 3"]

    assert c.post("/api/roll", json={"shared_id": sid, "move_id": "muster", "modifiers": {"value": -2}}).status_code == 200
    p = c.get("/api/messages").json()[-1]["payload"]
    assert p["modifiers"] == [{"id": "value", "label": "Item Value", "option": "Value 2", "value": -2}]
    assert p["bonus"] == -2
    # omitting a declared modifier applies its default
    c.post("/api/roll", json={"shared_id": sid, "move_id": "muster"})
    p = c.get("/api/messages").json()[-1]["payload"]
    assert p["modifiers"][0]["option"] == "Value 0" and p["bonus"] == 0
    # a value outside the declared options is refused
    assert c.post("/api/roll", json={"shared_id": sid, "move_id": "muster", "modifiers": {"value": -9}}).status_code == 400
    app.state.db.close()


def _roll_until(client, cid, move_id, tier, tries=40):
    """Roll a move until it lands on `tier`; returns the chat message."""
    for _ in range(tries):
        client.post("/api/roll", json={"character_id": cid, "move_id": move_id})
        msg = client.get("/api/messages").json()[-1]
        if msg["payload"]["tier"] == tier:
            return msg
    raise AssertionError(f"never rolled {tier}")


def test_roll_card_applies_its_outcome(alice):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    msg = _roll_until(alice, cid, "trailsense", "10+")
    # the pack's authored action, plus nothing else on a hit
    assert [a["kind"] for a in msg["payload"]["actions"]] == ["hold"]
    assert msg["payload"]["actions"][0]["label"] == "Hold 2 Focus"

    r = alice.post(f"/api/messages/{msg['id']}/apply", json={"index": 0})
    assert r.status_code == 200, r.text
    doc = alice.get(f"/api/characters/{cid}").json()["data"]
    assert doc["moves"]["hold"]["Focus"] == 2

    card = [m for m in alice.get("/api/messages").json() if m["id"] == msg["id"]][0]
    assert card["payload"]["applied"]["0"] == {"by": "Alice", "detail": "+2 Focus"}
    # applying twice is refused
    again = alice.post(f"/api/messages/{msg['id']}/apply", json={"index": 0})
    assert again.status_code == 400 and "already applied" in again.json()["detail"]


def test_marking_xp_needs_no_authoring(alice):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    msg = _roll_until(alice, cid, "sharp_tongue", "6-")
    assert msg["payload"]["actions"][0] == {"kind": "xp", "n": 1, "label": "Mark XP"}
    alice.post(f"/api/messages/{msg['id']}/apply", json={"index": 0})
    assert alice.get(f"/api/characters/{cid}").json()["data"]["xp"] == 1


def test_hp_and_debility_outcomes(alice):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    msg = _roll_until(alice, cid, "trailsense", "6-")
    kinds = [a["kind"] for a in msg["payload"]["actions"]]
    assert kinds == ["xp", "hp", "debility"]

    alice.post(f"/api/messages/{msg['id']}/apply", json={"index": 1})
    doc = alice.get(f"/api/characters/{cid}").json()["data"]
    assert 14 <= doc["hp"]["current"] < 18, "1d4 damage came off the top"

    # "mark a debility" leaves the choice to the player
    blank = alice.post(f"/api/messages/{msg['id']}/apply", json={"index": 2})
    assert blank.status_code == 400 and "pick a debility" in blank.json()["detail"]
    assert alice.post(f"/api/messages/{msg['id']}/apply", json={"index": 2, "choice": "rattled"}).status_code == 200
    assert alice.get(f"/api/characters/{cid}").json()["data"]["debilities"]["rattled"] is True


def test_only_someone_who_may_edit_the_sheet_can_apply(gm, alice, bob):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    msg = _roll_until(alice, cid, "sharp_tongue", "6-")
    denied = bob.post(f"/api/messages/{msg['id']}/apply", json={"index": 0})
    assert denied.status_code == 403
    assert gm.post(f"/api/messages/{msg['id']}/apply", json={"index": 0}).status_code == 200


def test_shared_sheet_outcomes_touch_the_shared_sheet(gm):
    sid = sheet_id(gm)
    gm.post(f"/api/shared/{sid}/patch", json={"path": "/stats/luck", "value": 2})
    for _ in range(40):
        gm.post("/api/roll", json={"shared_id": sid, "move_id": "muster"})
        msg = gm.get("/api/messages").json()[-1]
        if msg["payload"]["tier"] == "6-":
            break
    else:
        raise AssertionError("never rolled 6-")
    stat = next(a for a in msg["payload"]["actions"] if a["kind"] == "stat")
    index = msg["payload"]["actions"].index(stat)
    assert gm.post(f"/api/messages/{msg['id']}/apply", json={"index": index}).status_code == 200
    assert gm.get("/api/shared").json()[0]["data"]["stats"]["luck"] == 1


def test_a_moves_own_checklist_is_stored_like_a_sections(alice):
    cid = alice.post("/api/characters", json={"playbook": "wanderer", "name": "Pedr"}).json()["id"]
    # Hardened is "each time you take this move, pick 1", with a write-in on one option.
    assert alice.post(f"/api/characters/{cid}/patch",
                      json={"path": "/moves/taken", "value": "hardened", "op": "list_add"}).status_code == 200
    assert alice.post(f"/api/characters/{cid}/patch",
                      json={"path": "/moves/options/hardened", "value": ["hardened_knack"]}).status_code == 200
    assert alice.post(f"/api/characters/{cid}/patch",
                      json={"path": "/option_text/hardened/hardened_knack", "value": "shoeing horses"}).status_code == 200

    doc = alice.get(f"/api/characters/{cid}").json()["data"]
    assert doc["moves"]["options"]["hardened"] == ["hardened_knack"]
    assert doc["option_text"]["hardened"]["hardened_knack"] == "shoeing horses"
