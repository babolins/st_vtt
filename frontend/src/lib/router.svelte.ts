/** Where you are, in the URL.
 *
 *  Hash routing, deliberately: it needs no server rewrites, survives being served
 *  under a sub-path (see vite.config.ts), and costs ~60 lines against a router
 *  dependency. What it buys is everything that assumes an address — a link in
 *  chat that points at a sheet, the back button, a reload that returns you to
 *  where you were, and, later, a graph node that can open the record it draws.
 */

export type Route =
  | { kind: 'all' }
  | { kind: 'character'; id: string }
  | { kind: 'shared'; id: string }
  | { kind: 'move'; id: string };

export const ALL: Route = { kind: 'all' };

export function parse(hash: string): Route | null {
  const path = hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  if (!path.length) return null;
  const [head, id] = path;
  if (head === 'all') return ALL;
  if (head === 'c' && id) return { kind: 'character', id };
  if (head === 's' && id) return { kind: 'shared', id };
  if (head === 'm' && id) return { kind: 'move', id };
  return null;
}

export function href(route: Route): string {
  switch (route.kind) {
    case 'all': return '#/all';
    case 'character': return `#/c/${route.id}`;
    case 'shared': return `#/s/${route.id}`;
    case 'move': return `#/m/${route.id}`;
  }
}

export const router = $state({ route: parse(location.hash) ?? ALL, landed: parse(location.hash) !== null });

addEventListener('hashchange', () => {
  router.route = parse(location.hash) ?? ALL;
  router.landed = true;
});

export function go(route: Route): void {
  location.hash = href(route);
}

/** Send someone to their own sheet on first load, rather than to everything at once. */
export function land(route: Route): void {
  if (router.landed) return;
  router.landed = true;
  history.replaceState(null, '', href(route));
  router.route = route;
}

export const isAt = (route: Route): boolean => href(router.route) === href(route);
