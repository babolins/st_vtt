import { describe, expect, it } from 'vitest';
import { balancedRows, placements } from './statrows';

describe('balancedRows', () => {
  it.each([
    [6, 5, [3, 3]],
    [6, 4, [3, 3]],
    [5, 4, [3, 2]],
    [7, 5, [4, 3]],
    [7, 3, [3, 2, 2]],
    [8, 3, [3, 3, 2]],
    [4, 3, [2, 2]],
  ])('%i stats where %i fit: %j', (n, fit, rows) => {
    expect(balancedRows(n, fit)).toEqual(rows);
  });

  it('keeps one row when everything fits', () => {
    expect(balancedRows(6, 6)).toEqual([6]);
    expect(balancedRows(6, 11)).toEqual([6]);
  });

  it('puts fuller rows first', () => {
    for (let n = 1; n <= 12; n++) {
      for (let fit = 1; fit <= n; fit++) {
        const rows = balancedRows(n, fit);
        expect(rows.reduce((a, b) => a + b, 0)).toBe(n);
        expect(Math.max(...rows)).toBeLessThanOrEqual(fit);
        expect(Math.max(...rows) - Math.min(...rows)).toBeLessThanOrEqual(1);
        expect([...rows].sort((a, b) => b - a)).toEqual(rows);
      }
    }
  });

  it('leaves a box alone only where no layout can avoid it', () => {
    // Odd counts two to a row, and a single column.
    expect(balancedRows(5, 2)).toEqual([2, 2, 1]);
    expect(balancedRows(3, 1)).toEqual([1, 1, 1]);
    for (let n = 2; n <= 12; n++) {
      for (let fit = 3; fit <= n; fit++) expect(balancedRows(n, fit)).not.toContain(1);
    }
  });

  it('handles nothing, and a width too narrow for even one box', () => {
    expect(balancedRows(0, 4)).toEqual([]);
    expect(balancedRows(3, 0)).toEqual([1, 1, 1]);
  });
});

describe('placements', () => {
  it('spans each box over two half-tracks, left to right', () => {
    expect(placements([3])).toEqual([
      { row: 1, column: 1 }, { row: 1, column: 3 }, { row: 1, column: 5 },
    ]);
  });

  it('starts a row one box short one half-track in, so it is centred', () => {
    expect(placements([3, 2]).slice(3)).toEqual([{ row: 2, column: 2 }, { row: 2, column: 4 }]);
    // The lone box of 2 + 2 + 1 sits in the middle of four half-tracks.
    expect(placements([2, 2, 1])[4]).toEqual({ row: 3, column: 2 });
  });
});
