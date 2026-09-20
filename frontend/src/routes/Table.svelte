<script lang="ts">
  import { app, isGm, myCharacters, otherCharacters, sharedSheets } from '../lib/state.svelte';
  import { dialogs } from '../lib/dialogs.svelte';
  import Header from './Header.svelte';
  import ChatPanel from '../chat/ChatPanel.svelte';
  import RollDialog from '../chat/RollDialog.svelte';
  import CharacterSheet from '../sheet/CharacterSheet.svelte';
  import SharedSheet from '../sheet/SharedSheet.svelte';
  import NewCharacter from '../gm/NewCharacter.svelte';
  import Collapsible from '../ui/Collapsible.svelte';
  import MoveFinder from '../ui/MoveFinder.svelte';
  import Rail from './Rail.svelte';
  import MovePage from './MovePage.svelte';
  import People from './People.svelte';
  import RecordPage from './RecordPage.svelte';
  import Graph from './Graph.svelte';
  import Timeline from './Timeline.svelte';
  import { land, router } from '../lib/router.svelte';
  import Peek from '../ui/Peek.svelte';

  let chatOpen = $state(false);
  let showNew = $state(false);
  let finding = $state(false);

  // ⌘K anywhere, the way every other dense app opens its search.
  function onkey(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      finding = !finding;
      e.preventDefault();
    }
  }
  const mine = $derived(myCharacters());
  const others = $derived(otherCharacters());
  const unread = $derived(app.messages.length);
  const route = $derived(router.route.place);
  const peeked = $derived(router.route.peek);

  // Land on your own sheet, not on everyone's at once. Only when the URL says
  // nothing — a link someone sent you always wins.
  $effect(() => {
    if (mine.length) land({ kind: 'character', id: mine[0].id });
    else if (sharedSheets().length) land({ kind: 'shared', id: sharedSheets()[0].id });
  });

  const character = $derived(route.kind === 'character' ? app.characters[route.id] : undefined);
  const shared = $derived(route.kind === 'shared' ? app.shared[route.id] : undefined);
</script>

<svelte:window onkeydown={onkey} />

<div class="layout">
  <Header onnew={() => (showNew = true)} onfind={() => (finding = true)} />
  <Rail onfind={() => (finding = true)} />
  <main>
    {#if route.kind === 'character'}
      {#if character}
        <CharacterSheet row={character} />
      {:else}
        <div class="card empty"><p class="muted">That character is not on this table any more.</p></div>
      {/if}
    {:else if route.kind === 'shared'}
      {#if shared}
        <SharedSheet row={shared} />
      {:else}
        <div class="card empty"><p class="muted">That sheet is not on this table any more.</p></div>
      {/if}
    {:else if route.kind === 'move'}
      <MovePage id={route.id} />
    {:else if route.kind === 'people'}
      <People />
    {:else if route.kind === 'record'}
      <RecordPage id={route.id} />
    {:else if route.kind === 'graph'}
      <Graph />
    {:else if route.kind === 'timeline'}
      <Timeline />
    {:else}
      {#each mine as row (row.id)}
        <CharacterSheet {row} />
      {/each}
      {#if mine.length === 0}
        <div class="card empty">
          <p class="muted">You have no character yet.</p>
          <button class="primary" onclick={() => (showNew = true)}>Create a character</button>
        </div>
      {/if}

      {#each sharedSheets() as row (row.id)}
        <SharedSheet {row} />
      {/each}

      {#if others.length}
        <Collapsible id="others" title={isGm() ? 'Player characters' : 'Other characters'} level={2} open={isGm()}>
          {#each others as row (row.id)}
            <CharacterSheet {row} />
          {/each}
        </Collapsible>
      {/if}
    {/if}
  </main>
  <aside class:open={chatOpen}>
    <ChatPanel onclose={() => (chatOpen = false)} />
  </aside>
  {#if peeked}
    <Peek place={peeked} />
  {/if}
  <button class="fab primary" onclick={() => (chatOpen = !chatOpen)} aria-label="toggle chat">💬 <span class="small">{unread}</span></button>
</div>

{#if dialogs.roll}
  <RollDialog req={dialogs.roll} onclose={() => (dialogs.roll = null)} />
{/if}
{#if showNew}
  <NewCharacter onclose={() => (showNew = false)} />
{/if}
{#if finding && app.content}
  <MoveFinder onclose={() => (finding = false)} />
{/if}

<style>
  .layout { display: grid; grid-template-columns: minmax(11em, 14em) minmax(0, 1fr) minmax(20em, 26em); grid-template-rows: auto 1fr; height: 100%; }
  /* No padding above the scrollport: a sheet's sticky header sits flush at the
     top, and there is no strip left over for content to peek through. */
  main { grid-column: 2; grid-row: 2; overflow-y: auto; padding: 0 .75em .75em; }
  main > :global(:first-child) { margin-top: .75em; }
  aside { grid-column: 3; grid-row: 2; border-left: 1px solid var(--border); background: var(--bg-elev); min-height: 0; display: flex; flex-direction: column; }
  .fab { display: none; position: fixed; right: 1em; bottom: 1em; border-radius: 999px; padding: .6em .9em; box-shadow: var(--shadow); z-index: 20; }
  .empty { padding: 1.5em; text-align: center; margin-bottom: .75em; }
  @media (max-width: 900px) {
    /* The rail becomes a strip under the header; the sheet takes the rest. */
    .layout { grid-template-columns: 1fr; grid-template-rows: auto auto 1fr; }
    main { grid-column: 1; grid-row: 3; }
    aside { position: fixed; inset: auto 0 0 0; height: 70vh; transform: translateY(100%); transition: transform .2s; z-index: 30; border-top: 1px solid var(--border); border-left: 0; box-shadow: 0 -4px 20px rgba(0,0,0,.2); }
    aside.open { transform: none; }
    .fab { display: inline-flex; gap: .3em; align-items: center; }
  }
</style>
