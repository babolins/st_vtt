import { describe, expect, it } from 'vitest';
import { requestableMoves } from './moveindex';
import type { CharacterRow, ContentPack, Move, RollSpec } from './types';

function move(name: string, stat?: RollSpec['stat']): Move {
  return {
    id: name.toLowerCase().replace(/\W+/g, '_'),
    name,
    trigger: '',
    text: '',
    roll: stat === undefined ? null : { stat, bonus: 0, label: null, modifiers: [] },
    outcomes: {},
    hold: null,
    tracks: {} as Move['tracks'],
    requires: null,
    themes: [],
    tags: [],
    replaces: null,
    insert: null,
    grants: null,
    options: [],
    min: null,
    max: null,
  };
}

function pack(parts: Partial<Record<'basic' | 'playbook' | 'insert' | 'shared', Move[]>>): ContentPack {
  return {
    moves: { basic: parts.basic ?? [] },
    playbooks: [{ id: 'heavy', name: 'The Heavy', moves: parts.playbook ?? [] }],
    inserts: [{ id: 'warband', name: 'Warband', moves: parts.insert ?? [] }],
    arcana: [],
    shared_sheets: [{ id: 'village', name: 'The Village', moves: parts.shared ?? [] }],
  } as unknown as ContentPack;
}

function character(taken: Move[], extra: { arcana?: Move[]; custom?: Move[]; inserts?: string[] } = {}): CharacterRow {
  return {
    id: 'c1',
    owner: 'Alice',
    revision: 1,
    updated_at: 0,
    data: {
      playbook: 'heavy',
      moves: { taken: [...taken, ...(extra.custom ?? [])].map((m) => m.id), tracks: {} },
      arcana: extra.arcana ? [{ id: 'horn', name: 'The Horn', moves: extra.arcana }] : [],
      custom_moves: extra.custom ?? [],
      inserts: extra.inserts ?? [],
    },
  } as unknown as CharacterRow;
}

const names = (c: ContentPack, rows: CharacterRow[] = []) => requestableMoves(c, rows).map((e) => e.move.name);

describe('requestableMoves', () => {
  const clash = move('Clash', 'str');
  const fury = move('Battle Fury', 'con');
  const cleave = move('Cleave', 'str');

  it("offers the table's moves, then the moves the player's characters have", () => {
    const c = pack({ basic: [clash], playbook: [fury, cleave] });
    expect(names(c, [character([fury])])).toEqual(['Clash', 'Battle Fury']);
  });

  it('offers only the table moves to a player with no character', () => {
    expect(names(pack({ basic: [clash], playbook: [fury] }))).toEqual(['Clash']);
  });

  it("offers a character's arcana and custom moves, which are on the sheet without being in the pack's lists", () => {
    const horn = move('Sound the Horn', 'wis');
    const trick = move('Old Trick', 'dex');
    expect(names(pack({ basic: [clash] }), [character([], { arcana: [horn], custom: [trick] })])).toEqual([
      'Clash',
      'Old Trick',
      'Sound the Horn',
    ]);
  });

  it('leaves out moves with nothing to roll', () => {
    expect(names(pack({ basic: [move('Make Camp'), clash] }))).toEqual(['Clash']);
  });

  it("leaves out a shared sheet's moves, which roll the sheet's stats and not a character's", () => {
    expect(names(pack({ basic: [clash], shared: [move('Hold Fast', 'fortunes')] }))).toEqual(['Clash']);
  });

  it('offers a move once, however many of the characters have it', () => {
    const c = pack({ basic: [clash], playbook: [fury] });
    expect(names(c, [character([fury]), { ...character([fury]), id: 'c2' }])).toEqual(['Clash', 'Battle Fury']);
  });
});
