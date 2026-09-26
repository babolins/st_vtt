<script lang="ts">
  import type { CharacterDoc, Move, SharedDoc, TrackKind, TrackState } from '../../lib/types';
  import type { Patcher } from '../../lib/patch';
  import { openRoll } from '../../lib/dialogs.svelte';
  import { send } from '../../lib/ws';
  import Tracks from '../../ui/Tracks.svelte';
  import MoveBody from '../../ui/MoveBody.svelte';

  let {
    move, characterId = null, sharedId = null, editable = false, tracks, ontrack, onremove, compact = false, canRoll = true,
    doc, p,
  }: {
    move: Move; characterId?: string | null; sharedId?: string | null; editable?: boolean;
    tracks?: TrackState; ontrack?: (kind: TrackKind, v: number) => void;
    onremove?: () => void; compact?: boolean; canRoll?: boolean;
    /** the sheet this card sits on, when the move carries its own checklist */
    doc?: CharacterDoc | SharedDoc; p?: Patcher;
  } = $props();
  // svelte-ignore state_referenced_locally
  let open = $state(!compact);
</script>

<div class="move" class:compact>
  <div class="row head">
    <button class="ghost name" onclick={() => (open = !open)}>{move.name}</button>
    {#each move.tags as t}<span class="tag">{t}</span>{/each}
    {#if move.requires?.level}<span class="tag">lvl {move.requires.level}+</span>{/if}
    <span class="grow"></span>
    {#if ontrack}
      <Tracks tracks={move.tracks} state={tracks} onchange={ontrack} disabled={!editable} />
    {/if}
    <button class="ghost small" title="Post this move to the chat" onclick={() => send({ type: 'share_move', character_id: characterId, move_id: move.id }).catch(() => {})}>Share</button>
    {#if move.roll && canRoll}
      <button class="small primary" onclick={() => openRoll({ characterId, sharedId, move })}>Roll</button>
    {/if}
    {#if onremove && editable}<button class="ghost small danger" onclick={onremove} title="Remove">✕</button>{/if}
  </div>
  {#if open}
    <div class="body">
      <MoveBody {move} {doc} {p} {editable} />
    </div>
  {/if}
</div>

<style>
  .move { border: 1px solid var(--border); border-radius: 6px; padding: .3em .6em; margin: .3em 0; background: var(--bg); }
  .head { gap: .35em; }
  .name { font-weight: 600; padding: .1em .2em; color: var(--fg); text-align: left; }
  .body { padding: .2em 0 .3em; }
</style>
