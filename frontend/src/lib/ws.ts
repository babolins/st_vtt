import { api, basePath } from './api';
import { applyPointer, type PatchOp } from './pointer';
import { app, loadState, toast } from './state.svelte';
import { applyEcho, PatchQueue, type PatchEntry } from './sync';
import type { Message, StateResponse } from './types';
import { presenceKey } from './util';

export const clientId = Math.random().toString(36).slice(2, 10);

let socket: WebSocket | null = null;
let backoff = 500;
let refCounter = 0;
const pending = new Map<number, { resolve: () => void; reject: (e: Error) => void; patch: boolean }>();
const patches = new PatchQueue();
/** Open, and the outbox replayed: until then patches queue behind it and other messages are refused. */
let synced = false;
let closedByUs = false;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function entityRow(entity: unknown, id: unknown) {
  const key = String(id);
  return entity === 'character' ? app.characters[key] : entity === 'shared' ? app.shared[key] : entity === 'record' ? app.records[key] : undefined;
}

function applyLocally(e: PatchEntry): void {
  const target = entityRow(e.entity, e.id);
  if (!target) return;
  try { applyPointer(target.data, e.path, e.value, e.op); } catch (err) { console.warn('local patch failed', err); }
}

function countUnsaved(): void {
  app.unsaved = patches.unsaved;
}

/** Load a fresh snapshot, then re-apply our patches it does not include yet. */
export async function refreshState(): Promise<void> {
  const s = await api.get<StateResponse>(`/api/state?client=${clientId}`);
  loadState(s);
  for (const e of patches.rebase(s.applied_ref ?? 0, s.me?.name)) applyLocally(e);
  countUnsaved();
}

function transmit(ref: number, msg: Record<string, unknown>): void {
  socket!.send(JSON.stringify({ ...msg, ref, client: clientId }));
}

function flushOutbox(): boolean {
  if (!socket || socket.readyState !== WebSocket.OPEN) return false;
  for (const e of patches.drain()) {
    patches.sent(e);
    transmit(e.ref, e.msg);
  }
  countUnsaved();
  return true;
}

export function connect(): void {
  closedByUs = false;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  socket = new WebSocket(`${proto}://${location.host}${basePath}/ws`);
  const ws = socket;
  socket.onopen = async () => {
    backoff = 500;
    app.connected = true;
    try { await refreshState(); } catch (e) { console.error(e); }
    if (socket !== ws) return; // dropped meanwhile; the next socket replays the outbox
    synced = flushOutbox();
    sendEphemeral({ type: 'presence_sync' });
    for (const k of Object.keys(app.fieldPresence)) delete app.fieldPresence[k];
  };
  socket.onmessage = (ev) => handle(JSON.parse(ev.data));
  socket.onclose = (ev) => {
    app.connected = false;
    socket = null;
    synced = false;
    patches.disconnected();
    countUnsaved();
    let lost = false;
    for (const [, p] of pending) {
      if (p.patch) { p.resolve(); continue; } // back in the outbox
      lost = true;
      p.reject(new Error('disconnected'));
    }
    pending.clear();
    if (lost) toast('Not connected', 'error');
    if (ev.code === 4401 || ev.code === 4409) {
      app.loginNotice = ev.code === 4409 ? 'You were signed in on another device, so this one was signed out.' : 'Your session ended. Please sign in again.';
      app.me = null;
      return;
    }
    if (!closedByUs) {
      reconnectTimer = setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 10000);
    }
  };
}

/** Log out: stop reconnecting and drop anything unsent. */
export function disconnect(): void {
  closedByUs = true;
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  patches.clear();
  countUnsaved();
  socket?.close();
}

/** Fire-and-forget message (focus/blur/typing); no ack, no error. */
export function sendEphemeral(msg: Record<string, unknown>): void {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify({ ...msg, client: clientId }));
}

/** Send a message the server acks (chat, rolls, ...). Refused, with a toast, while not connected. */
export function send(msg: Record<string, unknown>): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!synced || !socket || socket.readyState !== WebSocket.OPEN) {
      toast('Not connected', 'error');
      reject(new Error('not connected'));
      return;
    }
    const ref = ++refCounter;
    pending.set(ref, { resolve, reject, patch: false });
    transmit(ref, msg);
  });
}

/**
 * Send a patch the caller has already applied locally (`value` is what it applied). While not
 * connected it waits in the outbox to be replayed on reconnect. Resolves once acked or queued;
 * never rejects (errors are toasted).
 */
export function sendPatch(msg: Record<string, unknown>, value: unknown): Promise<void> {
  const e: PatchEntry = {
    ref: ++refCounter, msg, entity: String(msg.entity), id: (msg.id as string | null) ?? null,
    path: String(msg.path), op: msg.op as PatchOp, value, user: app.me?.name ?? '', overtaken: false,
  };
  if (!synced || !socket || socket.readyState !== WebSocket.OPEN) {
    patches.queue(e);
    countUnsaved();
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    pending.set(e.ref, { resolve, reject: () => resolve(), patch: true });
    patches.sent(e);
    transmit(e.ref, msg);
  });
}

function handle(ev: any): void {
  switch (ev.type) {
    case 'ack': {
      const p = pending.get(ev.ref);
      if (p) { pending.delete(ev.ref); p.resolve(); }
      patches.settle(ev.ref);
      break;
    }
    case 'error': {
      const p = ev.ref != null ? pending.get(ev.ref) : undefined;
      if (p) {
        pending.delete(ev.ref);
        p.reject(new Error(ev.message));
        if (patches.settle(ev.ref)) refreshState().catch(() => {});
      }
      toast(ev.message, 'error');
      break;
    }
    case 'patch': {
      if (ev.client === clientId) {
        if (!applyEcho(patches.get(ev.ref), ev.merged)) break; // already shown, and nothing landed on top of it since
      } else {
        patches.overtake(ev.entity, ev.id, ev.path);
      }
      const target = entityRow(ev.entity, ev.id);
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
    case 'record_created':
    case 'record_updated':
      app.records[ev.record.id] = ev.record;
      break;
    case 'record_deleted':
      delete app.records[ev.id];
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
