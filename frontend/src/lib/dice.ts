// The server sends a die group's results and the values it kept, not which dice
// those were. With ties a value can be both kept and dropped -- 3d6kl2 rolling
// [5, 5, 3] keeps [3, 5] -- so each kept value accounts for one die only.

/** Which of `results` were kept: each value in `kept` claims the first unclaimed die. */
export function keptMask(results: number[], kept: number[]): boolean[] {
  const left = [...kept];
  return results.map((r) => {
    const i = left.indexOf(r);
    if (i < 0) return false;
    left.splice(i, 1);
    return true;
  });
}
