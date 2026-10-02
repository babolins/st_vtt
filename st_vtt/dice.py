"""Dice expression parser and roller.

Grammar (whitespace ignored, case-insensitive):

    expr  := term (('+' | '-') term)*
    term  := dice | integer | ref
    dice  := [N] 'd' M [('kh' | 'kl') K]      e.g. 2d6, d8, 3d6kh2, 2d8kl1
    ref   := '{' name '}'                     resolved via the `refs` mapping;
                                              a ref may expand to a dice term
                                              ("1d8") or an integer ("2").
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Callable, Mapping

MAX_DICE = 100
MAX_SIDES = 1000


class DiceError(ValueError):
    pass


_TOKEN = re.compile(
    r"\s*(?:(?P<sign>[+-])|(?P<dice>(\d*)d(\d+)(?:(kh|kl)(\d+))?)|(?P<int>\d+)|(?P<ref>\{([^}]+)\}))",
    re.IGNORECASE,
)


@dataclass
class DieGroup:
    count: int
    sides: int
    keep: str | None = None  # "kh" | "kl"
    keep_n: int | None = None
    sign: int = 1
    results: list[int] = field(default_factory=list)
    kept: list[int] = field(default_factory=list)

    @property
    def notation(self) -> str:
        s = f"{self.count}d{self.sides}"
        if self.keep:
            s += f"{self.keep}{self.keep_n}"
        return s

    @property
    def subtotal(self) -> int:
        return self.sign * sum(self.kept)

    def to_dict(self) -> dict:
        return {
            "die": self.notation,
            "sign": self.sign,
            "results": list(self.results),
            "kept": list(self.kept),
            "subtotal": self.subtotal,
        }


@dataclass
class RollResult:
    expr: str
    groups: list[DieGroup]
    modifier: int
    total: int

    def to_dict(self) -> dict:
        return {
            "expr": self.expr,
            "dice": [g.to_dict() for g in self.groups],
            "modifier": self.modifier,
            "total": self.total,
        }


@dataclass
class _Term:
    sign: int
    dice: DieGroup | None = None
    value: int = 0


# How deep a {reference} may expand into one holding another, so one that names itself ends.
MAX_REF_DEPTH = 3


def _parse(expr: str, refs: Mapping[str, str | int] | None, depth: int = 0) -> list[_Term]:
    if depth > MAX_REF_DEPTH:
        raise DiceError("reference expansion too deep")
    refs = refs or {}
    terms: list[_Term] = []
    pos = 0
    sign = 1
    expect_term = True
    s = expr.strip()
    if not s:
        raise DiceError("empty dice expression")
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m or m.end() == pos:
            raise DiceError(f"unexpected {s[pos : pos + 8]!r} in {expr!r}")
        pos = m.end()
        if m.group("sign"):
            if expect_term and terms:
                raise DiceError(f"unexpected sign in {expr!r}")
            if expect_term:  # leading sign
                sign = -1 if m.group("sign") == "-" else 1
            else:
                sign = -1 if m.group("sign") == "-" else 1
                expect_term = True
            continue
        if not expect_term:
            raise DiceError(f"missing operator before {m.group(0).strip()!r} in {expr!r}")
        if m.group("dice"):
            count = int(m.group(3) or 1)
            sides = int(m.group(4))
            keep = (m.group(5) or "").lower() or None
            keep_n = int(m.group(6)) if m.group(6) else None
            if count < 1 or count > MAX_DICE:
                raise DiceError(f"dice count must be 1..{MAX_DICE}")
            if sides < 1 or sides > MAX_SIDES:
                raise DiceError(f"die sides must be 1..{MAX_SIDES}")
            if keep and (keep_n is None or keep_n < 1 or keep_n > count):
                raise DiceError(f"keep count must be 1..{count}")
            terms.append(_Term(sign, DieGroup(count, sides, keep, keep_n, sign)))
        elif m.group("int"):
            terms.append(_Term(sign, value=int(m.group("int"))))
        elif m.group("ref"):
            name = m.group(9).strip()
            if name not in refs:
                raise DiceError(f"unknown reference {{{name}}}")
            sub = _parse(str(refs[name]), refs, depth + 1)
            for t in sub:
                t.sign *= sign
                if t.dice:
                    t.dice.sign *= sign
            terms.extend(sub)
        sign = 1
        expect_term = False
    if expect_term:
        raise DiceError(f"dangling operator in {expr!r}")
    return terms


def parse(expr: str, refs: Mapping[str, str | int] | None = None) -> None:
    """Validate an expression without rolling. Raises DiceError."""
    _parse(expr, refs)


def roll(
    expr: str,
    refs: Mapping[str, str | int] | None = None,
    rng: Callable[[int, int], int] | None = None,
) -> RollResult:
    """Roll `expr`. `rng(a, b)` returns an int in [a, b]; defaults to random.randint."""
    rng = rng or random.randint
    terms = _parse(expr, refs)
    groups: list[DieGroup] = []
    modifier = 0
    for t in terms:
        if t.dice:
            g = t.dice
            g.results = [rng(1, g.sides) for _ in range(g.count)]
            if g.keep == "kh":
                g.kept = sorted(g.results, reverse=True)[: g.keep_n]
            elif g.keep == "kl":
                g.kept = sorted(g.results)[: g.keep_n]
            else:
                g.kept = list(g.results)
            groups.append(g)
        else:
            modifier += t.sign * t.value
    total = sum(g.subtotal for g in groups) + modifier
    return RollResult(expr=expr.strip(), groups=groups, modifier=modifier, total=total)
