import pytest

from st_vtt.config import UserConfig
from st_vtt.perms import Forbidden, check_patch, strip_for_user, visible_to

gm = UserConfig(name="Gm", role="gm")
alice = UserConfig(name="Alice")
bob = UserConfig(name="Bob")


def test_owner_and_gm_can_edit_character():
    check_patch(alice, "character", "Alice", "/hp/current")
    check_patch(gm, "character", "Alice", "/hp/current")
    with pytest.raises(Forbidden):
        check_patch(bob, "character", "Alice", "/hp/current")


def test_gm_notes_gm_only():
    with pytest.raises(Forbidden):
        check_patch(alice, "character", "Alice", "/gm_notes")
    check_patch(gm, "character", "Alice", "/gm_notes")


def test_anyone_edits_shared_but_not_gm_notes():
    check_patch(bob, "shared", None, "/stats/luck")
    with pytest.raises(Forbidden):
        check_patch(bob, "shared", None, "/gm_notes")
    with pytest.raises(Forbidden):
        check_patch(bob, "shared", None, "/notes", gm_only=True)
    check_patch(gm, "shared", None, "/notes", gm_only=True)


def test_immutable_and_root():
    with pytest.raises(Forbidden):
        check_patch(gm, "character", "Alice", "/playbook")
    with pytest.raises(Forbidden):
        check_patch(gm, "character", "Alice", "")


def test_shared_sheet_template_is_fixed():
    # The sheet renders by data.template; a player changing it broke the sheet for everyone.
    for user in (bob, gm):
        with pytest.raises(Forbidden):
            check_patch(user, "shared", None, "/template")


def test_visibility_and_strip():
    assert visible_to(alice, None)
    assert visible_to(alice, ["Alice"])
    assert not visible_to(bob, ["Alice"])
    assert visible_to(gm, ["Alice"])
    assert "gm_notes" not in strip_for_user(alice, "character", {"gm_notes": "x", "notes": "y"})
    assert "gm_notes" in strip_for_user(gm, "character", {"gm_notes": "x"})
