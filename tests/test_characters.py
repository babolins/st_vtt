"""Document construction from a content pack."""

import pytest

from st_vtt.characters import default_section_value, ensure_list_ids, new_character, new_shared_sheet, validate_import
from st_vtt.content import ContentPack


def _pack(**overrides) -> ContentPack:
    raw = {
        "pack": {"id": "t", "name": "T", "stats": [{"id": "str", "label": "STR"}]},
        "playbooks": [
            {
                "id": "pb",
                "name": "PB",
                "hp_max": 10,
                "inserts": ["gear"],
                "sections": [
                    {
                        "id": "appearance",
                        "title": "Appearance",
                        "type": "lines",
                        "lines": [
                            {
                                "id": "age",
                                "write_in": "or make something up",
                                "options": [
                                    {"id": "age_young", "label": "young & brash"},
                                    {"id": "age_old", "label": "old & leathery"},
                                ],
                            },
                            {
                                "id": "voice",
                                "options": [
                                    {"id": "voice_soft", "label": "soft-spoken"},
                                    {"id": "voice_loud", "label": "gravelly voice"},
                                ],
                            },
                        ],
                    }
                ],
            }
        ],
    }
    raw.update(overrides)
    return ContentPack.model_validate(raw)


def test_new_character_seeds_its_sections_and_inserts():
    pack = _pack()
    doc = new_character(pack, pack.playbooks[0], "Pedr")
    assert doc["inserts"] == ["gear"]
    assert doc["sections"]["appearance"] == {"age": None, "voice": None}


def test_an_insert_brings_its_sections_and_fixed_moves():
    pack = _pack(
        inserts=[
            {
                "id": "mule",
                "name": "Mule",
                "starting_moves": {"fixed": ["stubborn"]},
                "moves": [{"id": "stubborn", "name": "Stubborn"}],
                "sections": [
                    {
                        "id": "mule_temper",
                        "title": "Temperament",
                        "type": "choose",
                        "options": [{"id": "placid", "label": "Placid"}],
                    }
                ],
            }
        ],
        playbooks=[{"id": "pb", "name": "PB", "hp_max": 10, "inserts": ["gear", "mule"]}],
    )
    doc = new_character(pack, pack.playbooks[0], "Pedr")
    assert doc["inserts"] == ["gear", "mule"]
    assert doc["moves"]["taken"] == ["stubborn"]
    assert doc["sections"]["mule_temper"] is None


def test_section_start_seeds_a_new_sheet():
    pack = _pack(
        shared_sheets=[
            {
                "id": "village",
                "name": "Village",
                "sections": [
                    {
                        "id": "resources",
                        "title": "Resources",
                        "type": "table",
                        "columns": [{"id": "resource", "label": "Resource"}],
                        "start": [{"resource": "Farming"}, {"resource": "Distilling"}],
                    }
                ],
            }
        ]
    )
    doc = new_shared_sheet(pack, pack.shared_sheets[0])
    assert [{k: v for k, v in r.items() if k != "id"} for r in doc["sections"]["resources"]] == [
        {"resource": "Farming"},
        {"resource": "Distilling"},
    ]
    # the seed is copied, not shared between sheets
    doc["sections"]["resources"].append({"resource": "Mill"})
    assert len(new_shared_sheet(pack, pack.shared_sheets[0])["sections"]["resources"]) == 2


def test_default_section_value_per_type():
    pack = _pack(
        playbooks=[
            {
                "id": "pb",
                "name": "PB",
                "hp_max": 10,
                "sections": [
                    {"id": "a", "title": "A", "type": "choose", "options": [{"id": "x", "label": "X"}]},
                    {"id": "b", "title": "B", "type": "multichoose", "options": [{"id": "y", "label": "Y"}]},
                    {"id": "c", "title": "C", "type": "pips", "max": 3},
                    {"id": "d", "title": "D", "type": "text"},
                    {"id": "e", "title": "E", "type": "table", "columns": [{"id": "col", "label": "Col"}]},
                    {"id": "f", "title": "F", "type": "names", "lists": [{"label": "Hills", "names": ["Bryn"]}]},
                ],
            }
        ]
    )
    got = [default_section_value(s) for s in pack.playbooks[0].sections]
    assert got == [None, [], 0, "", [], {"origin": "", "name": ""}]


def test_import_fills_in_what_a_hand_written_document_leaves_out():
    pack = _pack()
    doc, warnings = validate_import(pack, {"playbook": "pb", "name": "Pedr"})
    assert doc["sections"]["appearance"] == {"age": None, "voice": None}
    assert doc["inserts"] == ["gear"]
    assert warnings == []


def test_a_new_sheet_has_somewhere_to_keep_a_moves_picks():
    pack = _pack()
    doc = new_character(pack, pack.playbooks[0], "Pedr")
    assert doc["moves"]["options"] == {}
    shared = new_shared_sheet(
        pack,
        ContentPack.model_validate(
            {
                "pack": {"id": "t", "name": "T", "stats": [{"id": "str", "label": "STR"}]},
                "shared_sheets": [{"id": "village", "name": "Village"}],
            }
        ).shared_sheets[0],
    )
    assert shared["moves"]["options"] == {}


def _table_pack() -> ContentPack:
    """`crew` is a table on one playbook and a checklist on the other; `hirelings` is a table on an insert."""
    table = {
        "id": "crew",
        "title": "Crew",
        "type": "table",
        "columns": [{"id": "name", "label": "Name"}],
        "start": [{"name": "Bryn"}, {"name": "Mab"}],
    }
    checklist = {"id": "crew", "title": "Crew", "type": "checklist", "options": [{"id": "cook", "label": "Cook"}]}
    return _pack(
        inserts=[
            {
                "id": "band",
                "name": "Band",
                "sections": [
                    {
                        "id": "hirelings",
                        "title": "Hirelings",
                        "type": "table",
                        "columns": [{"id": "name", "label": "Name"}],
                    }
                ],
            }
        ],
        playbooks=[
            {"id": "pb", "name": "PB", "hp_max": 10, "sections": [table]},
            {"id": "pb2", "name": "PB2", "hp_max": 10, "sections": [checklist]},
        ],
    )


def test_table_start_rows_get_ids():
    pack = _table_pack()
    rows = new_character(pack, pack.playbooks[0], "Pedr")["sections"]["crew"]
    assert [r["name"] for r in rows] == ["Bryn", "Mab"]
    assert all(isinstance(r["id"], str) and r["id"] for r in rows)
    assert rows[0]["id"] != rows[1]["id"]
    assert "id" not in pack.playbooks[0].sections[0].start[0]  # the pack's copy is untouched


def test_ensure_list_ids_fills_missing_and_duplicate_ids():
    pack = _table_pack()
    doc = new_character(pack, pack.playbooks[0], "Pedr")
    doc["gear"]["items"] = [{"id": "g1", "name": "rope"}, {"id": "g1", "name": "rope"}, {"name": "lamp"}, "junk"]
    doc["followers"] = [{"name": "Hob", "members": [{"name": "a"}, {"name": "b", "id": 7}]}]
    doc["arcana"] = [{"name": "ring", "id": ""}]
    doc["custom_moves"] = [{"id": "custom_x", "name": "Mine"}]
    doc["sections"]["crew"] = [{"name": "Bryn"}]
    doc["sections"]["hirelings"] = [{"name": "Dafydd"}]  # insert not taken: rows kept, still need ids
    assert ensure_list_ids(pack, doc, "character") is True
    items = doc["gear"]["items"]
    assert items[0]["id"] == "g1" and items[1]["id"] not in ("g1", "") and isinstance(items[2]["id"], str)
    assert items[3] == "junk"
    members = doc["followers"][0]["members"]
    assert doc["followers"][0]["id"] and all(isinstance(m["id"], str) for m in members)
    assert doc["arcana"][0]["id"]
    assert doc["custom_moves"][0]["id"] == "custom_x"
    assert doc["sections"]["crew"][0]["id"] and doc["sections"]["hirelings"][0]["id"]
    assert ensure_list_ids(pack, doc, "character") is False  # and only once


def test_ensure_list_ids_leaves_other_sections_alone():
    pack = _table_pack()
    doc = new_character(pack, pack.playbooks[1], "Pedr")
    doc["sections"]["crew"] = ["cook"]  # the checklist `crew`, sharing a table's id
    assert ensure_list_ids(pack, doc, "character") is False
    assert doc["sections"]["crew"] == ["cook"]


def test_ensure_list_ids_on_records_and_shared_sheets():
    pack = _pack(
        shared_sheets=[
            {
                "id": "v",
                "sections": [
                    {"id": "npcs", "title": "NPCs", "type": "table", "columns": [{"id": "name", "label": "Name"}]}
                ],
            }
        ]
    )
    rec = {"ties": [{"type": "kin-of", "to": "x", "note": ""}]}
    assert ensure_list_ids(pack, rec, "record") is True and rec["ties"][0]["id"]
    sheet = new_shared_sheet(pack, pack.shared_sheets[0])
    sheet["sections"]["npcs"] = [{"name": "Wolf"}]
    assert ensure_list_ids(pack, sheet, "shared") is True and sheet["sections"]["npcs"][0]["id"]


def test_import_gives_list_items_ids():
    pack = _table_pack()
    doc = new_character(pack, pack.playbooks[0], "Pedr")
    doc["gear"]["items"] = [{"name": "rope"}]
    doc["sections"]["crew"] = [{"name": "Bryn"}]
    clean, _ = validate_import(pack, doc)
    assert clean["gear"]["items"][0]["id"] and clean["sections"]["crew"][0]["id"]


def test_import_of_something_that_is_not_a_character():
    with pytest.raises(ValueError, match="character must be a JSON object"):
        validate_import(_pack(), ["playbook", "pb"])


def test_import_with_an_unknown_playbook_keeps_it_and_brings_no_sections():
    pack = _pack()
    doc, warnings = validate_import(pack, {"playbook": "druid", "name": "Pedr"})
    assert warnings == ["unknown playbook 'druid'; sheet will render with generic sections only"]
    assert doc["playbook"] == "druid" and doc["name"] == "Pedr"
    # The generic parts of a sheet are filled in, but none of another playbook's sections.
    assert doc["sections"] == {} and doc["hp"] and doc["stats"] == {"str": 0}
    # Its own sections are kept for when the playbook comes back.
    doc, _ = validate_import(pack, {"playbook": "druid", "sections": {"grove": {"oak": True}}})
    assert doc["sections"] == {"grove": {"oak": True}}


def test_import_with_no_playbook_at_all():
    doc, warnings = validate_import(_pack(), {"name": "Pedr"})
    assert warnings == ["unknown playbook None; sheet will render with generic sections only"]
    assert doc["playbook"] == ""


def test_import_from_another_pack_is_moved_into_this_one():
    doc, warnings = validate_import(_pack(), {"playbook": "pb", "pack_id": "stonetop"})
    assert warnings == ["character was exported from pack 'stonetop', current pack is 't'"]
    assert doc["pack_id"] == "t"
    # Nothing to say about one with no pack, or this pack.
    for raw in ({"playbook": "pb"}, {"playbook": "pb", "pack_id": "t"}):
        assert validate_import(_pack(), raw)[1] == []


def test_import_drops_stats_this_pack_does_not_have():
    doc, warnings = validate_import(_pack(), {"playbook": "pb", "stats": {"str": 2, "cha": 1, "luck": 3}})
    assert doc["stats"] == {"str": 2}
    assert warnings == ["unknown stat 'cha' dropped", "unknown stat 'luck' dropped"]


def test_import_keeps_moves_this_pack_does_not_have():
    pack = _pack(moves={"basic": [{"id": "brawl", "name": "Brawl"}]})
    doc, warnings = validate_import(
        pack,
        {
            "playbook": "pb",
            "moves": {"taken": ["brawl", "mystery", "custom_x"]},
            "custom_moves": [{"id": "custom_x", "name": "Mine"}],
        },
    )
    assert doc["moves"]["taken"] == ["brawl", "mystery", "custom_x"]
    # The sheet's own custom moves are known.
    assert warnings == ["unknown move 'mystery' kept as-is"]


def test_import_replaces_a_part_of_the_wrong_shape_with_its_default():
    doc, _ = validate_import(_pack(), {"playbook": "pb", "hp": "lots", "stats": [3], "moves": {"taken": ["x"]}})
    fresh = new_character(_pack(), _pack().playbooks[0], "")
    assert doc["hp"] == fresh["hp"] and doc["stats"] == {"str": 0}
    assert doc["moves"]["taken"] == ["x"]  # only what's missing from a part of the right shape is filled


def test_import_leaves_out_what_the_server_assigns():
    doc, _ = validate_import(_pack(), {"playbook": "pb", "id": "abc", "owner": "Mallory", "revision": 99})
    assert not {"id", "owner", "revision"} & doc.keys()


def test_import_into_a_pack_without_playbooks_is_refused():
    pack = ContentPack.model_validate({"pack": {"id": "t", "name": "T", "stats": [{"id": "str", "label": "STR"}]}})
    with pytest.raises(ValueError, match="pack 't' has no playbooks, so it can't hold a character"):
        validate_import(pack, {"playbook": "pb", "name": "Pedr"})


def test_import_resets_numbers_that_are_not_whole_numbers():
    pack = _pack()
    doc, warnings = validate_import(
        pack,
        {
            "playbook": "pb",
            "stats": {"str": "abc"},
            "hp": {"current": "lots", "max": 8},
            "xp": True,
            "level": 2,
            "moves": {"hold": {"readiness": 1.5, "ammo": 2}},
        },
    )
    assert doc["stats"] == {"str": 0}
    assert doc["hp"] == {"current": 10, "max": 8}
    assert (doc["xp"], doc["level"]) == (0, 2)
    assert doc["moves"]["hold"] == {"ammo": 2}
    assert warnings == [
        "/stats/str was 'abc', not a whole number; reset to 0",
        "/hp/current was 'lots', not a whole number; reset to 10",
        "/xp was True, not a whole number; reset to 0",
        "/moves/hold/readiness was 1.5, not a whole number; dropped",
    ]
