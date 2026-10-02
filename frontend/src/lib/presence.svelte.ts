// `use:presence={{ entity, id, path }}` on an input: announces focus/blur to the
// table and shows who else is editing the same field (outline + name badge).
import { app } from './state.svelte';
import { sendEphemeral } from './ws';
import { presenceKey, userColor } from './util';

export interface PresenceOpts {
  entity: string;
  id: string;
  path: string;
}

// The badge is tied to its input by CSS anchor positioning (see .presence-badge
// in app.css), so the browser keeps it on the input through any layout change.
// Each input needs its own anchor name.
let anchors = 0;

export function presence(node: HTMLElement, opts: PresenceOpts | undefined) {
  let current = opts;
  let badge: HTMLElement | null = null;
  const anchor = `--presence-${++anchors}`;

  const key = () => (current ? presenceKey(current.entity, current.id, current.path) : null);
  const onFocus = () => {
    if (current) sendEphemeral({ type: 'focus', ...current });
  };
  const onBlur = () => {
    if (current) sendEphemeral({ type: 'blur' });
  };
  node.addEventListener('focusin', onFocus);
  node.addEventListener('focusout', onBlur);

  const stop = $effect.root(() => {
    $effect(() => {
      const k = key();
      const others = k ? Object.values(app.fieldPresence).filter((f) => f.key === k) : [];
      if (others.length === 0) {
        node.style.boxShadow = '';
        node.style.removeProperty('anchor-name');
        badge?.remove();
        badge = null;
        return;
      }
      // Your own other tabs/devices show as "you"; other people first, by name.
      const me = app.me?.name;
      const names = [...new Set(others.map((o) => o.user))].sort((x, y) => (x === me ? 1 : 0) - (y === me ? 1 : 0));
      const color = userColor(names[0]);
      node.style.boxShadow = `0 0 0 2px ${color}`;
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'presence-badge';
        badge.style.setProperty('position-anchor', anchor);
        // After the input in the document, as an anchor must be, and inside the
        // same positioned box, so it scrolls and clips with it.
        (node.offsetParent ?? node.parentElement)?.appendChild(badge);
      }
      node.style.setProperty('anchor-name', anchor);
      badge.textContent = names.map((n) => (n === me ? 'you' : n)).join(', ');
      badge.style.background = color;
    });
  });

  return {
    update(next: PresenceOpts | undefined) {
      current = next;
    },
    destroy() {
      node.removeEventListener('focusin', onFocus);
      node.removeEventListener('focusout', onBlur);
      badge?.remove();
      stop();
    },
  };
}
