/** Every move in the pack, flattened once, with where it came from.
 *
 *  The pack is already in memory, so browsing and searching need no index on the
 *  server and no round trip: 387 moves in the Stonetop pack, and a pack an order
 *  of magnitude bigger would still be a single pass.
 */
import type { CharacterRow, ContentPack, Move } from './types';
import { moveIndex, playbookOf } from './util';

export type SourceKind = 'group' | 'playbook' | 'insert' | 'arcanum' | 'shared' | 'custom';

export interface MoveSource {
  kind: SourceKind;
  /** the group name, playbook id, insert id, ... */
  id: string;
  /** what to show: "Basic moves", "The Heavy", "Initiates of Danu" */
  label: string;
}

export interface IndexedMove {
  move: Move;
  source: MoveSource;
}

const title = (s: string) => s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');

export function allMoves(content: ContentPack): IndexedMove[] {
  const out: IndexedMove[] = [];
  const seen = new Set<string>();
  const push = (move: Move, source: MoveSource) => {
    const key = `${source.kind}:${source.id}:${move.id}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ move, source });
  };
  for (const [group, moves] of Object.entries(content.moves)) {
    for (const m of moves) push(m, { kind: 'group', id: group, label: `${title(group)} moves` });
  }
  for (const pb of content.playbooks) {
    for (const m of pb.moves) push(m, { kind: 'playbook', id: pb.id, label: pb.name });
  }
  for (const ins of content.inserts) {
    for (const m of ins.moves) push(m, { kind: 'insert', id: ins.id, label: ins.name });
  }
  for (const a of content.arcana) {
    for (const m of a.moves) push(m, { kind: 'arcanum', id: a.id, label: a.name });
  }
  for (const sheet of content.shared_sheets) {
    for (const m of sheet.moves) push(m, { kind: 'shared', id: sheet.id, label: sheet.name });
  }
  return out;
}

/** The moves one character actually has, in the order a sheet lists them. */
export function movesOf(content: ContentPack, row: CharacterRow): IndexedMove[] {
  const doc = row.data;
  const index = moveIndex(content, doc);
  const pb = playbookOf(content, doc);
  const out: IndexedMove[] = [];
  for (const id of doc.moves.taken) {
    const move = index.get(id);
    if (!move) continue;
    const from = content.playbooks.find((p) => p.moves.some((m) => m.id === move.id));
    const insert = content.inserts.find((i) => i.moves.some((m) => m.id === move.id));
    const arc = doc.arcana.find((a) => a.moves.some((m) => m.id === move.id));
    const source: MoveSource = from
      ? { kind: 'playbook', id: from.id, label: from.id === pb?.id ? from.name : `${from.name} (borrowed)` }
      : insert
        ? { kind: 'insert', id: insert.id, label: insert.name }
        : arc
          ? { kind: 'arcanum', id: arc.id, label: arc.name }
          : { kind: 'custom', id: 'custom', label: 'Custom' };
    out.push({ move, source });
  }
  return out;
}

/** Shared moves everyone has — the ones printed on the handout, not on a playbook. */
export function tableMoves(content: ContentPack): IndexedMove[] {
  return allMoves(content).filter((e) => e.source.kind === 'group');
}

/** Group by the pack's own themes, falling back to source when a pack authors none. */
export function byTheme(entries: IndexedMove[]): { label: string; entries: IndexedMove[]; authored: boolean }[] {
  const themed = new Map<string, IndexedMove[]>();
  const unthemed: IndexedMove[] = [];
  for (const e of entries) {
    const themes = e.move.themes ?? [];
    if (themes.length === 0) unthemed.push(e);
    for (const t of themes) {
      const list = themed.get(t) ?? [];
      list.push(e);
      themed.set(t, list);
    }
  }
  const groups = [...themed.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([label, list]) => ({ label: title(label), entries: list, authored: true }));
  if (unthemed.length) {
    // No themes in this pack (or not on these moves): source is the honest fallback.
    for (const g of bySource(unthemed)) groups.push({ ...g, authored: false });
  }
  return groups;
}

export function bySource(entries: IndexedMove[]): { label: string; entries: IndexedMove[] }[] {
  const order: SourceKind[] = ['group', 'shared', 'playbook', 'insert', 'arcanum', 'custom'];
  const groups = new Map<string, { label: string; kind: SourceKind; entries: IndexedMove[] }>();
  for (const e of entries) {
    const key = `${e.source.kind}:${e.source.id}`;
    const g = groups.get(key) ?? { label: e.source.label, kind: e.source.kind, entries: [] };
    g.entries.push(e);
    groups.set(key, g);
  }
  return [...groups.values()]
    .sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind) || a.label.localeCompare(b.label))
    .map(({ label, entries }) => ({ label, entries }));
}

export function alphabetical(entries: IndexedMove[]): { label: string; entries: IndexedMove[] }[] {
  const letters = new Map<string, IndexedMove[]>();
  for (const e of [...entries].sort((a, b) => a.move.name.localeCompare(b.move.name))) {
    const letter = (e.move.name[0] ?? '#').toUpperCase();
    const key = /[A-Z]/.test(letter) ? letter : '#';
    (letters.get(key) ?? letters.set(key, []).get(key)!).push(e);
  }
  return [...letters.entries()].map(([label, list]) => ({ label, entries: list }));
}
