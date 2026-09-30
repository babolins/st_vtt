import { describe, expect, it } from 'vitest';
import { applyEcho, pathsOverlap, PatchQueue, type PatchEntry } from './sync';

function entry(ref: number, path = '/stats/fortunes', over: Partial<PatchEntry> = {}): PatchEntry {
  return {
    ref, msg: { type: 'patch', entity: 'shared', id: 'v', path, op: 'set', value: ref },
    entity: 'shared', id: 'v', path, op: 'set', value: ref, user: 'Alice', overtaken: false, ...over,
  };
}

describe('pathsOverlap', () => {
  it.each([
    ['/stats/fortunes', '/stats/fortunes', true],
    ['/stats', '/stats/fortunes', true],
    ['/stats/fortunes', '/stats', true],
    ['', '/stats/fortunes', true],
    ['/stats/fortunes', '/stats/fort', false],
    ['/stats/fort', '/stats/fortunes', false],
    ['/stats/fortunes', '/stats/stores', false],
    ['/gear/1', '/gear/10', false],
  ])('%j and %j: %s', (a, b, overlap) => {
    expect(pathsOverlap(a, b)).toBe(overlap);
  });
});

describe('applyEcho', () => {
  it('skips our own echo when nothing landed on top of it', () => {
    expect(applyEcho(entry(1), false)).toBe(false);
  });
  it('applies it when overtaken', () => {
    expect(applyEcho(entry(1, undefined, { overtaken: true }), false)).toBe(true);
  });
  it('always applies merged results', () => {
    expect(applyEcho(entry(1), true)).toBe(true);
    expect(applyEcho(undefined, true)).toBe(true);
  });
  it('skips an echo it has no record of', () => {
    expect(applyEcho(undefined, false)).toBe(false);
  });
});

describe('PatchQueue', () => {
  it('marks only in-flight patches to the same sheet and an overlapping path as overtaken', () => {
    const q = new PatchQueue();
    const same = entry(1), child = entry(2, '/stats/fortunes/x'), other = entry(3, '/stats/stores');
    const elsewhere = entry(4, '/stats/fortunes', { id: 'w' });
    const queued = entry(5);
    for (const e of [same, child, other, elsewhere]) q.sent(e);
    q.queue(queued);
    q.overtake('shared', 'v', '/stats/fortunes');
    expect([same, child, other, elsewhere, queued].map((e) => e.overtaken)).toEqual([true, true, false, false, false]);
  });

  // The failure in #24: A and B set the same field; the server applies A's then B's.
  it('converges on the server order when two clients set the same field', () => {
    const server: number[] = [];
    const shown = { a: 0, b: 0 };
    const qa = new PatchQueue(), qb = new PatchQueue();
    const pa = entry(1), pb = entry(1);
    shown.a = 1; qa.sent(pa);
    shown.b = 2; qb.sent(pb);
    server.push(1, 2);
    // A receives: its own echo, then B's patch
    if (applyEcho(qa.get(1), false)) shown.a = 1;
    qa.settle(1);
    qa.overtake('shared', 'v', '/stats/fortunes'); shown.a = 2;
    // B receives: A's patch, then its own echo
    qb.overtake('shared', 'v', '/stats/fortunes'); shown.b = 1;
    if (applyEcho(qb.get(1), false)) shown.b = 2;
    qb.settle(1);
    expect(shown).toEqual({ a: server.at(-1), b: server.at(-1) });
  });

  it('puts in-flight patches back in the outbox ahead of later ones, in ref order', () => {
    const q = new PatchQueue();
    q.sent(entry(2, undefined, { overtaken: true }));
    q.sent(entry(1));
    q.queue(entry(3));
    q.disconnected();
    q.queue(entry(4));
    expect(q.unsaved).toBe(4);
    const out = q.drain();
    expect(out.map((e) => e.ref)).toEqual([1, 2, 3, 4]);
    expect(out.every((e) => !e.overtaken)).toBe(true);
    expect(q.unsaved).toBe(0);
  });

  it('replays only what the snapshot lacks, and only as the same user', () => {
    const q = new PatchQueue();
    q.sent(entry(1));
    q.sent(entry(2));
    q.disconnected();
    q.queue(entry(3));
    q.queue(entry(4, undefined, { user: 'Bob' }));
    // the server had applied ref 1 before the socket dropped
    expect(q.rebase(1, 'Alice').map((e) => e.ref)).toEqual([2, 3]);
    expect(q.drain().map((e) => e.ref)).toEqual([2, 3]);
  });

  it('re-applies in-flight patches after a refresh while connected, without queueing them', () => {
    const q = new PatchQueue();
    q.sent(entry(5));
    q.sent(entry(6));
    expect(q.rebase(5, 'Alice').map((e) => e.ref)).toEqual([6]);
    expect(q.unsaved).toBe(0);
    expect(q.settle(6)?.ref).toBe(6);
    expect(q.get(6)).toBeUndefined();
  });
});
