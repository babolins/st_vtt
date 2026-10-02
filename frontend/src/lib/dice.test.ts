import { describe, expect, it } from 'vitest';
import { keptMask } from './dice';

describe('keptMask', () => {
  it('strikes only as many tied dice as were dropped', () => {
    // 3d6kl2 = [5, 5, 3] keeps [3, 5]: one 5 stays, the other is dropped.
    expect(keptMask([5, 5, 3], [3, 5])).toEqual([true, false, true]);
    // 3d6kh2 = [4, 4, 4] keeps [4, 4].
    expect(keptMask([4, 4, 4], [4, 4])).toEqual([true, true, false]);
  });

  it('keeps every die when nothing was dropped', () => {
    expect(keptMask([6, 2, 2], [6, 2, 2])).toEqual([true, true, true]);
  });

  it('strikes every die when none were kept', () => {
    expect(keptMask([1, 2], [])).toEqual([false, false]);
  });
});
