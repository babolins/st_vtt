import pytest

from st_vtt.patch import PatchError, apply_patch, get_pointer


def test_set_nested_creates_intermediates():
    d = {}
    apply_patch(d, "/moves/pips/x", 2)
    assert d == {"moves": {"pips": {"x": 2}}}


def test_list_append_and_index():
    d = {"items": []}
    apply_patch(d, "/items/-", {"n": 1})
    apply_patch(d, "/items/-", {"n": 2})
    apply_patch(d, "/items/0/n", 9)
    assert [i["n"] for i in d["items"]] == [9, 2]
    apply_patch(d, "/items/0", op="remove")
    assert d["items"] == [{"n": 2}]
    with pytest.raises(PatchError):
        apply_patch(d, "/items/5", 1)


def test_escapes_and_get():
    d = {"a/b": {"~": 1}}
    assert get_pointer(d, "/a~1b/~0") == 1


def test_remove_missing_key():
    with pytest.raises(PatchError):
        apply_patch({"a": 1}, "/b", op="remove")


def test_bad_pointer():
    with pytest.raises(PatchError):
        apply_patch({}, "a/b", 1)


def test_list_ops_idempotent():
    d = {}
    apply_patch(d, "/moves/taken", "a", "list_add")
    apply_patch(d, "/moves/taken", "a", "list_add")
    apply_patch(d, "/moves/taken", "b", "list_add")
    assert d["moves"]["taken"] == ["a", "b"]
    apply_patch(d, "/moves/taken", "a", "list_remove")
    apply_patch(d, "/moves/taken", "zzz", "list_remove")
    assert d["moves"]["taken"] == ["b"]
    with pytest.raises(PatchError):
        apply_patch({"x": 1}, "/x", "a", "list_add")


def test_text_patch_merges_concurrent_edits():
    from diff_match_patch import diff_match_patch

    dmp = diff_match_patch()
    base = "The mill burned.\nOld Mab is missing."
    a = "The mill burned last night.\nOld Mab is missing."
    b = "The mill burned.\nOld Mab is missing. Bryn went looking."
    doc = {"notes": base}
    pa = dmp.patch_toText(dmp.patch_make(base, a))
    pb = dmp.patch_toText(dmp.patch_make(base, b))
    apply_patch(doc, "/notes", op="text_patch", patch=pa)
    merged = apply_patch(doc, "/notes", op="text_patch", patch=pb)
    assert merged == "The mill burned last night.\nOld Mab is missing. Bryn went looking."
    assert doc["notes"] == merged
    # patching a missing field starts from ""
    d2 = {}
    apply_patch(d2, "/notes", op="text_patch", patch=dmp.patch_toText(dmp.patch_make("", "hi")))
    assert d2["notes"] == "hi"
    with pytest.raises(PatchError):
        apply_patch({"n": 3}, "/n", op="text_patch", patch=pa)


def _gear():
    return {"items": [{"id": "a", "name": "rope"}, {"id": "b", "name": "lamp"}, {"id": "c", "name": "axe"}]}


def test_id_token_selects_by_id():
    d = _gear()
    assert get_pointer(d, "/items/@b/name") == "lamp"
    apply_patch(d, "/items/@c/name", "hatchet")
    apply_patch(d, "/items/@b", {"id": "b", "name": "lantern"})
    assert [i["name"] for i in d["items"]] == ["rope", "lantern", "hatchet"]


def test_id_token_survives_a_delete_above():
    d = _gear()
    apply_patch(d, "/items/@a", op="remove")
    apply_patch(d, "/items/@c/name", "hatchet")
    assert d["items"] == [{"id": "b", "name": "lamp"}, {"id": "c", "name": "hatchet"}]


def test_append_then_address_by_id():
    d = _gear()
    apply_patch(d, "/items/-", {"id": "d", "name": ""})
    apply_patch(d, "/items/@d/name", "salt")
    assert d["items"][-1] == {"id": "d", "name": "salt"}


def test_removing_a_missing_id_does_nothing():
    d = _gear()
    apply_patch(d, "/items/@b", op="remove")
    assert apply_patch(d, "/items/@b", op="remove") is None
    assert [i["id"] for i in d["items"]] == ["a", "c"]
    # nor does removing something inside an item that is gone
    d = {"followers": [{"id": "f", "members": [{"id": "m"}]}]}
    apply_patch(d, "/followers/@f", op="remove")
    apply_patch(d, "/followers/@f/members/@m", op="remove")
    assert d == {"followers": []}


def test_setting_under_a_missing_id_is_an_error():
    d = _gear()
    before = _gear()
    for path in ("/items/@zzz/name", "/items/@zzz", "/missing/@zzz/name"):
        with pytest.raises(PatchError):
            apply_patch(d, path, "x")
    with pytest.raises(PatchError):
        get_pointer(d, "/items/@zzz")
    assert d == before


def test_text_patch_under_a_missing_id_is_an_error():
    from diff_match_patch import diff_match_patch

    dmp = diff_match_patch()
    d = _gear()
    with pytest.raises(PatchError):
        apply_patch(d, "/items/@zzz/name", op="text_patch", patch=dmp.patch_toText(dmp.patch_make("", "hi")))
    assert d == _gear()


def test_id_token_is_a_plain_key_in_an_object():
    d = {"m": {"@x": 1}}
    assert get_pointer(d, "/m/@x") == 1
    apply_patch(d, "/m/@y", 2)
    assert d == {"m": {"@x": 1, "@y": 2}}
