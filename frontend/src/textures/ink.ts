// The paper theme's ink textures, as tileable SVGs.
//
// Heavy strokes in print do not take ink evenly: the bar under a heading is
// eaten away along its bottom edge, and the stat boxes are chipped all round,
// with the odd speck knocked out of the middle. Thin rules, by contrast, are
// clean -- so only heavy strokes get any of this.
//
// The Vite config writes these out at the start of every dev server and build
// (see `inkTextures` there), so the stylesheet references plain files and there
// is nothing to run at render time and no filter cost. Seeded, so every build
// draws the same wear.
//
// The wear is cut out of the ink with a mask rather than painted over it, so
// whatever lies under the stroke -- the sheet's own colour -- shows through.

const INK = '#17150f';
// --warn in the paper theme: a stat under a debility is boxed in this instead.
const WARN = '#86621a';

type Rng = { uniform(a: number, b: number): number; random(): number };

/** mulberry32: small, fast, and the same sequence for a seed everywhere. */
function seeded(seed: number): Rng {
  let a = seed >>> 0;
  const random = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return { random, uniform: (lo, hi) => lo + (hi - lo) * random() };
}

const f = (n: number) => n.toFixed(1);

/** Polygons eating into an edge, in blocky steps like a worn plate. */
function bites(rng: Rng, width: number, edgeY: number, depth: number, step: number, run: number): string[] {
  const out: string[] = [];
  let x = 8; // leave the tile's seams solid so repeats do not show
  while (x < width - 10) {
    const w = rng.uniform(step * 0.5, step * 1.4);
    const d = rng.uniform(depth * 0.2, depth);
    if (rng.random() < 0.55) {
      // a square notch
      out.push(`<rect x="${f(x)}" y="${f(edgeY - d)}" width="${f(w)}" height="${f(d + 1)}"/>`);
    } else {
      // a ragged wedge
      out.push(
        `<path d="M${f(x)},${f(edgeY + 1)} L${f(x)},${f(edgeY - d)} ` +
          `L${f(x + w * 0.5)},${f(edgeY - d * rng.uniform(0.3, 1.0))} ` +
          `L${f(x + w)},${f(edgeY + 1)} Z"/>`,
      );
    }
    x += w + rng.uniform(run, run * 3.2);
  }
  return out;
}

function specks(rng: Rng, width: number, height: number, n: number, size: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < n; i++) {
    const x = rng.uniform(2, width - 2);
    const y = rng.uniform(0.4, height - 0.6);
    const s = rng.uniform(size * 0.4, size);
    out.push(`<rect x="${f(x)}" y="${f(y)}" width="${f(s)}" height="${f(s * rng.uniform(0.6, 1.4))}"/>`);
  }
  return out;
}

/** A mask that keeps the ink everywhere except under `shapes`. */
function wearMask(width: number, height: number, shapes: string[]): string {
  return (
    `<mask id="wear" maskUnits="userSpaceOnUse" x="0" y="0" width="${width}" height="${height}">` +
    `<rect width="${width}" height="${height}" fill="#fff"/>` +
    `<g fill="#000">${shapes.join('')}</g>` +
    `</mask>`
  );
}

const svg = (width: number, height: number, body: string) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${body}</svg>`;

/** A heavy heading bar, worn along its underside. */
export function ruleTile(seed: number, width = 320, bar = 3.2, height = 4.4): string {
  const rng = seeded(seed);
  // Depth caps at a third of the bar: the ink thins there, it never breaks.
  // Bite deeper and the line reads as dashed rather than worn.
  const worn = [...bites(rng, width, bar, 1.2, 4.0, 11.0), ...specks(rng, width, bar, 9, 0.7)];
  const ink = `<rect width="${width}" height="${bar}" fill="${INK}" mask="url(#wear)"/>`;
  return svg(width, height, wearMask(width, height, worn) + ink);
}

/** A chipped outline with chamfered corners, for border-image (9-slice). */
export function boxTile(seed: number, ink = INK, size = 32, stroke = 5, chamfer = 8): string {
  const rng = seeded(seed);
  const s = stroke / 2, c = chamfer, h = size;
  const path =
    `M${f(c)},${f(s)} L${f(h - c)},${f(s)} L${f(h - s)},${f(c)} ` +
    `L${f(h - s)},${f(h - c)} L${f(h - c)},${f(h - s)} L${f(c)},${f(h - s)} ` +
    `L${f(s)},${f(h - c)} L${f(s)},${f(c)} Z`;
  const chips: string[] = [];
  for (let i = 0; i < 22; i++) {
    // Knock chips off wherever the stroke runs, biased to the edges.
    const side = 'tblr'[Math.floor(rng.random() * 4)];
    const along = rng.uniform(c * 0.4, h - c * 0.4);
    const w = rng.uniform(1.0, 3.0), d = rng.uniform(0.9, 2.3);
    if (side === 't') chips.push(`<rect x="${f(along)}" y="-0.2" width="${f(w)}" height="${f(d)}"/>`);
    else if (side === 'b') chips.push(`<rect x="${f(along)}" y="${f(h - d + 0.2)}" width="${f(w)}" height="${f(d)}"/>`);
    else if (side === 'l') chips.push(`<rect x="-0.2" y="${f(along)}" width="${f(d)}" height="${f(w)}"/>`);
    else chips.push(`<rect x="${f(h - d + 0.2)}" y="${f(along)}" width="${f(d)}" height="${f(w)}"/>`);
  }
  return svg(h, h, wearMask(h, h, chips) + `<path d="${path}" fill="none" stroke="${ink}" stroke-width="${stroke}" mask="url(#wear)"/>`);
}

/** Every texture the paper theme uses, by the file name app.css asks for. */
export function inkTextures(): Record<string, string> {
  return {
    'ink-rule.svg': ruleTile(7),
    'ink-rule-alt.svg': ruleTile(23),
    'ink-box.svg': boxTile(11),
    'ink-box-warn.svg': boxTile(11, WARN),
  };
}
