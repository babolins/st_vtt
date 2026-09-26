import { api, basePath } from './api';
import { applyPointer } from './pointer';
import { app, loadState, toast } from './state.svelte';
import type { Message, StateResponse } from './types';
import { presenceKey } from './util';

export const clientId = Math.random().toString(36).slice(2, 10);

let socket: WebSocket | null = null;
let backoff = 500;
let refCounter = 0;
const pending = new Map<number, { resolve: () => void; reject: (e: Error) => void; entity?: string; id?: string }>();
let closedByUs = false;

export async function refreshState(): Promise<void> {
  const s = await api.get<StateResponse>('/api/state');
  loadState(s);
}

export function connect(): void {
  closedByUs = false;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  socket = new WebSocket(`${proto}://${location.host}${basePath}/ws`);
  socket.onopen = async () => {
    backoff = 500;
    app.connected = true;
    try { await refreshState(); } catch (e) { console.error(e); }
    sendEphemeral({ type: 'presence_sync' });
    for (const k of Object.keys(app.fieldPresence)) delete app.fieldPresence[k];
  };
  socket.onmessage = (ev) => handle(JSON.parse(ev.data));
  socket.onclose = (ev) => {
    app.connected = false;
    socket = null;
    for (const [, p] of pending) p.reject(new Error('disconnected'));
    pending.clear();
    if (ev.code === 4401 || ev.code === 4409) {
      app.loginNotice = ev.code === 4409 ? 'You were signed in on another device, so this one was signed out.' : 'Your session ended. Please sign in again.';
      app.me = null;
      return;
    }
    if (!closedByUs) setTimeout(connect, backoff), (backoff = Math.min(backoff * 2, 10000));
  };
}

export function disconnect(): void {
  closedByUs = true;
  socket?.close();
}

/** Fire-and-forget message (focus/blur/typing); no ack, no error. */
export function sendEphemeral(msg: Record<string, unknown>): void {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify({ ...msg, client: clientId }));
}

export function send(msg: Record<string, unknown>): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      reject(new Error('not connected'));
      return;
    }
    const ref = ++refCounter;
    pending.set(ref, { resolve, reject, entity: msg.entity as string, id: msg.id as string });
    socket.send(JSON.stringify({ ...msg, ref, client: clientId }));
  });
}

function handle(ev: any): void {
  switch (ev.type) {
    case 'ack': {
      const p = pending.get(ev.ref);
      if (p) { pending.delete(ev.ref); p.resolve(); }
      break;
    }
    case 'error': {
      const p = ev.ref != null ? pending.get(ev.ref) : undefined;
      if (p) {
        pending.delete(ev.ref);
        p.reject(new Error(ev.message));
        if (p.entity) refreshState().catch(() => {});
      }
      toast(ev.message, 'error');
      break;
    }
    case 'patch': {
      if (ev.client === clientId && !ev.merged) break; // we applied it optimistically; merged results must be re-applied
      const target = ev.entity === 'character' ? app.characters[ev.id] : ev.entity === 'shared' ? app.shared[ev.id] : null;
      if (!target) { refreshState().catch(() => {}); break; }
      try {
        applyPointer(target.data, ev.path, ev.value, ev.op);
        target.revision = ev.revision;
      } catch {
        refreshState().catch(() => {});
      }
      break;
    }
    case 'message': {
      const m = ev.message as Message;
      app.messages = [...app.messages.slice(-499), m];
      break;
    }
    case 'message_updated': {
      const m = ev.message as Message;
      app.messages = app.messages.map((old) => (old.id === m.id ? m : old));
      break;
    }
    case 'chat_cleared':
      app.messages = [];
      break;
    case 'character_created':
      app.characters[ev.character.id] = ev.character;
      break;
    case 'character_deleted':
      delete app.characters[ev.id];
      break;
    case 'character_owner':
      if (app.characters[ev.id]) app.characters[ev.id].owner = ev.owner;
      break;
    case 'shared_created':
    case 'shared_replaced':
      app.shared[ev.sheet.id] = ev.sheet;
      break;
    case 'shared_deleted':
      delete app.shared[ev.id];
      break;
    case 'presence':
      app.online = ev.users;
      for (const [c, f] of Object.entries(app.fieldPresence)) if (!ev.users.includes(f.user)) delete app.fieldPresence[c];
      break;
    case 'field_presence':
      if (!ev.client || ev.client === clientId) break;
      if (ev.path == null) delete app.fieldPresence[ev.client];
      else app.fieldPresence[ev.client] = { user: ev.user, key: presenceKey(ev.entity, ev.id, ev.path) };
      break;
    case 'typing':
      if (ev.active) app.typing[ev.user] = Date.now() + 4000;
      else delete app.typing[ev.user];
      break;
  }
}
