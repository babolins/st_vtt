import { describe, expect, it } from 'vitest';
import { search, splitMarks } from './movesearch';
import type { IndexedMove } from './moveindex';
import type { Move } from './types';

function move(name: string, trigger = '', text = '', extra: Partial<Move> = {}): Move {
  return {
    id: name.toLowerCase().replace(/\W+/g, '_'), name, trigger, text,
    roll: null, outcomes: {}, hold: null, tracks: {} as Move['tracks'],
    requires: null, themes: [], tags: [], replaces: null, insert: null, grants: null,
    options: [], min: null, max: null, ...extra,
  };
}

const entry = (m: Move, label = 'Basic moves'): IndexedMove => ({ move: m, source: { kind: 'group', id: 'basic', label } });

const clash = entry(move('Clash', 'When you fight in melee or close quarters...', '...roll +STR.'));
const makeCamp = entry(move('Make Camp', 'When you settle in to rest in an unsafe area...', 'Consume 1 use of supplies.'));
const defend = entry(move('Defend', 'When you take up a defensive stance or jump in to protect others...', 'Hold 3 Readiness.'));
const tormentsBlessing = entry(move("Torment's Blessing: Word of Torment", 'When you speak the word...', 'They suffer.'), 'Thrall');
const seekInsight = entry(move('Seek Insight', 'When you study a situation or person...', 'Ask the GM 3 questions from the list.'));
const pack = [clash, makeCamp, defend, tormentsBlessing, seekInsight];

const top = (q: string) => search(pack, q)[0]?.entry.move.name;

describe('finding a move by name', () => {
  it('prefers an exact prefix', () => {
    expect(top('def')).toBe('Defend');
  });

  it('matches initials, the way an abbreviation works', () => {
    expect(top('mkcmp')).toBe('Make Camp');
  });

  it('does not let a long name swallow any short letter sequence', () => {
    // "melee" hides inside "Tor(m)ent's B(le)ssing" as a subsequence. It used to
    // rank above Clash, whose trigger actually says the word.
    expect(top('melee')).toBe('Clash');
  });
});

describe('finding a move by what it is about', () => {
  it('finds one from words in its trigger, in any order', () => {
    expect(top('resting somewhere unsafe')).toBe('Make Camp');
  });

  it('stems lightly, so "resting" finds "rest"', () => {
    expect(top('rest unsafe')).toBe('Make Camp');
  });

  it('ignores the words every trigger contains', () => {
    // "when you" is in all of them; "defensive" is in one.
    expect(top('when you take a defensive stance')).toBe('Defend');
  });

  it('carries the line it matched, so the result explains itself', () => {
    const hit = search(pack, 'resting somewhere unsafe')[0];
    expect(hit.field).toBe('trigger');
    expect(hit.snippet.toLowerCase()).toContain('unsafe');
  });

  it('searches the body as well as the trigger', () => {
    expect(top('ask the gm 3 questions')).toBe('Seek Insight');
  });

  it('returns nothing rather than everything for a miss', () => {
    expect(search(pack, 'xylophone')).toEqual([]);
  });
});

describe('a name always beats a mention', () => {
  it('ranks the move called Defend above one that merely says "defensive"', () => {
    const hits = search(pack, 'defend');
    expect(hits[0].entry.move.name).toBe('Defend');
  });
});

describe('splitMarks', () => {
  it('splits a name into hit and non-hit runs', () => {
    expect(splitMarks('Defend', [[0, 3]])).toEqual([
      { text: 'Def', hit: true },
      { text: 'end', hit: false },
    ]);
  });

  it('leaves an unmarked name whole', () => {
    expect(splitMarks('Defend', [])).toEqual([{ text: 'Defend', hit: false }]);
  });
});
