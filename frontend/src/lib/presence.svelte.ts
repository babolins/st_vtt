// `use:presence={{ entity, id, path }}` on an input: announces focus/blur to the
// table and shows who else is editing the same field (outline + name badge).
import { app } from './state.svelte';
import { sendEphemeral } from './ws';
import { presenceKey, userColor } from './util';

export interface PresenceOpts { entity: string; id: string; path: string }

export function presence(node: HTMLElement, opts: PresenceOpts | undefined) {
  let current = opts;
  let badge: HTMLElement | null = null;

  const key = () => (current ? presenceKey(current.entity, current.id, current.path) : null);
  const onFocus = () => { if (current) sendEphemeral({ type: 'focus', ...current }); };
  const onBlur = () => { if (current) sendEphemeral({ type: 'blur' }); };
  node.addEventListener('focusin', onFocus);
  node.addEventListener('focusout', onBlur);

  // The badge sits in the input's offsetParent, at the input's offset. A layout
  // change can move the input without resizing it (stat boxes rebalancing onto
  // two rows), but then the parent resizes, so both are watched. An input moved
  // inside a parent that keeps its size is not caught.
  let watched: Element | null = null;
  function place() {
    const parent = node.offsetParent as HTMLElement | null;
    if (parent !== watched) {
      if (watched) ro.unobserve(watched);
      if (parent) ro.observe(parent);
      watched = parent;
    }
    if (!badge || !parent) return;
    if (badge.parentElement !== parent) parent.appendChild(badge);
    badge.style.left = `${node.offsetLeft + node.offsetWidth - badge.offsetWidth - 2}px`;
    badge.style.top = `${node.offsetTop - 9}px`;
  }
  const ro = new ResizeObserver(place);
  ro.observe(node); // its first callback finds the parent to watch

  const stop = $effect.root(() => {
    $effect(() => {
      const k = key();
      const others = k ? Object.values(app.fieldPresence).filter((f) => f.key === k) : [];
      if (others.length === 0) {
        node.style.boxShadow = '';
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
      }
      badge.textContent = names.map((n) => (n === me ? 'you' : n)).join(', ');
      badge.style.background = color;
      requestAnimationFrame(place);
    });
  });

  return {
    update(next: PresenceOpts | undefined) { current = next; },
    destroy() {
      node.removeEventListener('focusin', onFocus);
      node.removeEventListener('focusout', onBlur);
      ro.disconnect();
      badge?.remove();
      stop();
    },
  };
}
