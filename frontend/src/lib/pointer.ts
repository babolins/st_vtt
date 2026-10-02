// Minimal RFC 6901 JSON Pointer apply, mirroring st_vtt/patch.py.
// Inside a list, `@<id>` names the element whose `id` is <id> (see there).

export function splitPointer(path: string): string[] {
  if (path === '') return [];
  if (!path.startsWith('/')) throw new Error(`bad pointer ${path}`);
  return path
    .slice(1)
    .split('/')
    .map((p) => p.replace(/~1/g, '/').replace(/~0/g, '~'));
}

export function escapeToken(tok: string): string {
  return tok.replace(/~/g, '~0').replace(/\//g, '~1');
}

/** The token for a list element by its id: build item paths with this, not the index. */
export function at(id: string): string {
  return '@' + escapeToken(id);
}

/** Position in `list` of the element `tok` names (-1 for an `@<id>` that is not there). */
function indexOf(list: any[], tok: string): number {
  if (tok.startsWith('@')) {
    const want = tok.slice(1);
    return list.findIndex((el) => el != null && typeof el === 'object' && el.id === want);
  }
  return Number(tok);
}

export function getPointer(doc: any, path: string): any {
  let node = doc;
  for (const tok of splitPointer(path)) {
    if (node == null) return undefined;
    node = Array.isArray(node) ? node[indexOf(node, tok)] : node[tok];
  }
  return node;
}

export type PatchOp = 'set' | 'remove' | 'list_add' | 'list_remove' | 'text_patch';

export function applyPointer(doc: any, path: string, value: any, op: PatchOp = 'set'): void {
  if (op === 'list_add' || op === 'list_remove') {
    let list = getPointer(doc, path);
    if (!Array.isArray(list)) list = [];
    const next =
      op === 'list_add' ? (list.includes(value) ? list : [...list, value]) : list.filter((x: any) => x !== value);
    applyPointer(doc, path, next, 'set');
    return;
  }
  if (op === 'text_patch') op = 'set'; // caller passes the merged text as value
  const tokens = splitPointer(path);
  if (tokens.length === 0) {
    if (op === 'remove') throw new Error('cannot remove root');
    for (const k of Object.keys(doc)) delete doc[k];
    Object.assign(doc, value);
    return;
  }
  let node = doc;
  for (let i = 0; i < tokens.length - 1; i++) {
    const tok = tokens[i];
    const next = tokens[i + 1];
    if (Array.isArray(node)) {
      const i = indexOf(node, tok);
      if (i < 0 && op === 'remove') return; // what it would have removed went with the item
      node = node[i];
    } else {
      if (node[tok] == null) {
        if (op === 'remove') throw new Error(`missing ${tok}`);
        if (next.startsWith('@')) throw new Error(`no list item with id ${next.slice(1)}`);
        node[tok] = next === '-' || /^\d+$/.test(next) ? [] : {};
      }
      node = node[tok];
    }
    if (node == null) throw new Error(`cannot descend into ${tok}`);
  }
  const last = tokens[tokens.length - 1];
  if (Array.isArray(node)) {
    const i = last === '-' ? node.length : indexOf(node, last);
    if (op === 'set') {
      if (i < 0) throw new Error(`no list item with id ${last.slice(1)}`);
      if (i === node.length) node.push(value);
      else node[i] = value;
    } else if (i >= 0) {
      node.splice(i, 1);
    }
  } else if (op === 'set') {
    node[last] = value;
  } else {
    delete node[last];
  }
}
