<script lang="ts">
  /** A glance at something, without leaving where you are.
   *
   *  A move someone shared, a character whose name came up. It opens over the
   *  current surface, has its own address so a reload keeps it, and closes back
   *  to exactly where you were. This is the interaction a relationship graph
   *  will live or die on: click a node, read the record, keep the graph.
   */
  import { app, canEdit } from '../lib/state.svelte';
  import { allMoves, movesOf } from '../lib/moveindex';
  import { go, peek as peekAt, unpeek, type Place } from '../lib/router.svelte';
  import { openRoll } from '../lib/dialogs.svelte';
  import { send } from '../lib/ws';
  import { fmtMod } from '../lib/util';
  import MoveBody from './MoveBody.svelte';

  let { place }: { place: Place } = $props();

  const content = $derived(app.content!);
  const move = $derived(place.kind === 'move' ? allMoves(content).find((e) => e.move.id === place.id) : undefined);
  const character = $derived(place.kind === 'character' ? app.characters[place.id] : undefined);
  const sheet = $derived(place.kind === 'shared' ? app.shared[place.id] : undefined);

  const pb = $derived(character ? content.playbooks.find((p) => p.id === character.data.playbook) : undefined);
  const mineWithMove = $derived(
    move ? Object.values(app.characters).find((row) => canEdit(row) && movesOf(content, row).some((e) => e.move.id === move.move.id)) : undefined,
  );
  const holders = $derived(move ? Object.values(app.characters).filter((row) => movesOf(content, row).some((e) => e.move.id === move.move.id)) : []);
  const debilities = $derived(content.pack.debilities.filter((d) => character?.data.debilities[d.id]));

  function onkey(e: KeyboardEvent) {
    if (e.key === 'Escape') unpeek();
  }
</script>

<svelte:window onkeydown={onkey} />

<aside class="peek" aria-label="Preview">
  <div class="row bar">
    <span class="muted small">{move ? move.source.label : character ? `${pb?.name ?? ''} · ${character.owner ?? 'unowned'}` : sheet ? 'Shared sheet' : ''}</span>
    <span class="grow"></span>
    <button class="ghost small" onclick={() => go(place)} title="Open this as the page">Open</button>
    <button class="ghost small" onclick={unpeek} title="Close (esc)">✕</button>
  </div>

  {#if move}
    <h3 class="title">{move.move.name}</h3>
    <MoveBody move={move.move} />
    <div class="row acts">
      {#if move.move.roll && mineWithMove}
        <button class="small primary" onclick={() => openRoll({ characterId: mineWithMove.id, sharedId: null, move: move.move })}>Roll</button>
      {/if}
      <button class="small" onclick={() => send({ type: 'share_move', character_id: mineWithMove?.id ?? null, move_id: move.move.id }).catch(() => {})}>Show the table</button>
    </div>
    {#if holders.length}
      <p class="small muted who">
        Taken by
        {#each holders as row, i}<!--
          -->{i > 0 ? ', ' : ' '}<button class="linky" onclick={() => peekAt({ kind: 'character', id: row.id })}>{row.data.name || 'Unnamed'}</button><!--
        -->{/each}
      </p>
    {/if}
  {:else if character}
    <h3 class="title">{character.data.name || 'Unnamed'}</h3>
    <div class="stats">
      {#each content.pack.stats as s}
        <div class="stat"><span class="lbl">{s.label}</span><span class="val">{fmtMod(character.data.stats[s.id] ?? 0)}</span></div>
      {/each}
    </div>
    <p class="vitals small">
      <span>HP <strong>{character.data.hp.current}</strong>/{character.data.hp.max}</span>
      <span>Armor <strong>{character.data.armor}</strong></span>
      <span>Level <strong>{character.data.level}</strong></span>
      <span>XP <strong>{character.data.xp}</strong></span>
    </p>
    {#if debilities.length}<p class="small deb">{debilities.map((d) => d.label).join(' · ')}</p>{/if}
    {#if character.data.look}<p class="small muted">{character.data.look}</p>{/if}
  {:else if sheet}
    <h3 class="title">{sheet.data.name || 'Shared sheet'}</h3>
    <p class="small muted">Open it to edit — a shared sheet is too big to glance at.</p>
  {:else}
    <p class="small muted">Nothing to show here any more.</p>
  {/if}
</aside>

<style>
  .peek {
    grid-column: 3; grid-row: 2; min-height: 0; overflow-y: auto;
    border-left: 1px solid var(--border); background: var(--bg-elev); padding: .5em .75em 1em;
  }
  .bar { gap: .3em; position: sticky; top: -.5em; background: var(--bg-elev); padding: .2em 0 .3em; }
  .title { font-size: 1.15em; margin: .1em 0 .4em; }
  .acts { gap: .4em; margin-top: .7em; }
  .who { margin-top: .7em; }
  .linky { background: none; border: 0; padding: 0; color: var(--accent); cursor: pointer; font: inherit; }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(3.2em, 1fr)); gap: .3em; margin: .2em 0 .5em; }
  .stat { text-align: center; border: 1px solid var(--border); border-radius: 6px; padding: .2em; }
  .lbl { display: block; font-size: .7em; letter-spacing: .06em; color: var(--fg-muted); text-transform: uppercase; }
  .val { font-size: 1.1em; font-weight: 700; }
  .vitals { display: flex; gap: .8em; flex-wrap: wrap; }
  .deb { color: var(--warn); }
  @media (max-width: 900px) {
    /* Narrow: a sheet from the bottom, not a column that squeezes the page. */
    .peek {
      grid-column: 1 / -1; grid-row: 3; position: fixed; inset: auto 0 0 0; height: 70vh; z-index: 30;
      border-left: 0; border-top: 1px solid var(--border); box-shadow: 0 -4px 20px rgba(0, 0, 0, .2);
    }
  }
</style>
