/** Where you are, in the URL.
 *
 *  Hash routing, deliberately: it needs no server rewrites, survives being served
 *  under a sub-path (see vite.config.ts), and costs ~60 lines against a router
 *  dependency. What it buys is everything that assumes an address — a link in
 *  chat that points at a sheet, the back button, a reload that returns you to
 *  where you were, and, later, a graph node that can open the record it draws.
 */

export type Place =
  | { kind: 'all' }
  | { kind: 'character'; id: string }
  | { kind: 'shared'; id: string }
  | { kind: 'move'; id: string }
  | { kind: 'people' }
  | { kind: 'record'; id: string }
  | { kind: 'graph' }
  | { kind: 'timeline' };

/** Where you are, plus what you are glancing at without going there. */
export interface Route {
  place: Place;
  peek?: Place;
}

export const ALL: Place = { kind: 'all' };

function parsePlace(path: string): Place | null {
  const parts = path.replace(/^#?\/?/, '').split('/').filter(Boolean);
  if (!parts.length) return null;
  const [head, id] = parts;
  if (head === 'all') return ALL;
  if (head === 'c' && id) return { kind: 'character', id };
  if (head === 's' && id) return { kind: 'shared', id };
  if (head === 'm' && id) return { kind: 'move', id };
  if (head === 'people') return { kind: 'people' };
  if (head === 'n' && id) return { kind: 'record', id };
  if (head === 'graph') return { kind: 'graph' };
  if (head === 'when') return { kind: 'timeline' };
  return null;
}

export function parse(hash: string): Route | null {
  const [path, query] = hash.replace(/^#/, '').split('?');
  const place = parsePlace(path);
  if (!place) return null;
  const peeked = new URLSearchParams(query ?? '').get('peek');
  const peek = peeked ? parsePlace(peeked) ?? undefined : undefined;
  return peek ? { place, peek } : { place };
}

function placeHref(place: Place): string {
  switch (place.kind) {
    case 'all': return '/all';
    case 'character': return `/c/${place.id}`;
    case 'shared': return `/s/${place.id}`;
    case 'move': return `/m/${place.id}`;
    case 'people': return '/people';
    case 'record': return `/n/${place.id}`;
    case 'graph': return '/graph';
    case 'timeline': return '/when';
  }
}

export function href(route: Route | Place): string {
  const full: Route = 'place' in route ? route : { place: route };
  const base = `#${placeHref(full.place)}`;
  return full.peek ? `${base}?peek=${placeHref(full.peek)}` : base;
}

export const router = $state({ route: parse(location.hash) ?? { place: ALL }, landed: parse(location.hash) !== null });

addEventListener('hashchange', () => {
  router.route = parse(location.hash) ?? { place: ALL };
  router.landed = true;
});

export function go(place: Place): void {
  location.hash = href({ place });
}

/** Glance at something without leaving where you are. */
export function peek(place: Place): void {
  location.hash = href({ place: router.route.place, peek: place });
}

export function unpeek(): void {
  location.hash = href({ place: router.route.place });
}

/** Send someone to their own sheet on first load, rather than to everything at once. */
export function land(place: Place): void {
  if (router.landed) return;
  router.landed = true;
  history.replaceState(null, '', href({ place }));
  router.route = { place };
}

export const isAt = (place: Place): boolean => placeHref(router.route.place) === placeHref(place);
