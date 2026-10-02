// Dialogs any component can open: set the request here and the dialog, mounted once in the Table route, shows.

import type { Move } from './types';

export interface RollRequest {
  characterId: string | null;
  /** set instead of characterId when the move belongs to a shared sheet */
  sharedId?: string | null;
  move: Move | null;
  stat?: string | null;
  label?: string;
  bonus?: number;
}

export const dialogs = $state({
  roll: null as RollRequest | null,
});

export function openRoll(req: RollRequest): void {
  dialogs.roll = req;
}
