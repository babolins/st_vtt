import json

import pytest

from conftest import ROOT
from st_vtt.content import ContentError, level_up_cost, load_content, merge_pack_files


def test_example_pack_loads(pack):
    assert pack.pack.id == "example"
    assert pack.playbook("wanderer") is not None
    assert "take_a_risk" in pack.shared_moves()
    assert pack.find_move("trailsense", "wanderer").hold.name == "Focus"


def test_level_cost():
    assert level_up_cost("6 + 2*level", 1) == 8
    assert level_up_cost("6 + 2*level", 3) == 12
    with pytest.raises(ValueError):
        level_up_cost("__import__('os')", 1)


def _write_pack(tmp_path, **overrides):
    src = tmp_path / "pack"
    src.mkdir()
    base = {
        "pack": {"id": "t", "name": "T", "stats": [{"id": "str", "label": "STR"}]},
        "moves": {"basic": [{"id": "hit", "name": "Hit", "roll": {"stat": "str"}, "outcomes": {"10+": "ok"}}]},
        "playbooks": [{"id": "pb", "name": "PB", "hp_max": 10, "starting_moves": {"fixed": ["hit"]}}],
    }
    base.update(overrides)
    (src / "all.json").write_text(json.dumps(base))
    return src


def test_minimal_pack(tmp_path):
    p = load_content(_write_pack(tmp_path))
    assert p.playbooks[0].hp_max == 10


def test_unknown_stat_reference_is_reported(tmp_path):
    src = _write_pack(tmp_path, moves={"basic": [{"id": "hit", "name": "Hit", "roll": {"stat": "dex"}}]})
    with pytest.raises(ContentError) as ei:
        load_content(src)
    assert "unknown stat 'dex'" in str(ei.value)


def test_unknown_starting_move(tmp_path):
    src = _write_pack(tmp_path, playbooks=[{"id": "pb", "name": "PB", "hp_max": 10, "starting_moves": {"fixed": ["nope"]}}])
    with pytest.raises(ContentError) as ei:
        load_content(src)
    assert "unknown move 'nope'" in str(ei.value)


def test_bad_json_names_file_and_line(tmp_path):
    src = tmp_path / "pack"
    src.mkdir()
    (src / "pack.json").write_text('{"pack": {\n  "id": }')
    with pytest.raises(ContentError) as ei:
        load_content(src)
    assert "pack.json" in str(ei.value) and "line 2" in str(ei.value)


def test_duplicate_object_key_across_files(tmp_path):
    src = _write_pack(tmp_path)
    (src / "extra.json").write_text(json.dumps({"pack": {"id": "x", "name": "x", "stats": [{"id": "a", "label": "A"}]}}))
    with pytest.raises(ContentError) as ei:
        merge_pack_files(src)
    assert "already defined" in str(ei.value)


def test_extra_field_rejected(tmp_path):
    src = _write_pack(tmp_path, playbooks=[{"id": "pb", "name": "PB", "hp_max": 10, "bogus": 1}])
    with pytest.raises(ContentError) as ei:
        load_content(src)
    assert "bogus" in str(ei.value)


def test_unknown_top_level_key(tmp_path):
    src = tmp_path / "pack"
    src.mkdir()
    src.joinpath("all.json").write_text(json.dumps({
        "pack": {"id": "t", "name": "T", "stats": [{"id": "str", "label": "STR"}]},
        "town_sheet": {"name": "Home"},
    }))
    with pytest.raises(ContentError) as ei:
        load_content(src)
    assert "unknown top-level key 'town_sheet'" in str(ei.value)


def test_shared_sheet_validation(tmp_path):
    src = _write_pack(tmp_path, shared_sheets=[{"id": "a", "sizes": ["x"], "size_start": "y"}, {"id": "a"}])
    with pytest.raises(ContentError) as ei:
        load_content(src)
    msg = str(ei.value)
    assert "duplicate template ids" in msg and "size_start" in msg


def test_example_pack_has_gm_screen(pack):
    t = pack.shared_sheet("gm_screen")
    assert t.visibility == "gm" and not t.auto_create
    assert any(c.type == "dice" for c in t.sections[0].columns)


def test_nested_options_and_write_ins(tmp_path):
    src = _write_pack(tmp_path, playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "sections": [{
            "id": "kit", "title": "Kit", "type": "multichoose", "options": [
                {"id": "weapons", "label": "Weapons", "max": 2, "options": [
                    {"id": "sword", "label": "Sword", "tracks": {"bulk": 1}},
                    {"id": "axe", "label": "Axe", "tracks": {"bulk": 1}},
                    {"id": "other", "label": "Other", "write_in": "what is it?"},
                ]},
                {"id": "plain", "label": "Plain"},
            ],
        }],
    }])
    pack = load_content(src)
    weapons = pack.playbooks[0].sections[0].options[0]
    assert weapons.max == 2 and [o.id for o in weapons.options] == ["sword", "axe", "other"]
    assert weapons.options[-1].write_in == "what is it?"
    assert weapons.options[0].write_in is None


def test_nested_option_ids_must_be_unique_within_a_section(tmp_path):
    src = _write_pack(tmp_path, playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "sections": [{"id": "kit", "title": "Kit", "type": "multichoose", "options": [
            {"id": "sword", "label": "Sword"},
            {"id": "weapons", "label": "Weapons", "options": [{"id": "sword", "label": "Dup"}]},
        ]}],
    }])
    with pytest.raises(ContentError) as ei:
        load_content(src)
    assert "duplicate option id 'sword'" in str(ei.value)


def test_nested_option_bounds_are_checked(tmp_path):
    src = _write_pack(tmp_path, playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "sections": [{"id": "kit", "title": "Kit", "type": "multichoose", "options": [
            {"id": "weapons", "label": "Weapons", "max": 4, "options": [{"id": "sword", "label": "Sword"}]},
        ]}],
    }])
    with pytest.raises(ContentError) as ei:
        load_content(src)
    assert "max exceeds the number of nested options" in str(ei.value)

    (tmp_path / "b").mkdir()
    src2 = _write_pack(tmp_path / "b", playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "sections": [{"id": "kit", "title": "Kit", "type": "multichoose", "options": [{"id": "a", "label": "A", "min": 1}]}],
    }])
    with pytest.raises(ContentError) as ei:
        load_content(src2)
    assert "min/max only apply to a nested sub-choice" in str(ei.value)


def test_nested_option_effects_are_validated(tmp_path):
    src = _write_pack(tmp_path, playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "sections": [{"id": "kit", "title": "Kit", "type": "choose", "options": [
            {"id": "parent", "label": "Parent", "options": [
                {"id": "child", "label": "Child", "effects": {"moves": ["nope"]}},
            ]},
        ]}],
    }])
    with pytest.raises(ContentError) as ei:
        load_content(src)
    assert "unknown move 'nope'" in str(ei.value)


def _load(tmp_path, name, **overrides):
    """Write a one-off pack under its own directory and load it."""
    root = tmp_path / name
    root.mkdir(parents=True)
    return load_content(_write_pack(root, **overrides))


def test_note_options_are_prose_not_picks(tmp_path):
    pack = _load(tmp_path, "a", playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "sections": [{
            "id": "intro", "title": "Introductions", "type": "multichoose", "required": False,
            "options": [
                {"id": "step1", "label": "1. Introduce yourself", "note": True},
                {"id": "step4", "label": "4-5. The folk of the village", "note": True, "min": 1, "max": 2,
                 "options": [{"id": "q1", "label": "Who is your closest kin?", "write_in": "your answer"},
                             {"id": "q2", "label": "Who is your lover?", "write_in": "your answer"}]},
            ],
        }],
    }])
    sec = pack.playbooks[0].sections[0]
    assert sec.options[0].note and not sec.options[0].options
    assert sec.options[1].min == 1 and sec.options[1].max == 2


def test_a_note_cannot_be_selected_so_it_cannot_carry_effects(tmp_path):
    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "a", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "sections": [{"id": "s", "title": "S", "type": "multichoose", "options": [
                {"id": "n", "label": "N", "note": True, "effects": {"moves": []}},
            ]}],
        }])
    assert "cannot have effects" in str(ei.value)


def test_lines_sections_need_lines_and_unique_ids(tmp_path):
    pack = _load(tmp_path, "a", playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "sections": [{
            "id": "appearance", "title": "Appearance", "type": "lines",
            "lines": [{"id": "age", "write_in": "", "options": [{"id": "young", "label": "young"}]}],
        }],
    }])
    assert pack.playbooks[0].sections[0].lines[0].id == "age"

    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "b", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "sections": [{"id": "a", "title": "A", "type": "lines", "lines": [
                {"id": "age", "options": [{"id": "x", "label": "x"}]},
                {"id": "voice", "options": [{"id": "x", "label": "x"}]},
            ]}],
        }])
    assert "duplicate option id 'x'" in str(ei.value)


def test_a_lines_option_is_a_plain_label(tmp_path):
    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "a", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "sections": [{"id": "a", "title": "A", "type": "lines", "lines": [
                {"id": "age", "options": [{"id": "x", "label": "x", "tracks": {"uses": 2}}]},
            ]}],
        }])
    assert "plain labels" in str(ei.value)


def test_section_start_must_fit_the_section(tmp_path):
    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "a", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "sections": [{"id": "s", "title": "S", "type": "multichoose",
                          "options": [{"id": "a", "label": "A"}], "start": ["nope"]}],
        }])
    assert "unknown option 'nope'" in str(ei.value)

    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "b", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "sections": [{"id": "s", "title": "S", "type": "table",
                          "columns": [{"id": "c", "label": "C"}], "start": [{"nope": 1}]}],
        }])
    assert "unknown column 'nope'" in str(ei.value)


def test_inserts_are_first_class(tmp_path):
    pack = _load(
        tmp_path, "a",
        inserts=[{
            "id": "ghost", "name": "Ghost",
            "starting_moves": {"fixed": ["unliving"]},
            "moves": [{"id": "unliving", "name": "Unliving"}],
            "sections": [{"id": "ghost_instinct", "title": "Instinct", "type": "choose",
                          "options": [{"id": "denial", "label": "Denial"}]}],
        }],
        playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10, "inserts": ["gear", "ghost"],
            "moves": [{"id": "haunt", "name": "Haunt", "insert": "ghost"}],
        }],
    )
    assert pack.insert("ghost").starting_moves.fixed == ["unliving"]
    assert "unliving" in pack.all_moves()
    assert [s.id for s in pack.sections_for("pb")] == ["ghost_instinct"]


def test_unknown_insert_references_are_reported(tmp_path):
    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "a", playbooks=[{"id": "pb", "name": "PB", "hp_max": 10, "inserts": ["nope"]}])
    assert "unknown insert 'nope'" in str(ei.value)

    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "b", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "moves": [{"id": "m", "name": "M", "insert": "nope"}],
        }])
    assert "unknown insert 'nope'" in str(ei.value)


def test_an_insert_section_id_may_not_clash_with_a_playbook_it_can_join(tmp_path):
    with pytest.raises(ContentError) as ei:
        _load(
            tmp_path, "a",
            inserts=[{"id": "ins", "name": "Ins", "sections": [
                {"id": "instinct", "title": "Instinct", "type": "choose",
                 "options": [{"id": "a", "label": "A"}]}]}],
            playbooks=[{"id": "pb", "name": "PB", "hp_max": 10, "sections": [
                {"id": "instinct", "title": "Instinct", "type": "choose",
                 "options": [{"id": "b", "label": "B"}]}]}],
        )
    assert "clashes with inserts[ins]" in str(ei.value)


def test_boxes_are_declared_by_kind(tmp_path):
    pack = _load(tmp_path, "a", playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "moves": [{"id": "blades", "name": "Blades", "tracks": {"statuses": ["a few left", "out"]}}],
        "sections": [{"id": "kit", "title": "Kit", "type": "multichoose", "options": [
            {"id": "crossbow", "label": "Crossbow", "tracks": {"bulk": 1, "statuses": ["low ammo", "all out"]}},
            {"id": "whisky", "label": "Whisky", "tracks": {"uses": 2}},
            {"id": "progress", "label": "Progress", "tracks": {"marks": 3}},
            {"id": "plain", "label": "Plain"},
        ]}],
    }])
    by_id = {o.id: o for o in pack.playbooks[0].sections[0].all_options()}
    assert by_id["crossbow"].tracks.kinds() == {"bulk": 1, "statuses": 2}
    assert by_id["whisky"].tracks.kinds() == {"uses": 2}
    assert by_id["progress"].tracks.kinds() == {"marks": 3}
    assert by_id["plain"].tracks.any() is False
    assert pack.playbooks[0].moves[0].tracks.statuses == ["a few left", "out"]


def test_outcomes_take_plain_text_or_actions(tmp_path):
    pack = _load(tmp_path, "a", playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "moves": [{"id": "m", "name": "M", "roll": {"stat": "str"}, "outcomes": {
            "10+": "Plain markdown.",
            "7-9": {"text": "Hold 1.", "apply": [{"kind": "hold", "name": "Guard", "n": 1}]},
            "6-": {"text": "No XP here.", "mark_xp": False},
        }}],
    }])
    outcomes = pack.playbooks[0].moves[0].outcomes
    assert outcomes["10+"].text == "Plain markdown." and outcomes["10+"].apply == []
    assert outcomes["7-9"].apply[0].name == "Guard"
    assert outcomes["6-"].mark_xp is False


def test_outcome_actions_are_checked_against_the_pack(tmp_path):
    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "a", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "moves": [{"id": "m", "name": "M", "outcomes": {
                "6-": {"text": "x", "apply": [{"kind": "hp", "amount": "not dice"}]}}}],
        }])
    assert "amount" in str(ei.value)

    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "b", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "moves": [{"id": "m", "name": "M", "outcomes": {
                "6-": {"text": "x", "apply": [{"kind": "sheet_debility", "id": "hungry"}]}}}],
        }])
    assert "shared-sheet move" in str(ei.value)


def test_a_grant_names_other_playbooks(tmp_path):
    pack = _load(tmp_path, "a", playbooks=[
        {"id": "pb", "name": "PB", "hp_max": 10, "moves": [
            {"id": "borrow", "name": "Borrow", "tags": ["multiclass"],
             "grants": {"from_playbooks": ["other"], "n": 1, "exclude_tags": ["stat"]}}]},
        {"id": "other", "name": "Other", "hp_max": 10, "moves": [
            {"id": "theirs", "name": "Theirs"}, {"id": "their_stat", "name": "Stat", "tags": ["stat"]}]},
    ])
    grant = pack.playbooks[0].moves[0].grants
    assert grant.from_playbooks == ["other"] and grant.exclude_tags == ["stat"]

    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "b", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "moves": [{"id": "m", "name": "M", "grants": {"from_playbooks": ["pb"]}}]}])
    assert "own playbook" in str(ei.value)


def test_a_move_can_carry_its_own_checklist(tmp_path):
    pack = _load(tmp_path, "a", playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "moves": [{
            "id": "veteran", "name": "Veteran", "text": "Each time you take this move, pick 1.",
            "min": 1, "max": 1,
            "options": [
                {"id": "tags", "label": "Two new tags"},
                {"id": "tougher", "label": "+2 max HP each", "tracks": {"marks": 2}},
                {"id": "knack", "label": "Some knack", "write_in": "which knack"},
            ],
        }],
    }])
    move = pack.playbooks[0].moves[0]
    assert [o.id for o in move.options] == ["tags", "tougher", "knack"]
    assert move.min == 1 and move.max == 1
    assert move.options[1].tracks.kinds() == {"marks": 2}


def test_move_option_bounds_and_ids_are_checked(tmp_path):
    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "a", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "moves": [{"id": "m", "name": "M", "max": 3, "options": [{"id": "x", "label": "x"}]}]}])
    assert "max exceeds the number of options" in str(ei.value)

    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "b", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10, "moves": [{"id": "m", "name": "M", "max": 1}]}])
    assert "min/max only apply" in str(ei.value)

    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "c", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10, "moves": [{"id": "m", "name": "M", "options": [
                {"id": "x", "label": "x"}, {"id": "x", "label": "again"}]}]}])
    assert "duplicate option id 'x'" in str(ei.value)


def test_a_moves_options_cannot_carry_effects(tmp_path):
    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "a", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10, "moves": [{"id": "m", "name": "M", "options": [
                {"id": "x", "label": "x", "effects": {"armor": 1}}]}]}])
    assert "cannot carry effects" in str(ei.value)


def test_a_move_with_options_may_not_be_named_after_a_section(tmp_path):
    with pytest.raises(ContentError) as ei:
        _load(tmp_path, "a", playbooks=[{
            "id": "pb", "name": "PB", "hp_max": 10,
            "sections": [{"id": "clash", "title": "Clash", "type": "text"}],
            "moves": [{"id": "clash", "name": "Clash", "options": [{"id": "x", "label": "x"}]}],
        }])
    assert "already a section id" in str(ei.value)

    # Only a move that carries options shares the namespace, so a plain move may keep the name.
    pack = _load(tmp_path, "b", playbooks=[{
        "id": "pb", "name": "PB", "hp_max": 10,
        "sections": [{"id": "clash", "title": "Clash", "type": "text"}],
        "moves": [{"id": "clash", "name": "Clash"}],
    }])
    assert pack.playbooks[0].moves[0].id == "clash"


def test_table_column_called_id_rejected(tmp_path):
    src = _write_pack(tmp_path, playbooks=[{"id": "pb", "name": "PB", "hp_max": 10, "sections": [
        {"id": "crew", "title": "Crew", "type": "table", "columns": [{"id": "id", "label": "Id"}]}]}])
    with pytest.raises(ContentError, match="no column may be called 'id'"):
        load_content(src)
