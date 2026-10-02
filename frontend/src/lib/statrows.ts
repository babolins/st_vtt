// How a row of stat boxes wraps: evenly, not greedily.
//
// Greedy wrapping fills each row and leaves the rest for the last one -- six
// stats where five fit come out 5 + 1. Here the number of rows is whatever the
// width forces, and the stats are spread across them so rows differ by at most
// one box, fuller rows first: 3 + 3, 3 + 2, 3 + 2 + 2. Every box is the same
// width, and a shorter row is centred under the ones above it.
//
// The one lone box left is unavoidable: an odd number of stats where only two
// fit a row (2 + 2 + 1). It is centred like any other short row.

/** Row sizes for `n` boxes when at most `fit` fit on a row, fuller rows first. */
export function balancedRows(n: number, fit: number): number[] {
  if (n <= 0) return [];
  const perRow = Math.max(1, Math.min(Math.floor(fit), n));
  const rows = Math.ceil(n / perRow);
  const base = Math.floor(n / rows);
  const fuller = n % rows;
  return Array.from({ length: rows }, (_, i) => base + (i < fuller ? 1 : 0));
}

export interface Placement {
  /** 1-based grid row. */
  row: number;
  /** 1-based start line on a grid of half-box tracks; each box spans two. */
  column: number;
}

/**
 * Where each box goes on a grid of `2 * rows[0]` half-box tracks. A box spans
 * two tracks, so a row one box short starts one track in and sits centred.
 */
export function placements(rows: number[]): Placement[] {
  const cols = rows[0] ?? 0;
  return rows.flatMap((size, r) =>
    Array.from({ length: size }, (_, i) => ({ row: r + 1, column: 1 + (cols - size) + 2 * i })),
  );
}

// Within this of a fit is a fit: float sums of fractional widths land a hair
// either side of an exact one.
const SLACK = 0.01;

/**
 * How many boxes at least `box` px wide fit a `width` px row with `gap` px
 * between them, or null until the row and a box have been measured. Widths
 * are fractional: whole-pixel sums can come out a box too many.
 */
export function fitCount(width: number, box: number, gap: number): number | null {
  if (width <= 0 || box <= 0) return null;
  return Math.max(0, Math.floor((width + gap + SLACK) / (box + gap)));
}
