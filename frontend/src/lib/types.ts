import type { PatchOp } from './pointer';

// Mirrors st_vtt/content.py and the character / shared-sheet documents.

export interface Stat {
  id: string;
  label: string;
  min: number;
  max: number;
}
export interface Debility {
  id: string;
  label: string;
  affects: string[];
  text: string;
}
export interface Tier {
  label: string;
  min: number | null;
  max: number | null;
}
export interface RollRules {
  base: string;
  advantage: string;
  disadvantage: string;
  tiers: Tier[];
  mark_xp_on: string[];
}
export interface XpRules {
  level_up_cost: string;
  start_level: number;
  max_xp: number | null;
}
export interface DicePreset {
  label: string;
  expr: string;
}
export interface LoadRules {
  light: number;
  normal: number;
  heavy: number;
}
export interface PackMeta {
  id: string;
  name: string;
  description: string;
  stats: Stat[];
  stat_array: number[];
  debilities: Debility[];
  roll: RollRules;
  xp: XpRules;
  dice_presets: DicePreset[];
  load: LoadRules | null;
  gear_tags: string[];
  hold_names: string[];
}
export interface ModifierOption {
  label: string;
  value: number;
}
export interface Modifier {
  id: string;
  label: string;
  options: ModifierOption[];
  default: number;
  help: string;
}
export interface RollSpec {
  stat: string | string[] | null;
  bonus: number;
  label: string | null;
  modifiers: Modifier[];
}
export interface Hold {
  name: string;
  note: string;
}
/** What a roll's outcome can do to the sheet; the roll card offers each one as a button. */
export type OutcomeAction =
  | { kind: 'xp'; n: number; label: string }
  | { kind: 'hp'; amount: string; label: string }
  | { kind: 'hold'; name: string; n: number; label: string }
  | { kind: 'debility'; id: string | null; label: string }
  | { kind: 'stat'; id: string; delta: number; label: string }
  | { kind: 'sheet_debility'; id: string; label: string };
export interface Outcome {
  text: string;
  apply: OutcomeAction[];
}
export interface Requires {
  level: number | null;
  moves: string[];
}
/** The boxes the book prints: diamonds for carried load, circles for uses and ammo statuses. */
export interface Tracks {
  marks: number | null;
  bulk: number | null;
  uses: number | null;
  statuses: string[];
}
export type TrackKind = 'marks' | 'bulk' | 'uses' | 'statuses';
/** How many boxes of each declared kind are marked. */
export type TrackState = Partial<Record<TrackKind, number>>;
/** A move that lets you take moves from other playbooks. */
export interface Grant {
  from_playbooks: string[];
  n: number;
  exclude_tags: string[];
}
export interface Move {
  id: string;
  name: string;
  trigger: string;
  text: string;
  roll: RollSpec | null;
  outcomes: Record<string, Outcome>;
  hold: Hold | null;
  tracks: Tracks;
  requires: Requires | null;
  tags: string[];
  replaces: string | null;
  /** how the pack groups this move for browsing ('fighting', 'travel'); may be empty */
  themes: string[];
  /** taking this move adds the named insert to the sheet */
  insert: string | null;
  /** taking this move lets you pick moves from other playbooks */
  grants: Grant | null;
  /** a checklist the move carries ("each time you take this move, pick 1"); picks stay picked */
  options: Option[];
  min: number | null;
  max: number | null;
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
export interface Effects {
  moves: string[];
  inserts: string[];
  armor: number | null;
  hp: number | null;
  tags: string[];
}
export interface Option {
  id: string;
  label: string;
  text: string;
  effects: Effects | null;
  tracks: Tracks;
  /** when set, a one-line write-in box appears while this option is selected (the value is its placeholder) */
  write_in: string | null;
  /** a nested sub-choice, revealed only when this option is selected */
  options: Option[];
  min: number | null;
  max: number | null;
  /** prose with no checkbox: a heading, an instruction, or (with tracks) a plain tracker. Its children are always shown. */
  note: boolean;
}
export interface Column {
  id: string;
  label: string;
  type: 'text' | 'number' | 'check' | 'select' | 'dice';
  options: string[];
}
export interface NameList {
  label: string;
  names: string[];
}
/** one row of a `lines` section: pick exactly one option, or write your own */
export interface Line {
  id: string;
  label: string;
  options: Option[];
  write_in: string | null;
}
export type SectionType = 'choose' | 'multichoose' | 'checklist' | 'lines' | 'pips' | 'text' | 'table' | 'names';
export interface Section {
  id: string;
  title: string;
  type: SectionType;
  help: string;
  options: Option[];
  lines: Line[];
  min: number | null;
  max: number | null;
  columns: Column[];
  lists: NameList[];
  placeholder: string;
  required: boolean;
  collapsed: boolean;
  start: unknown;
}
export interface ChooseN {
  n: number;
  from: string[];
}
export interface StartingMoves {
  fixed: string[];
  choose: ChooseN[];
}
export interface Playbook {
  id: string;
  name: string;
  blurb: string;
  hp_max: number;
  damage_die: string;
  armor: number;
  stat_array: number[] | null;
  sections: Section[];
  moves: Move[];
  starting_moves: StartingMoves;
  /** core section names ('gear', 'followers', 'arcana') and/or ids from the pack's `inserts` */
  inserts: string[];
  hold_names: string[];
}
/** one of the half-sheets a playbook comes with: a warband, a spellbook, the ghost you become, ... */
export interface InsertDef {
  id: string;
  name: string;
  kind: string;
  blurb: string;
  description: string;
  sections: Section[];
  moves: Move[];
  starting_moves: StartingMoves;
  hold_names: string[];
}
export const CORE_INSERTS = ['gear', 'followers', 'arcana'] as const;
export interface FollowerRules {
  loyalty_max: number;
  tags: string[];
  costs: string[];
  instincts: string[];
  fields: Column[];
}
export interface Tracker {
  id: string;
  label: string;
  type: 'pips' | 'counter' | 'toggle';
  max: number | null;
}
export interface Arcanum {
  id: string;
  name: string;
  kind: string;
  tags: string[];
  description: string;
  questions: string[];
  prerequisites: string;
  moves: Move[];
  trackers: Tracker[];
}
export interface SheetStat {
  id: string;
  label: string;
  start: number;
  min: number;
  max: number;
  help: string;
}
export interface SharedSheetDef {
  id: string;
  name: string;
  blurb: string;
  auto_create: boolean;
  visibility: 'table' | 'gm';
  stats: SheetStat[];
  sizes: string[];
  size_start: string | null;
  debilities: Debility[];
  sections: Section[];
  moves: Move[];
}
export interface ContentPack {
  pack: PackMeta;
  moves: Record<string, Move[]>;
  playbooks: Playbook[];
  inserts: InsertDef[];
  followers: FollowerRules;
  arcana: Arcanum[];
  shared_sheets: SharedSheetDef[];
}

/** A person, faction or place the campaign remembers. Ties are typed from the
 *  start: in real session notes an NPC is mostly who they are to someone else. */
export interface Tie {
  id: string;
  type: string;
  to: string;
  note: string;
}
export interface RecordDoc {
  kind: string;
  name: string;
  pronouns: string;
  role: string;
  home: string;
  status: string;
  tags: string[];
  ties: Tie[];
  notes: string;
  /** events only: when in the table's own words, a hand-set order, and who was there */
  when?: string;
  order?: number;
  involves?: string[];
  /** GM only — the truth beside what the table believes. Absent for players. */
  secret?: string;
  /** 'table' or 'gm'; a 'gm' record is not sent to players at all. */
  visibility: string;
  created_by: string | null;
}
export interface RecordRow {
  id: string;
  kind: string;
  data: RecordDoc;
  revision: number;
  created_at: number;
  updated_at: number;
}

// ---- documents

export interface Follower {
  id: string;
  name: string;
  tags: string[];
  hp: { current: number; max: number };
  armor: number;
  damage_die: string;
  instinct: string;
  cost: string;
  loyalty: number;
  moves: string;
  gear: string;
  notes: string;
  is_group: boolean;
  members: FollowerMember[];
  fields: Record<string, unknown>;
}
export interface FollowerMember {
  id: string;
  name: string;
  hp: number;
}
export interface ArcanumInstance extends Omit<Arcanum, 'id'> {
  id: string;
  ref: string | null;
  answers: Record<string, string>;
  state: Record<string, number | boolean>;
  notes: string;
}
export interface GearItem {
  id: string;
  name: string;
  tags: string[];
  bulk: number;
  uses: { max: number; used: number } | null;
  /** ammo statuses, marked left to right */
  statuses: string[];
  statuses_marked: number;
  notes: string;
}
export interface CharacterDoc {
  pack_id: string;
  playbook: string;
  name: string;
  pronouns: string;
  look: string;
  stats: Record<string, number>;
  hp: { current: number; max: number };
  armor: number;
  xp: number;
  level: number;
  debilities: Record<string, boolean>;
  moves: {
    taken: string[];
    tracks: Record<string, TrackState>;
    hold: Record<string, number>;
    options: Record<string, string[]>;
  };
  inserts: string[];
  sections: Record<string, unknown>;
  option_tracks: Record<string, Record<string, TrackState>>;
  option_text: Record<string, Record<string, string>>;
  sub_choices: Record<string, Record<string, string[]>>;
  gear: { items: GearItem[] };
  followers: Follower[];
  arcana: ArcanumInstance[];
  custom_moves: Move[];
  notes: string;
  gm_notes?: string;
  creation_done: boolean;
}
export interface CharacterRow {
  id: string;
  owner: string | null;
  revision: number;
  updated_at: number;
  data: CharacterDoc;
}
export interface SharedDoc {
  pack_id: string;
  template: string;
  name: string;
  stats: Record<string, number>;
  size: string;
  debilities: Record<string, boolean>;
  sections: Record<string, unknown>;
  option_tracks: Record<string, Record<string, TrackState>>;
  option_text: Record<string, Record<string, string>>;
  sub_choices: Record<string, Record<string, string[]>>;
  moves: { tracks: Record<string, TrackState>; hold: Record<string, number>; options: Record<string, string[]> };
  notes: string;
  gm_notes?: string;
}
export interface SharedRow {
  id: string;
  template: string;
  revision: number;
  created_at: number;
  updated_at: number;
  data: SharedDoc;
}

export interface User {
  name: string;
  role: 'gm' | 'player';
}

// ---- chat messages (st_vtt/service.py builds the payloads, st_vtt/rolls.py the roll cards')

export interface DieGroup {
  die: string;
  sign: number;
  results: number[];
  kept: number[];
  subtotal: number;
}
export interface RollResult {
  expr: string;
  dice: DieGroup[];
  modifier: number;
  total: number;
}
export interface ChosenModifier {
  id: string;
  label: string;
  option: string;
  value: number;
}
/** A roll card: free-form dice, or a move rolled against a sheet (which adds the optional fields). */
export interface RollPayload {
  type: 'dice' | 'move';
  label: string;
  character: string | null;
  roll: RollResult;
  total: number;
  character_id: string | null;
  shared_id: string | null;
  gm_only: boolean;
  /** outcome index -> who applied it, once someone has */
  applied?: Record<string, { by: string; detail: string }>;
  move_id?: string | null;
  stat?: string | null;
  stat_label?: string | null;
  stat_mod?: number;
  bonus?: number;
  modifiers?: ChosenModifier[];
  mode?: 'normal' | 'advantage' | 'disadvantage' | 'both';
  /** debilities that forced disadvantage */
  auto_disadvantage?: string[];
  tier?: string | null;
  outcome?: string | null;
  mark_xp?: boolean;
  actions?: OutcomeAction[];
}
/** A move shared to the chat. Its outcomes are tier -> text. */
export interface MoveSharePayload {
  move_id: string;
  name: string;
  trigger: string;
  text: string;
  outcomes: Record<string, string>;
  hold: Hold | null;
  roll: RollSpec | null;
  character: string | null;
  character_id: string | null;
}
interface MessageBase {
  id: number;
  ts: number;
  author: string | null;
  visibility: string[] | null;
}
export type ChatMessage = MessageBase & { kind: 'chat' | 'system'; payload: { text: string } };
export type WhisperMessage = MessageBase & { kind: 'whisper'; payload: { text: string; to: string[] } };
export type RequestMessage = MessageBase & {
  kind: 'request';
  payload: {
    to: string;
    label: string;
    stat: string | null;
    /** the move to roll, when the request names one; without it the label says what the roll is for */
    move_id?: string | null;
    /** set by the roll that answers it; a request is answered once */
    answered?: { by: string; roll: number };
  };
};
export type RollMessage = MessageBase & { kind: 'roll'; payload: RollPayload };
export type MoveMessage = MessageBase & { kind: 'move'; payload: MoveSharePayload };
export type Message = ChatMessage | WhisperMessage | RequestMessage | RollMessage | MoveMessage;

// ---- what the server sends over the socket (st_vtt/ws.py, and the renders in st_vtt/service.py)

export type Entity = 'character' | 'shared' | 'record';
/** Someone's cursor: in a field, or (all null) nowhere. */
type FieldFocus = { entity: Entity; id: string; path: string } | { entity: null; id: null; path: null };
export type ServerEvent =
  | { type: 'ack'; ref: number }
  /** `ref` is missing when the server could not read the message at all */
  | { type: 'error'; message: string; ref?: number | null }
  /** `client` and `ref` are null for a change made over REST (an applied roll outcome, say) */
  | {
      type: 'patch';
      entity: Entity;
      id: string;
      path: string;
      value: unknown;
      op: PatchOp;
      revision: number;
      by: string;
      client: string | null;
      ref: number | null;
      merged: boolean;
    }
  | { type: 'message' | 'message_updated'; message: Message }
  | { type: 'chat_cleared' }
  | { type: 'character_created'; character: CharacterRow }
  | { type: 'character_deleted'; id: string }
  | { type: 'character_owner'; id: string; owner: string | null }
  | { type: 'shared_created' | 'shared_replaced'; sheet: SharedRow }
  | { type: 'shared_deleted'; id: string }
  | { type: 'record_created'; record: RecordRow }
  | { type: 'record_deleted'; id: string }
  | { type: 'presence'; users: string[] }
  | ({ type: 'field_presence'; user: string; client: string | null } & FieldFocus)
  | { type: 'typing'; user: string; active: boolean };
export interface StateResponse {
  me: User;
  campaign_name: string;
  users: User[];
  online: string[];
  characters: CharacterRow[];
  shared: SharedRow[];
  records: RecordRow[];
  messages: Message[];
  /** highest ref from this client the server has applied (see lib/sync.ts) */
  applied_ref?: number;
}
