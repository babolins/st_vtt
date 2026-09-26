// A deliberately tiny markdown subset: paragraphs, **bold**, *em*, `code`, "- " lists, line breaks.

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** One line's worth of markup, with no block wrapper: for labels, help text and triggers.
 *  Escapes first, so a pack can emphasise a word but never inject HTML. */
export function renderInline(s: string | null | undefined): string {
  return s ? inline(s) : '';
}

/** Every [[name]] in a blob of text, for working out what mentions what. */
export function linkedNames(text: string | null | undefined): string[] {
  if (!text) return [];
  return [...text.matchAll(/\[\[([^\]]+)\]\]/g)].map((m) => m[1].trim()).filter(Boolean);
}

/** Resolve a [[name]] to a place, or null. Set by lib/links.ts once state exists;
 *  markdown stays free of app state, and unresolved links stay plain text — which
 *  is also how a record the GM has hidden behaves for everyone else. */
let resolveLink: ((name: string) => { href: string; title: string } | null) | null = null;
export function setLinkResolver(fn: typeof resolveLink): void {
  resolveLink = fn;
}

/** Runs on already-escaped text, so the captured name is escaped HTML: it is
 *  emitted as-is, and decoded only to look the name up. */
function links(s: string): string {
  return s.replace(/\[\[([^\]]+)\]\]/g, (whole, raw) => {
    const shown = String(raw).trim();
    const name = shown.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
    const found = resolveLink?.(name);
    if (!found) return shown;
    return `<a class="entity" href="${esc(found.href)}" title="${esc(found.title)}">${shown}</a>`;
  });
}

function inline(s: string): string {
  return links(esc(s))
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/_(.+?)_/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

export function render(md: string | null | undefined): string {
  if (!md) return '';
  const out: string[] = [];
  const lines = md.replace(/\r/g, '').split('\n');
  let para: string[] = [];
  let list: string[] = [];
  const flush = () => {
    if (para.length) { out.push(`<p>${para.map(inline).join('<br>')}</p>`); para = []; }
    if (list.length) { out.push(`<ul>${list.map((l) => `<li>${inline(l)}</li>`).join('')}</ul>`); list = []; }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^\s*[-*•]\s+/.test(line)) {
      if (para.length) flush();
      list.push(line.replace(/^\s*[-*•]\s+/, ''));
    } else if (line.trim() === '') {
      flush();
    } else {
      if (list.length) flush();
      para.push(line);
    }
  }
  flush();
  return out.join('');
}
