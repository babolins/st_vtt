<script lang="ts">
  /** A move at its own address, so it can be linked to — from chat, from a
   *  search result, from anywhere. Shows the printed move and who at this table
   *  has taken it, which is the question that usually follows "what does it say?" */
  import { app } from '../lib/state.svelte';
  import { allMoves, movesOf } from '../lib/moveindex';
  import { go } from '../lib/router.svelte';
  import { openRoll } from '../lib/dialogs.svelte';
  import { send } from '../lib/ws';
  import MoveBody from '../ui/MoveBody.svelte';

  let { id }: { id: string } = $props();

  const content = $derived(app.content!);
  const found = $derived(allMoves(content).find((e) => e.move.id === id));
  const holders = $derived(
    found ? Object.values(app.characters).filter((row) => movesOf(content, row).some((e) => e.move.id === id)) : [],
  );
  const mineWithIt = $derived(holders.find((row) => row.owner === app.me?.name));
</script>

<div class="card page">
  {#if found}
    <div class="row head">
      <h2 class="name">{found.move.name}</h2>
      <span class="muted small">{found.source.label}</span>
      <span class="grow"></span>
      {#if found.move.roll && mineWithIt}
        <button class="small primary" onclick={() => openRoll({ characterId: mineWithIt.id, sharedId: null, move: found.move })}>Roll</button>
      {/if}
      <button class="small" onclick={() => send({ type: 'share_move', character_id: mineWithIt?.id ?? null, move_id: id }).catch(() => {})}>
        Show the table
      </button>
    </div>
    <MoveBody move={found.move} />
    {#if holders.length}
      <p class="small muted who">
        Taken by
        {#each holders as row, i}<!--
          -->{i > 0 ? ', ' : ' '}<a href="#/c/{row.id}">{row.data.name || 'Unnamed'}</a><!--
        -->{/each}
      </p>
    {/if}
  {:else}
    <p class="muted">No move with the id <code>{id}</code> in this pack.</p>
    <button class="small" onclick={() => go({ kind: 'all' })}>Back to everything</button>
  {/if}
</div>

<style>
  .page { padding: .75em 1em 1em; max-width: 46em; }
  .head { gap: .5em; align-items: baseline; margin-bottom: .5em; }
  .name { font-size: 1.3em; }
  .who { margin-top: .8em; }
</style>
