import pytest

from st_vtt import dice


def seq(*values):
    it = iter(values)
    return lambda a, b: next(it)


def test_simple_sum():
    r = dice.roll("2d6+1", rng=seq(3, 4))
    assert r.total == 8
    assert r.modifier == 1
    assert r.groups[0].results == [3, 4]


def test_keep_highest_and_lowest():
    r = dice.roll("3d6kh2", rng=seq(1, 6, 4))
    assert r.groups[0].kept == [6, 4] and r.total == 10
    r = dice.roll("3d6kl2", rng=seq(1, 6, 4))
    assert r.groups[0].kept == [1, 4] and r.total == 5


def test_bare_d_and_negative_terms():
    r = dice.roll("d8 - 2 + 1d4", rng=seq(5, 2))
    assert r.total == 5
    r = dice.roll("-1d4+10", rng=seq(3))
    assert r.total == 7


def test_refs_expand():
    r = dice.roll("{damage_die}+{str}", refs={"damage_die": "1d10", "str": 2}, rng=seq(7))
    assert r.total == 9
    with pytest.raises(dice.DiceError):
        dice.roll("{nope}")


@pytest.mark.parametrize("bad", ["", "2d", "d6+", "+", "2d6 3", "2d6kh3", "0d6", "1d0", "abc", "2d6++1"])
def test_bad_expressions(bad):
    with pytest.raises(dice.DiceError):
        dice.parse(bad)


def test_real_rng_bounds():
    for _ in range(50):
        r = dice.roll("2d6")
        assert 2 <= r.total <= 12


@pytest.mark.parametrize(
    "bad",
    [
        "1" * 5000,  # past Python's limit on digits, which raised a ValueError, not a DiceError
        "+".join(["100d6"] * 2),  # each group in bounds, too many dice all told
        "{a}+{a}",  # ...or once references are expanded
    ],
)
def test_size_limits_are_dice_errors(bad):
    with pytest.raises(dice.DiceError):
        dice.roll(bad, refs={"a": "60d6"})
