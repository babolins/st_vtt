import { applyPointer, type PatchOp } from './pointer';
import { app } from './state.svelte';
import { send } from './ws';

export type Entity = 'character' | 'shared' | 'record';

/**
 * Optimistically apply a patch locally, then send it. Errors are toasted by ws.ts and the entity refetched.
 * For op 'text_patch', `value` is the locally merged text and `patchText` the diff-match-patch patch to send.
 */
export function patch(entity: Entity, id: string | null, path: string, value: unknown, op: PatchOp = 'set', patchText?: string): Promise<void> {
  const target = entity === 'character' ? app.characters[id!] : entity === 'record' ? app.records[id!] : app.shared[id!];
  if (target) {
    try { applyPointer(target.data, path, value, op); } catch (e) { console.warn('local patch failed', e); }
  }
  const msg: Record<string, unknown> = { type: 'patch', entity, id, path, op };
  if (op === 'text_patch') msg.patch = patchText;
  else msg.value = value;
  return send(msg).catch(() => {});
}

export type Patcher = (path: string, value: unknown, op?: PatchOp, patchText?: string) => Promise<void>;

export function characterPatcher(id: string): Patcher {
  return (path, value, op = 'set', patchText) => patch('character', id, path, value, op, patchText);
}
export function sharedPatcher(id: string): Patcher {
  return (path, value, op = 'set', patchText) => patch('shared', id, path, value, op, patchText);
}
export function recordPatcher(id: string): Patcher {
  return (path, value, op = 'set', patchText) => patch('record', id, path, value, op, patchText);
}

/** Context shared by a sheet with its field components (set via setContext('sheet', ...)). */
export interface SheetContext { entity: Entity; id: string; p: Patcher }
export const SHEET = 'sheet';
