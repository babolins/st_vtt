// Bookkeeping for optimistic sheet patches, kept free of sockets and state so it can be tested.
//
// A client applies its own patches at once and the server applies everyone's in arrival order,
// echoing each to every client (the sender included) before acking it. Two rules keep clients
// on the server's value:
//  - Our own echo is normally skipped, as we already show it. But if someone else's patch to an
//    overlapping path reached us while ours was in flight, the server applied theirs first and
//    ours last, while we showed ours and then theirs; so the echo is applied.
//  - Patches made while disconnected, or in flight when the socket dropped, wait in an outbox
//    (keeping their refs) and are replayed in order on reconnect. The server acks, without
//    applying, any ref it has already applied for this client.

import type { PatchOp } from './pointer';

export interface PatchEntry {
  ref: number;
  /** the message as sent, less `ref` and `client` */
  msg: Record<string, unknown>;
  entity: string;
  id: string | null;
  path: string;
  op: PatchOp;
  /** what was applied locally, to re-apply on top of a fresh snapshot (for text_patch, the merged text) */
  value: unknown;
  /** who made it: an outbox is never replayed as someone else */
  user: string;
  /** another client's patch to an overlapping path arrived while this was in flight */
  overtaken: boolean;
}

/** Equal, or one a `/`-bounded prefix of the other (the root, '', is a prefix of everything). */
export function pathsOverlap(a: string, b: string): boolean {
  return a === b || a.startsWith(b + '/') || b.startsWith(a + '/');
}

/**
 * Whether to apply the server's echo of our own patch. Merged results (text_patch) always are:
 * they carry other people's edits too.
 */
export function applyEcho(entry: PatchEntry | undefined, merged: boolean): boolean {
  return merged || !!entry?.overtaken;
}

export class PatchQueue {
  private inflight = new Map<number, PatchEntry>();
  private outbox: PatchEntry[] = [];

  /** Waiting to be sent: made while disconnected, or in flight when the socket dropped. */
  get unsaved(): number {
    return this.outbox.length;
  }

  queue(entry: PatchEntry): void {
    this.outbox.push(entry);
  }

  sent(entry: PatchEntry): void {
    this.inflight.set(entry.ref, entry);
  }

  get(ref: number): PatchEntry | undefined {
    return this.inflight.get(ref);
  }

  /** Acked or refused: done with it. */
  settle(ref: number): PatchEntry | undefined {
    const e = this.inflight.get(ref);
    this.inflight.delete(ref);
    return e;
  }

  /** Someone else's patch arrived. */
  overtake(entity: string, id: string | null, path: string): void {
    for (const e of this.inflight.values()) {
      if (e.entity === entity && e.id === id && pathsOverlap(e.path, path)) e.overtaken = true;
    }
  }

  /** The socket dropped: in-flight patches go back to the outbox, ahead of anything made since. */
  disconnected(): void {
    const back = [...this.inflight.values()];
    this.inflight.clear();
    for (const e of back) e.overtaken = false;
    this.outbox = [...back, ...this.outbox].sort((a, b) => a.ref - b.ref);
  }

  /**
   * After loading a fresh snapshot: drop outbox entries the snapshot already includes (refs at or
   * below `appliedRef`) or made by someone other than `user`. Returns every patch still to land,
   * in flight or queued, in order, to re-apply on top of the snapshot.
   */
  rebase(appliedRef: number, user: string | undefined): PatchEntry[] {
    this.outbox = this.outbox.filter((e) => e.ref > appliedRef && e.user === user);
    const inflight = [...this.inflight.values()].filter((e) => e.ref > appliedRef);
    return [...inflight, ...this.outbox].sort((a, b) => a.ref - b.ref);
  }

  /** Take the outbox to send, in order. The caller passes each to `sent` as it goes. */
  drain(): PatchEntry[] {
    const out = this.outbox;
    this.outbox = [];
    return out;
  }

  clear(): void {
    this.inflight.clear();
    this.outbox = [];
  }
}
