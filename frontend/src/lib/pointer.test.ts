import { describe, expect, it } from 'vitest';
import { applyPointer, at, getPointer } from './pointer';

// Mirrors the id-token cases in tests/test_patch.py.

const gear = () => ({
  items: [
    { id: 'a', name: 'rope' },
    { id: 'b', name: 'lamp' },
    { id: 'c', name: 'axe' },
  ],
});

describe('@id tokens', () => {
  it('select by id', () => {
    const d = gear();
    expect(getPointer(d, '/items/@b/name')).toBe('lamp');
    applyPointer(d, '/items/@c/name', 'hatchet');
    applyPointer(d, '/items/@b', { id: 'b', name: 'lantern' });
    expect(d.items.map((i) => i.name)).toEqual(['rope', 'lantern', 'hatchet']);
  });

  it('survive a delete above', () => {
    const d = gear();
    applyPointer(d, '/items/@a', null, 'remove');
    applyPointer(d, '/items/@c/name', 'hatchet');
    expect(d.items).toEqual([
      { id: 'b', name: 'lamp' },
      { id: 'c', name: 'hatchet' },
    ]);
  });

  it('address an appended item', () => {
    const d = gear();
    applyPointer(d, '/items/-', { id: 'd', name: '' });
    applyPointer(d, '/items/@d/name', 'salt');
    expect(d.items.at(-1)).toEqual({ id: 'd', name: 'salt' });
  });

  it('removing a missing id does nothing', () => {
    const d = gear();
    applyPointer(d, '/items/@b', null, 'remove');
    applyPointer(d, '/items/@b', null, 'remove');
    expect(d.items.map((i) => i.id)).toEqual(['a', 'c']);
    const f = { followers: [{ id: 'f', members: [{ id: 'm' }] }] };
    applyPointer(f, '/followers/@f', null, 'remove');
    applyPointer(f, '/followers/@f/members/@m', null, 'remove');
    expect(f).toEqual({ followers: [] });
  });

  it('setting under a missing id throws and changes nothing', () => {
    const d: any = gear();
    for (const path of ['/items/@zzz/name', '/items/@zzz', '/missing/@zzz/name']) {
      expect(() => applyPointer(d, path, 'x')).toThrow();
    }
    expect(() => applyPointer(d, '/items/@zzz/name', 'x', 'text_patch')).toThrow();
    expect(d).toEqual(gear());
    expect(getPointer(d, '/items/@zzz')).toBeUndefined();
  });

  it('are a plain key in an object', () => {
    const d: any = { m: { '@x': 1 } };
    expect(getPointer(d, '/m/@x')).toBe(1);
    applyPointer(d, '/m/@y', 2);
    expect(d).toEqual({ m: { '@x': 1, '@y': 2 } });
  });

  it('at() escapes the id', () => {
    const d = { items: [{ id: 'a/b~c', n: 1 }] };
    expect(getPointer(d, `/items/${at('a/b~c')}/n`)).toBe(1);
  });
});

describe('reserved names', () => {
  it.each(['/__proto__/polluted', '/constructor/prototype/polluted', '/a/prototype'])(
    'are refused, so a patch cannot reach Object.prototype: %s',
    (path) => {
      expect(() => applyPointer({ a: {} }, path, 'yes')).toThrow(/reserved/);
      expect(({} as Record<string, unknown>).polluted).toBeUndefined();
    },
  );
});
