<script lang="ts">
  import { app } from '../lib/state.svelte';
  import { allMoves } from '../lib/moveindex';
  import { timeShort } from '../lib/util';
  import type { Message, Move } from '../lib/types';
  import MoveBody from '../ui/MoveBody.svelte';

  let { message }: { message: Message } = $props();
  const p = $derived(message.payload);
  // The card carries the move's text, but the pack has the authoritative copy —
  // options, tracks and all — so prefer it and keep one renderer for both.
  const move = $derived.by((): Move => {
    const found = p.move_id && app.content ? allMoves(app.content).find((e) => e.move.id === p.move_id)?.move : undefined;
    return found ?? ({
      id: p.move_id ?? 'shared', name: p.name, trigger: p.trigger ?? '', text: p.text ?? '',
      roll: null, outcomes: p.outcomes ?? {}, hold: p.hold ?? null, tracks: {},
      requires: null, themes: [], tags: [], replaces: null, insert: null, grants: null,
      options: [], min: null, max: null,
    } as unknown as Move);
  });
</script>

<div class="mc">
  <div class="row top">
    <strong>{message.author}</strong>
    {#if p.character}<span class="muted small">as {p.character}</span>{/if}
    <span class="muted small">shared a move</span>
    <span class="grow"></span>
    <span class="muted small">{timeShort(message.ts)}</span>
  </div>
  <div class="name">{move.name}</div>
  <MoveBody {move} />
</div>

<style>
  .mc { border: 1px solid var(--border); border-left: 4px solid var(--accent); border-radius: 6px; padding: .4em .6em; background: var(--bg); }
  .top { gap: .4em; }
  .name { font-weight: 600; margin: .15em 0; }
</style>
