// Small helpers for the sheet and chat: content-pack lookups, formatting, files.

import type { ContentPack, InsertDef, Move, Playbook, CharacterDoc } from './types';

export function levelUpCost(formula: string, level: number): number {
  if (!/^[0-9+\-*/() level]*$/.test(formula)) return Infinity;
  try { return Math.floor(Function('level', `return (${formula});`)(level)); } catch { return Infinity; }
}

/** One line to pick a move by: its trigger, or the start of its text when it has none. */
export function movePreview(m: Move): string {
  return m.trigger || m.text.slice(0, 120);
}

export function fmtMod(n: number): string {
  return n >= 0 ? `+${n}` : `${n}`;
}

export function playbookOf(content: ContentPack, doc: CharacterDoc): Playbook | undefined {
  return content.playbooks.find((p) => p.id === doc.playbook);
}

/** The pack-defined inserts on a sheet, in sheet order ('gear' and friends are engine sections). */
export function packInserts(content: ContentPack, doc: CharacterDoc): InsertDef[] {
  return doc.inserts
    .map((id) => content.inserts.find((i) => i.id === id))
    .filter((i): i is InsertDef => !!i);
}

/** Everything carried: gear bulk, plus every load box marked on a section option (Book I, p142). */
export function carriedLoad(content: ContentPack, doc: CharacterDoc, pb: Playbook | undefined): number {
  let load = 0;
  for (const item of doc.gear.items) load += Number(item.bulk) || 0;
  const sections = [...(pb?.sections ?? []), ...packInserts(content, doc).flatMap((i) => i.sections)];
  const index = moveIndex(content, doc);
  const owners = [...sections.map((s) => s.id), ...doc.moves.taken.filter((id) => index.get(id)?.options.length)];
  for (const owner of owners) {
    const marked = doc.option_tracks[owner];
    if (marked) for (const n of Object.values(marked)) load += Number(n.bulk) || 0;
  }
  return load;
}

export function loadLabel(content: ContentPack, load: number): string {
  const r = content.pack.load;
  if (!r) return '';
  return load <= r.light ? 'light' : load <= r.normal ? 'normal' : load <= r.heavy ? 'heavy' : 'overloaded';
}

/** All moves a character could know: shared + every playbook's + inserts + arcana-on-sheet + custom.
 *  Every playbook, because a move with `grants` can hand you one from elsewhere. */
export function moveIndex(content: ContentPack, doc: CharacterDoc): Map<string, Move> {
  const idx = new Map<string, Move>();
  for (const group of Object.values(content.moves)) for (const m of group) idx.set(m.id, m);
  for (const p of content.playbooks) for (const m of p.moves) idx.set(m.id, m);
  for (const ins of packInserts(content, doc)) for (const m of ins.moves) idx.set(m.id, m);
  for (const a of doc.arcana) for (const m of a.moves) idx.set(m.id, m);
  for (const m of doc.custom_moves) idx.set(m.id, m);
  return idx;
}

/** The playbook a move belongs to, when it is not this character's own. */
export function borrowedFrom(content: ContentPack, id: string, pb: Playbook | undefined): Playbook | undefined {
  if (pb?.moves.some((m) => m.id === id)) return undefined;
  return content.playbooks.find((p) => p.id !== pb?.id && p.moves.some((m) => m.id === id));
}

/** Moves from other playbooks this character may take, and how many picks are left unspent. */
export function granted(content: ContentPack, doc: CharacterDoc, pb: Playbook | undefined): { offers: { move: Move; from: Playbook }[]; left: number } {
  const taken = new Set(doc.moves.taken);
  const sources = new Set<string>();
  const exclude = new Set<string>();
  let any = false;
  let picks = 0;
  for (const m of pb?.moves ?? []) {
    if (!m.grants || !taken.has(m.id)) continue;
    picks += m.grants.n;
    for (const t of m.grants.exclude_tags) exclude.add(t);
    if (m.grants.from_playbooks.length === 0) any = true;
    else for (const id of m.grants.from_playbooks) sources.add(id);
  }
  const spent = [...taken].filter((id) => borrowedFrom(content, id, pb)).length;
  const offers: { move: Move; from: Playbook }[] = [];
  if (picks > spent) {
    for (const source of content.playbooks) {
      if (source.id === pb?.id || !(any || sources.has(source.id))) continue;
      for (const m of source.moves) {
        if (taken.has(m.id) || m.tags.some((t) => exclude.has(t))) continue;
        offers.push({ move: m, from: source });
      }
    }
  }
  return { offers, left: picks - spent };
}

export function timeShort(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function download(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function pickFile(accept = '.json'): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.onchange = async () => {
      const f = input.files?.[0];
      if (!f) return reject(new Error('no file'));
      try { resolve(JSON.parse(await f.text())); } catch (e) { reject(e); }
    };
    input.click();
  });
}

/** Deterministic, readable color per user name (hsl hue from a string hash). */
export function userColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return `hsl(${h % 360} 65% 45%)`;
}

export function presenceKey(entity: string, id: string, path: string): string {
  return `${entity}/${id}${path}`;
}
