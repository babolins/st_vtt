import re

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


def _doc():
    return {"items": [{"id": "a", "n": 1}], "n": 3, "notes": "hi"}


@pytest.mark.parametrize(
    ("path", "kwargs", "message"),
    [
        ("", {"op": "remove"}, "cannot remove root"),
        ("", {"value": ["not", "an", "object"]}, "root replacement must be an object"),
        ("/n", {"value": 4, "op": "replace"}, "unknown op 'replace'"),
        ("/notes", {"op": "text_patch"}, "text_patch needs a patch"),
        ("/notes", {"op": "text_patch", "patch": "garbage"}, "bad text patch: Invalid patch string: garbage"),
        ("/items/-", {"op": "remove"}, "'-' only valid when appending"),
        ("/items/-/n", {"value": 2}, "'-' only valid when appending"),
        ("/items/first", {"value": 2}, "bad list index 'first'"),
        ("/items/-1", {"value": 2}, "list index out of range: -1"),
        ("/items/1", {"op": "remove"}, "list index out of range: 1"),
        ("/missing", {"op": "remove"}, "missing key 'missing'"),
        ("/missing/x", {"op": "remove"}, "missing key 'missing'"),
        ("/n/x/y", {"value": 2}, "cannot descend into scalar at 'x'"),
        ("/n/x", {"value": 2}, "cannot set 'x' on a scalar"),
        ("/n/x", {"op": "remove"}, "cannot set 'x' on a scalar"),
    ],
)
def test_apply_patch_refuses(path, kwargs, message):
    d = _doc()
    with pytest.raises(PatchError, match=re.escape(message)):
        apply_patch(d, path, **kwargs)
    assert d == _doc()


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/items/-", "'-' only valid when appending"),
        ("/items/first", "bad list index 'first'"),
        ("/items/1", "list index out of range: 1"),
        ("/n/x", "cannot descend into scalar at 'x'"),
        ("n", "pointer must start with '/'"),
    ],
)
def test_get_pointer_refuses(path, message):
    with pytest.raises(PatchError, match=re.escape(message)):
        get_pointer(_doc(), path)


def test_the_empty_pointer_is_the_root():
    d = _doc()
    assert get_pointer(d, "") is d
    assert apply_patch(d, "", {"name": "Bryn"}) is d
    assert d == {"name": "Bryn"}


def test_remove_a_key():
    d = {"moves": {"hold": {"Focus": 2, "Luck": 1}}}
    assert apply_patch(d, "/moves/hold/Focus", op="remove") is None
    assert d == {"moves": {"hold": {"Luck": 1}}}


@pytest.mark.parametrize("path", ["/__proto__/x", "/constructor/prototype/x", "/a/prototype"])
def test_refuses_names_a_browser_would_follow_into_object_prototype(path):
    # Harmless keys to Python, but the patch is broadcast, and a browser applying it would
    # walk into Object.prototype and change every object in the app.
    with pytest.raises(PatchError, match="reserved"):
        apply_patch({"a": {}}, path, "x")
