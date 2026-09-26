/** What mentions what.
 *
 *  A campaign's notes refer to the same person from half a dozen places — a
 *  write-in on a sheet, a line in the town's notes, a record's own prose. Written
 *  as `[[Cerys]]`, those become links to one record, and the record can say where
 *  it is spoken of. Resolution is by name, like a wiki: a rename is a patch, and
 *  people type names, not ids.
 *
 *  A name that resolves to nothing — including, for a player, a record the GM has
 *  hidden — renders as plain text. That is the point: prep can mention someone
 *  the table has not met without the mention itself giving them away.
 */
import { app } from './state.svelte';
import { linkedNames, setLinkResolver } from './markdown';
import { href, type Place } from './router.svelte';

export interface Mention {
  /** where the mention was written */
  place: Place;
  label: string;
  /** the surrounding line, trimmed */
  context: string;
}

interface Target {
  place: Place;
  name: string;
  kind: 'record' | 'character';
}

/** Everything a [[name]] could point at, keyed by lowercased name. */
export function targets(): Map<string, Target> {
  const out = new Map<string, Target>();
  for (const row of Object.values(app.characters)) {
    const name = row.data.name?.trim();
    if (name) out.set(name.toLowerCase(), { place: { kind: 'character', id: row.id }, name, kind: 'character' });
  }
  // Records win a collision: a record is the thing someone wrote down on purpose.
  for (const row of Object.values(app.records)) {
    const name = row.data.name?.trim();
    if (name) out.set(name.toLowerCase(), { place: { kind: 'record', id: row.id }, name, kind: 'record' });
  }
  return out;
}

/** Teach the markdown renderer how to resolve a link. Called once, at start-up. */
export function installLinkResolver(): void {
  setLinkResolver((name) => {
    const found = targets().get(name.toLowerCase());
    return found ? { href: href({ place: found.place }), title: found.kind === 'record' ? 'Record' : 'Character sheet' } : null;
  });
}

function lineWith(text: string, name: string): string {
  const line = text.split('\n').find((l) => l.toLowerCase().includes(`[[${name.toLowerCase()}`)) ?? '';
  return line.trim().slice(0, 160);
}

/** Every text field, paired with where it lives, so mentions can be found in all of them. */
function* writtenText(): Generator<{ place: Place; label: string; text: string }> {
  for (const row of Object.values(app.characters)) {
    const label = row.data.name || 'a character';
    const place: Place = { kind: 'character', id: row.id };
    yield { place, label, text: row.data.notes ?? '' };
    yield { place, label, text: (row.data as { gm_notes?: string }).gm_notes ?? '' };
    for (const value of Object.values(row.data.option_text ?? {})) {
      for (const written of Object.values(value as Record<string, string>)) yield { place, label, text: written };
    }
  }
  for (const row of Object.values(app.shared)) {
    const label = row.data.name || 'a shared sheet';
    const place: Place = { kind: 'shared', id: row.id };
    for (const section of Object.values(row.data.sections ?? {})) {
      // Table rows and text sections both end up as strings somewhere in here.
      yield* stringsIn(section).map((text) => ({ place, label, text }));
    }
  }
  for (const row of Object.values(app.records)) {
    const label = row.data.name;
    const place: Place = { kind: 'record', id: row.id };
    yield { place, label, text: row.data.notes };
    yield { place, label, text: row.data.secret ?? '' };
    for (const tie of row.data.ties) yield { place, label, text: tie.note };
  }
}

function stringsIn(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(stringsIn);
  if (value && typeof value === 'object') return Object.values(value).flatMap(stringsIn);
  return [];
}

/** Where this record or character is spoken of. */
export function mentionsOf(name: string, self?: Place): Mention[] {
  const needle = name.trim().toLowerCase();
  if (!needle) return [];
  const out: Mention[] = [];
  const seen = new Set<string>();
  for (const { place, label, text } of writtenText()) {
    if (!text || !linkedNames(text).some((n) => n.toLowerCase() === needle)) continue;
    if (self && href({ place }) === href({ place: self })) continue;
    const key = `${href({ place })}:${lineWith(text, name)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ place, label, context: lineWith(text, name) });
  }
  return out;
}
