"""Generate the paper theme's ink textures as tileable SVG data URIs.

The official sheets are printed with heavy strokes that did not take ink evenly:
the bars under headings are eaten away along their bottom edge, and the stat
boxes are chipped all round, with the odd speck knocked out of the middle. Thin
rules, by contrast, are clean -- so only heavy strokes get any of this.

Deterministic (seeded): the texture is baked into the stylesheet, not computed
in the browser, so there is nothing to run at render time and no filter cost.
"""
import random
from urllib.parse import quote

INK = "#17150f"


def bites(rng, width, edge_y, depth, step, run):
    """White polygons eating into an edge, in blocky steps like a worn plate."""
    out = []
    x = 8.0  # leave the tile's seams solid so repeats do not show
    while x < width - 10:
        w = rng.uniform(step * 0.5, step * 1.4)
        d = rng.uniform(depth * 0.2, depth)
        if rng.random() < 0.55:
            # a square notch
            out.append(f'<rect x="{x:.1f}" y="{edge_y - d:.1f}" width="{w:.1f}" height="{d + 1:.1f}"/>')
        else:
            # a ragged wedge
            out.append(
                f'<path d="M{x:.1f},{edge_y + 1:.1f} L{x:.1f},{edge_y - d:.1f} '
                f'L{x + w * 0.5:.1f},{edge_y - d * rng.uniform(0.3, 1.0):.1f} '
                f'L{x + w:.1f},{edge_y + 1:.1f} Z"/>'
            )
        x += w + rng.uniform(run, run * 3.2)
    return out


def specks(rng, width, height, n, size):
    out = []
    for _ in range(n):
        x, y = rng.uniform(2, width - 2), rng.uniform(0.4, height - 0.6)
        s = rng.uniform(size * 0.4, size)
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s * rng.uniform(0.6, 1.4):.1f}"/>')
    return out


def rule_tile(seed, width=320.0, bar=3.2, height=4.4):
    """A heavy heading bar, worn along its underside."""
    rng = random.Random(seed)
    # Depth caps at a third of the bar: the ink thins there, it never breaks.
    white = bites(rng, width, bar, 1.2, 4.0, 11.0) + specks(rng, width, bar, 9, 0.7)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
        f'viewBox="0 0 {width:g} {height:g}">'
        f'<rect width="{width:g}" height="{bar:g}" fill="{INK}"/>'
        f'<g fill="#fff">{"".join(white)}</g>'
        f"</svg>"
    )


def box_tile(seed, size=32.0, stroke=5.0, chamfer=8.0):
    """A chipped outline with chamfered corners, for border-image (9-slice).

    Avara is drawn on a square grid and the sheets' boxes follow it: the corners
    are bevelled, never truly round.
    """
    rng = random.Random(seed)
    s, c, h = stroke / 2, chamfer, size
    path = (
        f"M{c:.1f},{s:.1f} L{h - c:.1f},{s:.1f} L{h - s:.1f},{c:.1f} "
        f"L{h - s:.1f},{h - c:.1f} L{h - c:.1f},{h - s:.1f} L{c:.1f},{h - s:.1f} "
        f"L{s:.1f},{h - c:.1f} L{s:.1f},{c:.1f} Z"
    )
    chips = []
    for _ in range(22):
        # Knock chips off wherever the stroke runs, biased to the edges.
        side = rng.choice("tblr")
        along = rng.uniform(c * 0.4, h - c * 0.4)
        w, d = rng.uniform(1.0, 3.0), rng.uniform(0.9, 2.3)
        if side == "t":
            chips.append(f'<rect x="{along:.1f}" y="{-0.2:.1f}" width="{w:.1f}" height="{d:.1f}"/>')
        elif side == "b":
            chips.append(f'<rect x="{along:.1f}" y="{h - d + 0.2:.1f}" width="{w:.1f}" height="{d:.1f}"/>')
        elif side == "l":
            chips.append(f'<rect x="{-0.2:.1f}" y="{along:.1f}" width="{d:.1f}" height="{w:.1f}"/>')
        else:
            chips.append(f'<rect x="{h - d + 0.2:.1f}" y="{along:.1f}" width="{d:.1f}" height="{w:.1f}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{h:g}" height="{h:g}" viewBox="0 0 {h:g} {h:g}">'
        f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="{stroke:g}"/>'
        f'<g fill="#fff">{"".join(chips)}</g>'
        f"</svg>"
    )


if __name__ == "__main__":
    from pathlib import Path

    here = Path(__file__).parent
    (here / "ink-rule.svg").write_text(rule_tile(7))
    (here / "ink-rule-alt.svg").write_text(rule_tile(23))
    (here / "ink-box.svg").write_text(box_tile(11))
    print("wrote ink-rule.svg, ink-rule-alt.svg, ink-box.svg")
