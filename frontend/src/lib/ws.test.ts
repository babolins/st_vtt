import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { StateResponse } from './types';

// ws.ts keeps its socket, pending sends and outbox at module level, so every test imports a fresh
// copy (with a fresh `app`) against a fake WebSocket and a mocked /api/state.

const get = vi.hoisted(() => vi.fn());
vi.mock('./api', () => ({ basePath: '', api: { get } }));

class FakeSocket {
  static OPEN = 1;
  static all: FakeSocket[] = [];
  readyState = 0;
  sent: any[] = [];
  onopen: (() => Promise<void>) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  constructor(public url: string) {
    FakeSocket.all.push(this);
  }
  send(data: string) {
    this.sent.push(JSON.parse(data));
  }
  close() {
    this.drop(1000);
  }
  // the server's side
  open(): Promise<void> {
    this.readyState = FakeSocket.OPEN;
    return this.onopen!();
  }
  receive(ev: Record<string, unknown>) {
    this.onmessage!({ data: JSON.stringify(ev) });
  }
  drop(code = 1006) {
    this.readyState = 3;
    this.onclose!({ code });
  }
}

function snapshot(over: Partial<StateResponse> = {}): StateResponse {
  return {
    me: { name: 'Alice', role: 'player' },
    campaign_name: 'Test',
    users: [],
    online: ['Alice'],
    characters: [{ id: 'c1', owner: 'Alice', revision: 0, data: { name: 'Bryn', hp: { current: 5, max: 10 } } }],
    shared: [{ id: 'v', template: 'village', revision: 0, created_at: 0, data: { notes: 'hello' } }],
    records: [],
    messages: [],
    applied_ref: 0,
    ...over,
  } as unknown as StateResponse;
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

let ws: typeof import('./ws');
let app: typeof import('./state.svelte').app;
let patch: typeof import('./patch').patch;

beforeEach(async () => {
  vi.useFakeTimers();
  vi.resetModules();
  vi.stubGlobal('WebSocket', FakeSocket);
  vi.stubGlobal('location', { protocol: 'http:', host: 'table.test' });
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  FakeSocket.all = [];
  get.mockReset().mockImplementation(async () => snapshot());
  ws = await import('./ws');
  ({ app } = await import('./state.svelte'));
  ({ patch } = await import('./patch'));
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const latest = () => FakeSocket.all[FakeSocket.all.length - 1];
const hp = () => (app.characters.c1.data as any).hp.current;
const kinds = (s: FakeSocket) => s.sent.map((m) => m.type);

/** Connect and open; the socket's `sent` starts empty. */
async function online(): Promise<FakeSocket> {
  ws.connect();
  const s = latest();
  await s.open();
  s.sent.length = 0;
  return s;
}

/** Let the scheduled reconnect fire and the new socket open. */
async function reconnect(): Promise<FakeSocket> {
  const before = FakeSocket.all.length;
  await vi.advanceTimersByTimeAsync(10_000);
  expect(FakeSocket.all.length).toBe(before + 1);
  await latest().open();
  return latest();
}

function echo(s: FakeSocket, sent: any, over: Record<string, unknown> = {}) {
  s.receive({
    type: 'patch',
    entity: sent.entity,
    id: sent.id,
    path: sent.path,
    value: sent.value,
    op: sent.op,
    revision: 1,
    client: ws.clientId,
    ref: sent.ref,
    merged: false,
    ...over,
  });
}

describe('connecting', () => {
  it('loads the table, then asks who is looking at what', async () => {
    ws.connect();
    const s = latest();
    expect(s.url).toBe('ws://table.test/ws');
    app.fieldPresence.stale = { user: 'Bob', key: 'x' };
    await s.open();
    expect(app.connected).toBe(true);
    expect(hp()).toBe(5);
    expect(get).toHaveBeenCalledWith(`/api/state?client=${ws.clientId}`);
    expect(s.sent).toEqual([{ type: 'presence_sync', client: ws.clientId }]);
    expect(app.fieldPresence).toEqual({});
  });

  it('replays edits made while disconnected, in order, and keeps showing them', async () => {
    const s1 = await online();
    s1.drop();
    void patch('character', 'c1', '/hp/current', 3);
    void patch('shared', 'v', '/notes', 'offline');
    expect(s1.sent).toEqual([]);
    expect(app.unsaved).toBe(2);
    expect(hp()).toBe(3);

    const s2 = await reconnect();
    // The fresh snapshot still has the old values; ours are laid back on top of it.
    expect(hp()).toBe(3);
    expect((app.shared.v.data as any).notes).toBe('offline');
    expect(kinds(s2)).toEqual(['patch', 'patch', 'presence_sync']);
    expect(s2.sent.slice(0, 2).map((m) => [m.ref, m.path, m.value])).toEqual([
      [1, '/hp/current', 3],
      [2, '/notes', 'offline'],
    ]);
    expect(app.unsaved).toBe(0);
  });

  it('puts an edit in flight back in the outbox when the socket drops, and resends it with its ref', async () => {
    const s1 = await online();
    const sending = patch('character', 'c1', '/hp/current', 3);
    const ref = s1.sent[0].ref;
    s1.drop();
    await sending; // resolves: it will be resent, so there is nothing to report
    expect(app.unsaved).toBe(1);
    const s2 = await reconnect();
    expect(s2.sent[0]).toMatchObject({ type: 'patch', ref, value: 3 });
  });

  it('does not resend an edit the server applied before the socket dropped', async () => {
    const s1 = await online();
    void patch('character', 'c1', '/hp/current', 3);
    s1.drop();
    get.mockImplementation(async () => snapshot({ applied_ref: 1 }));
    const s2 = await reconnect();
    expect(kinds(s2)).toEqual(['presence_sync']);
    expect(app.unsaved).toBe(0);
  });

  it('leaves the replay to the next socket when one drops while the table loads', async () => {
    const s1 = await online();
    s1.drop();
    void patch('character', 'c1', '/hp/current', 3);

    // The first reconnect drops while its snapshot loads; the next opens before that load ends.
    const slow = deferred<StateResponse>(),
      next = deferred<StateResponse>();
    get.mockImplementationOnce(() => slow.promise).mockImplementationOnce(() => next.promise);
    await vi.advanceTimersByTimeAsync(10_000);
    const s2 = latest();
    const opening2 = s2.open();
    s2.drop();
    await vi.advanceTimersByTimeAsync(10_000);
    const s3 = latest();
    const opening3 = s3.open();

    slow.resolve(snapshot());
    await opening2;
    expect(s2.sent).toEqual([]);
    expect(s3.sent).toEqual([]); // not before s3 has its own snapshot

    next.resolve(snapshot());
    await opening3;
    expect(kinds(s3)).toEqual(['patch', 'presence_sync']);
  });
});

describe('sending', () => {
  it('refuses a message while not connected, or while the table is still loading', async () => {
    await expect(ws.send({ type: 'chat', text: 'hi' })).rejects.toThrow('not connected');
    expect(app.toast?.text).toBe('Not connected');

    const loading = deferred<StateResponse>();
    get.mockImplementationOnce(() => loading.promise);
    ws.connect();
    const opening = latest().open();
    await expect(ws.send({ type: 'chat', text: 'hi' })).rejects.toThrow('not connected');
    ws.sendEphemeral({ type: 'typing', active: true }); // goes: it needs no table
    loading.resolve(snapshot());
    await opening;
    expect(kinds(latest())).toEqual(['typing', 'presence_sync']);
  });

  it('drops an ephemeral message while not connected', () => {
    ws.sendEphemeral({ type: 'typing', active: true });
    ws.connect();
    ws.sendEphemeral({ type: 'typing', active: true });
    expect(latest().sent).toEqual([]);
  });

  it('resolves a message on its ack, and rejects it with the error, toasted', async () => {
    const s = await online();
    const chat = ws.send({ type: 'chat', text: 'hi' });
    expect(s.sent[0]).toEqual({ type: 'chat', text: 'hi', ref: 1, client: ws.clientId });
    s.receive({ type: 'ack', ref: 1 });
    await expect(chat).resolves.toBeUndefined();

    const roll = ws.send({ type: 'roll', expr: '2d' });
    s.receive({ type: 'error', ref: 2, message: 'bad dice expression' });
    await expect(roll).rejects.toThrow('bad dice expression');
    expect(app.toast).toEqual({ text: 'bad dice expression', kind: 'error' });
    expect(get).toHaveBeenCalledTimes(1); // a refused message is not a refused edit
  });

  it('toasts an error that answers nothing of ours', async () => {
    const s = await online();
    s.receive({ type: 'error', message: 'invalid JSON' });
    expect(app.toast?.text).toBe('invalid JSON');
  });

  it('reloads the table when an edit is refused, so the sheet shows what was saved', async () => {
    const s = await online();
    const sending = patch('character', 'c1', '/hp/current', 99);
    expect(hp()).toBe(99);
    s.receive({ type: 'error', ref: s.sent[0].ref, message: 'not your character' });
    await expect(sending).resolves.toBeUndefined();
    await vi.waitFor(() => expect(hp()).toBe(5));
    expect(get).toHaveBeenCalledTimes(2);
    expect(app.toast?.text).toBe('not your character');
  });

  it('when the socket drops, rejects messages awaiting an answer but keeps edits', async () => {
    const s = await online();
    const chat = ws.send({ type: 'chat', text: 'hi' });
    const edit = patch('character', 'c1', '/hp/current', 3);
    s.drop();
    await expect(chat).rejects.toThrow('disconnected');
    await expect(edit).resolves.toBeUndefined();
    expect(app.toast?.text).toBe('Not connected');
    expect(app.unsaved).toBe(1);
    expect(app.connected).toBe(false);
  });

  it('does not toast when only edits were awaiting an answer', async () => {
    const s = await online();
    void patch('character', 'c1', '/hp/current', 3);
    s.drop();
    expect(app.toast).toBeNull();
  });
});

describe('reconnecting', () => {
  it('backs off from half a second to ten, and starts over once connected', async () => {
    ws.connect();
    const waits: number[] = [];
    for (let i = 0; i < 7; i++) {
      const before = FakeSocket.all.length;
      latest().drop();
      let waited = 0;
      while (FakeSocket.all.length === before) {
        await vi.advanceTimersByTimeAsync(100);
        waited += 100;
      }
      waits.push(waited);
    }
    expect(waits).toEqual([500, 1000, 2000, 4000, 8000, 10000, 10000]);

    await latest().open();
    latest().drop();
    await vi.advanceTimersByTimeAsync(499);
    const before = FakeSocket.all.length;
    await vi.advanceTimersByTimeAsync(1);
    expect(FakeSocket.all.length).toBe(before + 1);
  });

  it.each([
    [4409, 'signed in on another device'],
    [4401, 'Your session ended'],
  ])('signs out on close code %i, and does not reconnect', async (code, notice) => {
    const s = await online();
    s.drop(code);
    expect(app.me).toBeNull();
    expect(app.loginNotice).toContain(notice);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(FakeSocket.all).toHaveLength(1);
  });

  it('stops for good on logout, and forgets unsent edits', async () => {
    const s = await online();
    void patch('character', 'c1', '/hp/current', 3); // in flight
    ws.disconnect();
    expect(app.unsaved).toBe(0);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(FakeSocket.all).toEqual([s]);
  });

  it('stops for good on logout while waiting to reconnect', async () => {
    const s = await online();
    s.drop();
    void patch('character', 'c1', '/hp/current', 3);
    ws.disconnect();
    expect(app.unsaved).toBe(0);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(FakeSocket.all).toEqual([s]);
  });
});

describe('patches from the server', () => {
  it('skips the echo of our own edit, which we already show', async () => {
    const s = await online();
    void patch('character', 'c1', '/hp/current', 3);
    void patch('character', 'c1', '/hp/current', 4);
    echo(s, s.sent[0]);
    expect(hp()).toBe(4);
  });

  it("applies our echo after someone else's edit to the same field overtook it", async () => {
    // The server applied theirs first and ours last, so ours is what it holds.
    const s = await online();
    void patch('character', 'c1', '/hp/current', 3);
    s.receive({
      type: 'patch',
      entity: 'character',
      id: 'c1',
      path: '/hp',
      value: { current: 7, max: 10 },
      op: 'set',
      revision: 1,
      client: 'other',
      ref: 9,
      merged: false,
    });
    expect(hp()).toBe(7);
    echo(s, s.sent[0], { revision: 2 });
    expect(hp()).toBe(3);
    expect(app.characters.c1.revision).toBe(2);
  });

  it('is not overtaken by an edit elsewhere on the sheet', async () => {
    const s = await online();
    void patch('character', 'c1', '/hp/current', 3);
    void patch('character', 'c1', '/hp/current', 4);
    s.receive({
      type: 'patch',
      entity: 'character',
      id: 'c1',
      path: '/name',
      value: 'Bryony',
      op: 'set',
      revision: 1,
      client: 'other',
      ref: 9,
      merged: false,
    });
    echo(s, s.sent[0]);
    expect(hp()).toBe(4);
  });

  it("applies a merged text edit, which carries other people's typing too", async () => {
    const s = await online();
    void patch('shared', 'v', '/notes', 'hello there', 'text_patch', '@@ -1,5 +1,11 @@\n hello\n+ there\n');
    expect(s.sent[0]).toMatchObject({ op: 'text_patch', patch: '@@ -1,5 +1,11 @@\n hello\n+ there\n' });
    expect(s.sent[0]).not.toHaveProperty('value');
    echo(s, { ...s.sent[0], value: 'hello there, all' }, { op: 'set', merged: true });
    expect((app.shared.v.data as any).notes).toBe('hello there, all');
  });

  it('reloads the table for a sheet it does not have, or a patch that will not apply', async () => {
    const s = await online();
    s.receive({
      type: 'patch',
      entity: 'character',
      id: 'c9',
      path: '/hp/current',
      value: 1,
      op: 'set',
      revision: 1,
      client: 'other',
    });
    expect(get).toHaveBeenCalledTimes(2);
    s.receive({
      type: 'patch',
      entity: 'character',
      id: 'c1',
      path: '/name/first',
      value: 'B',
      op: 'set',
      revision: 1,
      client: 'other',
    });
    expect(get).toHaveBeenCalledTimes(3);
  });
});

describe('patch()', () => {
  it('shows an edit at once, before the server has it', async () => {
    const s = await online();
    const sending = patch('shared', 'v', '/notes', 'now');
    expect((app.shared.v.data as any).notes).toBe('now');
    expect(s.sent[0]).toEqual({
      type: 'patch',
      entity: 'shared',
      id: 'v',
      path: '/notes',
      op: 'set',
      value: 'now',
      ref: 1,
      client: ws.clientId,
    });
    s.receive({ type: 'ack', ref: 1 });
    await expect(sending).resolves.toBeUndefined();
  });

  it('still sends an edit to a sheet this tab has not loaded', async () => {
    const { recordPatcher } = await import('./patch');
    const s = await online();
    void recordPatcher('r1')('/role', 'farmer');
    expect(s.sent[0]).toMatchObject({ entity: 'record', id: 'r1', path: '/role', value: 'farmer' });
  });
});

describe('events from the server', () => {
  it('keeps the rows in step', async () => {
    const s = await online();
    s.receive({ type: 'character_created', character: { id: 'c2', owner: 'Bob', data: {} } });
    s.receive({ type: 'character_owner', id: 'c2', owner: 'Alice' });
    expect(app.characters.c2.owner).toBe('Alice');
    s.receive({ type: 'character_deleted', id: 'c2' });
    expect(app.characters).not.toHaveProperty('c2');

    s.receive({ type: 'shared_created', sheet: { id: 'w', data: {} } });
    s.receive({ type: 'shared_replaced', sheet: { id: 'w', data: { notes: 'new' } } });
    expect((app.shared.w.data as any).notes).toBe('new');
    s.receive({ type: 'shared_deleted', id: 'w' });
    expect(app.shared).not.toHaveProperty('w');

    s.receive({ type: 'record_created', record: { id: 'r1', data: { name: 'Cerys' } } });
    expect(app.records.r1.data.name).toBe('Cerys');
    s.receive({ type: 'record_deleted', id: 'r1' });
    expect(app.records).not.toHaveProperty('r1');
  });

  it('keeps the chat in step', async () => {
    const s = await online();
    s.receive({ type: 'message', message: { id: 1, kind: 'chat', payload: { text: 'hi' } } });
    s.receive({ type: 'message', message: { id: 2, kind: 'roll', payload: {} } });
    s.receive({ type: 'message_updated', message: { id: 2, kind: 'roll', payload: { applied: {} } } });
    expect(app.messages.map((m) => m.id)).toEqual([1, 2]);
    expect(app.messages[1].payload).toEqual({ applied: {} });
    s.receive({ type: 'chat_cleared' });
    expect(app.messages).toEqual([]);
  });

  it('shows who is online, where, and who is typing', async () => {
    const s = await online();
    s.receive({
      type: 'field_presence',
      user: 'Bob',
      client: 'cb',
      entity: 'character',
      id: 'c1',
      path: '/hp/current',
    });
    s.receive({
      type: 'field_presence',
      user: 'Alice',
      client: ws.clientId,
      entity: 'character',
      id: 'c1',
      path: '/name',
    });
    expect(app.fieldPresence).toEqual({ cb: { user: 'Bob', key: 'character/c1/hp/current' } });
    s.receive({ type: 'field_presence', user: 'Bob', client: 'cb', entity: null, id: null, path: null });
    expect(app.fieldPresence).toEqual({});

    s.receive({
      type: 'field_presence',
      user: 'Bob',
      client: 'cb',
      entity: 'character',
      id: 'c1',
      path: '/hp/current',
    });
    s.receive({ type: 'presence', users: ['Alice'] });
    expect(app.online).toEqual(['Alice']);
    expect(app.fieldPresence).toEqual({}); // Bob left

    s.receive({ type: 'typing', user: 'Bob', active: true });
    expect(app.typing.Bob).toBeGreaterThan(Date.now());
    s.receive({ type: 'typing', user: 'Bob', active: false });
    expect(app.typing).toEqual({});
  });
});
