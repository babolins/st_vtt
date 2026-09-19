// Mirrors st_vtt/content.py and the character / shared-sheet documents.

export interface Stat { id: string; label: string; min: number; max: number }
export interface Debility { id: string; label: string; affects: string[]; text: string }
export interface Tier { label: string; min: number | null; max: number | null }
export interface RollRules { base: string; advantage: string; disadvantage: string; tiers: Tier[]; mark_xp_on: string[] }
export interface XpRules { level_up_cost: string; start_level: number; max_xp: number | null }
export interface DicePreset { label: string; expr: string }
export interface LoadRules { light: number; normal: number; heavy: number }
export interface PackMeta {
  id: string; name: string; description: string; stats: Stat[]; stat_array: number[];
  debilities: Debility[]; roll: RollRules; xp: XpRules; dice_presets: DicePreset[];
  load: LoadRules | null; gear_tags: string[]; hold_names: string[];
}
export interface ModifierOption { label: string; value: number }
export interface Modifier { id: string; label: string; options: ModifierOption[]; default: number; help: string }
export interface RollSpec { stat: string | string[] | null; bonus: number; label: string | null; modifiers: Modifier[] }
export interface Hold { name: string; note: string }
/** What a roll's outcome can do to the sheet; the roll card offers each one as a button. */
export type OutcomeAction =
  | { kind: 'xp'; n: number; label: string }
  | { kind: 'hp'; amount: string; label: string }
  | { kind: 'hold'; name: string; n: number; label: string }
  | { kind: 'debility'; id: string | null; label: string }
  | { kind: 'stat'; id: string; delta: number; label: string }
  | { kind: 'sheet_debility'; id: string; label: string };
export interface Outcome { text: string; apply: OutcomeAction[] }
export interface Requires { level: number | null; moves: string[] }
/** The boxes the book prints: diamonds for carried load, circles for uses and ammo statuses. */
export interface Tracks { marks: number | null; bulk: number | null; uses: number | null; statuses: string[] }
export type TrackKind = 'marks' | 'bulk' | 'uses' | 'statuses';
/** How many boxes of each declared kind are marked. */
export type TrackState = Partial<Record<TrackKind, number>>;
/** A move that lets you take moves from other playbooks. */
export interface Grant { from_playbooks: string[]; n: number; exclude_tags: string[] }
export interface Move {
  id: string; name: string; trigger: string; text: string; roll: RollSpec | null;
  outcomes: Record<string, Outcome>; hold: Hold | null; tracks: Tracks;
  requires: Requires | null; tags: string[]; replaces: string | null;
  /** how the pack groups this move for browsing ('fighting', 'travel'); may be empty */
  themes: string[];
  /** taking this move adds the named insert to the sheet */
  insert: string | null;
  /** taking this move lets you pick moves from other playbooks */
  grants: Grant | null;
  /** a checklist the move carries ("each time you take this move, pick 1"); picks stay picked */
  options: Option[]; min: number | null; max: number | null;
}

/** Boxes declared, paired with how many are marked; what Tracks.svelte renders. */
export function trackKinds(t: Tracks | undefined): { kind: TrackKind; boxes: number; labels?: string[] }[] {
  if (!t) return [];
  const out: { kind: TrackKind; boxes: number; labels?: string[] }[] = [];
  if (t.marks) out.push({ kind: 'marks', boxes: t.marks });
  if (t.bulk) out.push({ kind: 'bulk', boxes: t.bulk });
  if (t.uses) out.push({ kind: 'uses', boxes: t.uses });
  if (t.statuses?.length) out.push({ kind: 'statuses', boxes: t.statuses.length, labels: t.statuses });
  return out;
}
export interface Effects { moves: string[]; inserts: string[]; armor: number | null; hp: number | null; tags: string[] }
export interface Option {
  id: string; label: string; text: string; effects: Effects | null; tracks: Tracks;
  /** when set, a one-line write-in box appears while this option is selected (the value is its placeholder) */
  write_in: string | null;
  /** a nested sub-choice, revealed only when this option is selected */
  options: Option[]; min: number | null; max: number | null;
  /** prose with no checkbox: a heading, an instruction, or (with tracks) a plain tracker. Its children are always shown. */
  note: boolean;
}
export interface Column { id: string; label: string; type: 'text' | 'number' | 'check' | 'select' | 'dice'; options: string[] }
export interface NameList { label: string; names: string[] }
/** one row of a `lines` section: pick exactly one option, or write your own */
export interface Line { id: string; label: string; options: Option[]; write_in: string | null }
export type SectionType = 'choose' | 'multichoose' | 'checklist' | 'lines' | 'pips' | 'text' | 'table' | 'names';
export interface Section {
  id: string; title: string; type: SectionType; help: string; options: Option[]; lines: Line[];
  min: number | null; max: number | null; columns: Column[]; lists: NameList[];
  placeholder: string; required: boolean; collapsed: boolean; start: unknown;
}
export interface ChooseN { n: number; from: string[] }
export interface StartingMoves { fixed: string[]; choose: ChooseN[] }
export interface Playbook {
  id: string; name: string; blurb: string; hp_max: number; damage_die: string; armor: number;
  stat_array: number[] | null; sections: Section[]; moves: Move[]; starting_moves: StartingMoves;
  /** core section names ('gear', 'followers', 'arcana') and/or ids from the pack's `inserts` */
  inserts: string[]; hold_names: string[];
}
/** one of the half-sheets a playbook comes with: a warband, a spellbook, the ghost you become, ... */
export interface InsertDef {
  id: string; name: string; kind: string; blurb: string; description: string;
  sections: Section[]; moves: Move[]; starting_moves: StartingMoves; hold_names: string[];
}
export const CORE_INSERTS = ['gear', 'followers', 'arcana'] as const;
export interface FollowerRules { loyalty_max: number; tags: string[]; costs: string[]; instincts: string[]; fields: Column[] }
export interface Tracker { id: string; label: string; type: 'pips' | 'counter' | 'toggle'; max: number | null }
export interface Arcanum {
  id: string; name: string; kind: string; tags: string[]; description: string; questions: string[];
  prerequisites: string; moves: Move[]; trackers: Tracker[];
}
export interface SheetStat { id: string; label: string; start: number; min: number; max: number; help: string }
export interface SharedSheetDef {
  id: string; name: string; blurb: string; auto_create: boolean; visibility: 'table' | 'gm';
  stats: SheetStat[]; sizes: string[]; size_start: string | null;
  debilities: Debility[]; sections: Section[]; moves: Move[];
}
export interface ContentPack {
  pack: PackMeta; moves: Record<string, Move[]>; playbooks: Playbook[]; inserts: InsertDef[];
  followers: FollowerRules; arcana: Arcanum[]; shared_sheets: SharedSheetDef[];
}

// ---- documents

export interface Follower {
  id: string; name: string; tags: string[]; hp: { current: number; max: number }; armor: number;
  damage_die: string; instinct: string; cost: string; loyalty: number; moves: string; gear: string;
  notes: string; is_group: boolean; members: { name: string; hp: number }[]; fields: Record<string, unknown>;
}
export interface ArcanumInstance extends Omit<Arcanum, 'id'> {
  id: string; ref: string | null; answers: Record<string, string>; state: Record<string, number | boolean>; notes: string;
}
export interface GearItem {
  id: string; name: string; tags: string[]; bulk: number;
  uses: { max: number; used: number } | null;
  /** ammo statuses, marked left to right */
  statuses: string[]; statuses_marked: number;
  notes: string;
}
export interface CharacterDoc {
  pack_id: string; playbook: string; name: string; pronouns: string; look: string;
  stats: Record<string, number>; hp: { current: number; max: number }; armor: number; xp: number; level: number;
  debilities: Record<string, boolean>;
  moves: { taken: string[]; tracks: Record<string, TrackState>; hold: Record<string, number>; options: Record<string, string[]> };
  inserts: string[];
  sections: Record<string, unknown>;
  option_tracks: Record<string, Record<string, TrackState>>;
  option_text: Record<string, Record<string, string>>;
  sub_choices: Record<string, Record<string, string[]>>;
  gear: { items: GearItem[] };
  followers: Follower[]; arcana: ArcanumInstance[]; custom_moves: Move[];
  notes: string; gm_notes?: string; creation_done: boolean;
}
export interface CharacterRow { id: string; owner: string | null; revision: number; updated_at: number; data: CharacterDoc }
export interface SharedDoc {
  pack_id: string; template: string; name: string; stats: Record<string, number>; size: string; debilities: Record<string, boolean>;
  sections: Record<string, unknown>; option_tracks: Record<string, Record<string, TrackState>>;
  option_text: Record<string, Record<string, string>>; sub_choices: Record<string, Record<string, string[]>>;
  moves: { tracks: Record<string, TrackState>; hold: Record<string, number>; options: Record<string, string[]> };
  notes: string; gm_notes?: string;
}
export interface SharedRow { id: string; template: string; revision: number; created_at: number; updated_at: number; data: SharedDoc }

export interface User { name: string; role: 'gm' | 'player' }
export interface Message {
  id: number; ts: number; author: string | null; kind: 'chat' | 'whisper' | 'roll' | 'system' | 'request' | 'move';
  payload: any; visibility: string[] | null;
}
export interface StateResponse {
  me: User; campaign_name: string; users: User[]; online: string[];
  characters: CharacterRow[]; shared: SharedRow[]; messages: Message[];
}
