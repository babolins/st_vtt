/** Fuzzy matching over the pack's moves.
 *
 *  Ranked by *where* the match lands, not just whether it matched: a name beats a
 *  trigger beats the body. The trigger matters because that is how people recall a
 *  move — nobody remembers it is called "Make Camp", they remember "the one about
 *  resting somewhere unsafe" — so a trigger hit also carries the line it matched,
 *  and the result shows it.
 */
import type { IndexedMove } from './moveindex';

export type MatchField = 'name' | 'trigger' | 'text' | 'source';

export interface Hit {
  entry: IndexedMove;
  score: number;
  field: MatchField;
  /** character ranges in the move's name to emphasise */
  marks: [number, number][];
  /** the matched line, when the match was not in the name */
  snippet: string;
}

/** Subsequence match: every query character in order. Returns positions, or null.
 *
 *  Constrained on purpose. A long name will contain almost any short letter
 *  sequence if you let the matches sprawl — "melee" hides inside "Tor(m)ent's
 *  B(le)ssing" — so a match only counts when it is tight: spread over not much
 *  more than its own length, or landing mostly on word starts the way an
 *  abbreviation does ("mkcmp" for Make Camp).
 */
function subsequence(haystack: string, needle: string): number[] | null {
  const hits: number[] = [];
  let i = 0;
  for (let h = 0; h < haystack.length && i < needle.length; h++) {
    if (haystack[h] === needle[i]) {
      hits.push(h);
      i++;
    }
  }
  if (i !== needle.length) return null;
  const span = hits[hits.length - 1] - hits[0] + 1;
  const wordStarts = hits.filter((at) => at === 0 || /[\s\-—(':]/.test(haystack[at - 1] ?? '')).length;
  // Room for an abbreviation ("mkcmp" for Make Camp) but not for a sprawl: the
  // letters of "melee" can be found scattered across "Torment's Blessing".
  const tight = span <= needle.length * 2.5 + 2;
  const initials = wordStarts >= Math.ceil(needle.length / 2);
  return tight || initials ? hits : null;
}

/** Contiguous runs score higher, and a match at a word start higher still. */
function tightness(positions: number[], haystack: string): number {
  let score = 0;
  for (let i = 0; i < positions.length; i++) {
    const at = positions[i];
    if (at === 0 || /[\s\-—(]/.test(haystack[at - 1] ?? '')) score += 6;
    if (i > 0 && at === positions[i - 1] + 1) score += 4;
  }
  return score;
}

function ranges(positions: number[]): [number, number][] {
  const out: [number, number][] = [];
  for (const p of positions) {
    const last = out[out.length - 1];
    if (last && last[1] === p) last[1] = p + 1;
    else out.push([p, p + 1]);
  }
  return out;
}

/** The sentence around a match, trimmed to something that fits one line. */
function lineAround(text: string, at: number, len: number): string {
  const start = Math.max(0, text.lastIndexOf(' ', Math.max(0, at - 40)));
  const end = text.indexOf(' ', Math.min(text.length, at + len + 50));
  const slice = text.slice(start, end === -1 ? text.length : end).trim();
  return (start > 0 ? '…' : '') + slice + (end !== -1 && end < text.length ? '…' : '');
}

/** Words every trigger contains; matching on them tells you nothing. */
const STOP = new Set(['the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'for', 'with', 'you', 'your',
  'when', 'that', 'this', 'it', 'is', 'are', 'be', 'as', 'by', 'from', 'one', 'someone', 'something', 'about']);

/** "resting" also matches "rest": enough stemming to be useful, not enough to be wrong. */
function stem(token: string): string {
  if (token.length > 5) {
    for (const suffix of ['ing', 'ed', 'es', 's']) {
      if (token.endsWith(suffix)) return token.slice(0, -suffix.length);
    }
  }
  return token;
}

interface Fields { name: string; trigger: string; body: string; where: string }

/** Earlier in a field counts for more: the opening clause is what a move is about. */
function nearness(at: number): number {
  return 1 + Math.max(0, 1 - at / 90) * 0.5;
}

function tokenScore(t: string, f: Fields): { score: number; field: MatchField; at: number } | null {
  const stemmed = stem(t);
  const tries: [string, number][] = stemmed === t ? [[t, 1]] : [[t, 1], [stemmed, 0.8]];
  for (const [needle, weight] of tries) {
    let at = f.name.indexOf(needle);
    if (at >= 0) return { score: 90 * weight, field: 'name', at };
    at = f.trigger.indexOf(needle);
    if (at >= 0) return { score: 55 * weight * nearness(at), field: 'trigger', at };
    at = f.body.indexOf(needle);
    if (at >= 0) return { score: 28 * weight * nearness(at), field: 'text', at };
    at = f.where.indexOf(needle);
    if (at >= 0) return { score: 18 * weight, field: 'source', at };
  }
  return null;
}

export function search(entries: IndexedMove[], query: string, limit = 60): Hit[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const squashed = q.replace(/\s+/g, '');
  const words = q.split(/\s+/).filter((w) => w.length > 1);
  const meaningful = words.filter((w) => !STOP.has(w));
  const tokens = meaningful.length ? meaningful : words;
  const hits: Hit[] = [];

  for (const entry of entries) {
    const { move, source } = entry;
    const name = move.name.toLowerCase();
    const trigger = (move.trigger ?? '').toLowerCase();
    const bodyText = [
      move.text ?? '',
      ...Object.values(move.outcomes ?? {}).map((o) => (typeof o === 'string' ? o : (o?.text ?? ''))),
      move.hold ? `hold ${move.hold.name} ${move.hold.note ?? ''}` : '',
    ].join('\n');
    const fields: Fields = {
      name,
      trigger,
      body: bodyText.toLowerCase(),
      where: `${source.label} ${move.tags.join(' ')} ${(move.themes ?? []).join(' ')}`.toLowerCase(),
    };

    // 1. the name, best first: prefix, then word-start, then anywhere, then fuzzy.
    const at = name.indexOf(q);
    if (at === 0) {
      hits.push({ entry, score: 1000 - name.length, field: 'name', marks: [[0, q.length]], snippet: '' });
      continue;
    }
    if (at > 0) {
      const wordStart = /[\s\-—(]/.test(name[at - 1] ?? '');
      hits.push({ entry, score: (wordStart ? 860 : 780) - name.length, field: 'name', marks: [[at, at + q.length]], snippet: '' });
      continue;
    }
    const fuzzy = subsequence(name, squashed);
    if (fuzzy) {
      hits.push({ entry, score: 600 + tightness(fuzzy, name) - name.length, field: 'name', marks: ranges(fuzzy), snippet: '' });
      continue;
    }

    // 2. every other word the person typed, scored where it lands. Nobody recalls
    //    "Make Camp" — they recall "resting somewhere unsafe", which is three
    //    words of which two are in the trigger.
    let total = 0;
    let matched = 0;
    let best: { score: number; field: MatchField; at: number } | null = null;
    for (const token of tokens) {
      const hit = tokenScore(token, fields);
      if (!hit) continue;
      matched++;
      total += hit.score;
      if (!best || hit.score > best.score) best = hit;
    }
    if (!best) continue;
    const coverage = matched / tokens.length;
    if (coverage < 0.5) continue;
    // The words in the order they were typed, found together, is a much stronger
    // signal than the same words scattered through a page of outcomes.
    if (tokens.length > 1) {
      const phrase = tokens.join(' ');
      if (fields.trigger.includes(phrase)) total += 60;
      else if (fields.body.includes(phrase)) total += 30;
    }
    const source_text = best.field === 'trigger' ? move.trigger : best.field === 'text' ? bodyText : '';
    hits.push({
      entry,
      // Kept under the name tiers on purpose: an exact name always wins.
      score: Math.min(520, total * coverage),
      field: best.field,
      marks: [],
      snippet: source_text ? lineAround(source_text, best.at, 8) : source.label,
    });
  }

  return hits
    .sort((a, b) => b.score - a.score || a.entry.move.name.localeCompare(b.entry.move.name))
    .slice(0, limit);
}

/** Split a name into emphasised and plain runs, for rendering a hit. */
export function splitMarks(name: string, marks: [number, number][]): { text: string; hit: boolean }[] {
  if (!marks.length) return [{ text: name, hit: false }];
  const out: { text: string; hit: boolean }[] = [];
  let at = 0;
  for (const [start, end] of marks) {
    if (start > at) out.push({ text: name.slice(at, start), hit: false });
    out.push({ text: name.slice(start, end), hit: true });
    at = end;
  }
  if (at < name.length) out.push({ text: name.slice(at), hit: false });
  return out;
}
