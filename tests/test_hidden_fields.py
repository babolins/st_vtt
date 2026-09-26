"""No hidden field reaches a player, by any route.

Driven by perms.HIDDEN_FIELDS, so a field added there is covered here without
touching this file, and an entity added there fails until `make` below knows how
to create one. A leak is invisible on screen, so this is the test that notices.
"""

import json

import pytest

from st_vtt.perms import HIDDEN_FIELDS
from test_api import alice, app, gm  # noqa: F401

SENTINEL = "only-the-gm-knows-this"
BASE = {"character": "/api/characters", "shared": "/api/shared", "record": "/api/records"}


def make(entity: str, alice, gm) -> str:
    """One `entity` that Alice is allowed to see."""
    if entity == "character":
        return alice.post("/api/characters", json={"playbook": "wanderer", "name": "Bryn"}).json()["id"]
    if entity == "shared":
        return gm.get("/api/shared").json()[0]["id"]  # the auto-created village, visible to the table
    if entity == "record":
        return alice.post("/api/records", json={"kind": "npc", "name": "Cerys"}).json()["id"]
    raise AssertionError(f"no way to make a {entity!r} for this test yet; add one")


def test_hidden_fields_are_top_level_names():
    # Stripping removes top-level keys, so a nested path here would never be stripped.
    for fields in HIDDEN_FIELDS.values():
        assert all(f and "/" not in f for f in fields)


@pytest.mark.parametrize("entity,field", [(e, f) for e, fields in HIDDEN_FIELDS.items() for f in fields])
def test_a_hidden_field_never_reaches_a_player(entity, field, alice, gm):
    eid = make(entity, alice, gm)
    base = BASE[entity]

    def recv(ws):
        return json.loads(ws.receive_text())

    # Over the socket: the GM writes it, and the next thing Alice hears is the GM's chat.
    with alice.websocket_connect("/ws") as wa:
        recv(wa)  # presence
        with gm.websocket_connect("/ws") as wg:
            recv(wa); recv(wg)  # presence x2
            wg.send_text(json.dumps({"type": "patch", "entity": entity, "id": eid, "path": f"/{field}", "value": SENTINEL}))
            wg.send_text(json.dumps({"type": "chat", "text": "done"}))
            assert recv(wa)["type"] == "message"

    # Over HTTP: everything that hands Alice this entity.
    urls = ["/api/state", base, f"{base}/{eid}"] + ([f"{base}/{eid}/export"] if entity != "record" else [])
    for url in urls:
        r = alice.get(url)
        assert r.status_code == 200, url
        assert SENTINEL not in r.text, url
    assert alice.get("/api/export/campaign").status_code == 403

    # The GM does get it from the same place, so the checks above are not vacuous.
    assert SENTINEL in gm.get(f"{base}/{eid}").text
