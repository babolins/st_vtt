<script lang="ts">
  /** The places you can be: your sheet, the table's sheets, everyone else's.
   *
   *  A registry rather than a layout — a future NPC directory, relationship graph
   *  or timeline is one more row here, not another section stacked onto a column
   *  that is already nineteen screens tall.
   */
  import { app, isGm, myCharacters, otherCharacters, sharedSheets } from '../lib/state.svelte';
  import { href, isAt, type Place } from '../lib/router.svelte';
  import { userColor } from '../lib/util';

  let { onfind }: { onfind: () => void } = $props();

  const mine = $derived(myCharacters());
  const others = $derived(otherCharacters());
  const online = (name: string | null) => !!name && app.online.includes(name);

  function label(row: { data: { name: string } }, fallback: string) {
    return row.data.name?.trim() || fallback;
  }
</script>

<nav class="rail" aria-label="Places">
  {#if mine.length}
    <div class="group">You</div>
    {#each mine as row (row.id)}
      {@const route: Place = { kind: 'character', id: row.id }}
      <a class="place" class:on={isAt(route)} href={href(route)}>
        <span class="nm">{label(row, 'Your character')}</span>
        <span class="sub">{app.content?.playbooks.find((p) => p.id === row.data.playbook)?.name ?? ''}</span>
      </a>
    {/each}
  {/if}

  {#if sharedSheets().length}
    <div class="group">The table</div>
    {#each sharedSheets() as row (row.id)}
      {@const route: Place = { kind: 'shared', id: row.id }}
      <a class="place" class:on={isAt(route)} href={href(route)}>
        <span class="nm">{label(row, 'Shared sheet')}</span>
      </a>
    {/each}
  {/if}

  {#if others.length}
    <div class="group">{isGm() ? 'Players' : 'Others'}</div>
    {#each others as row (row.id)}
      {@const route: Place = { kind: 'character', id: row.id }}
      <a class="place" class:on={isAt(route)} href={href(route)}>
        <span class="dot" class:lit={online(row.owner)} style="--who: {userColor(row.owner ?? '')}"></span>
        <span class="nm">{label(row, 'Unnamed')}</span>
        <span class="sub">{row.owner ?? ''}</span>
      </a>
    {/each}
  {/if}

  <div class="group">The campaign</div>
  <a class="place" class:on={isAt({ kind: 'people' })} href={href({ kind: 'people' })}>
    <span class="nm">People</span>
    <span class="sub">{Object.values(app.records).filter((r) => r.kind !== 'event').length || 'nobody yet'}</span>
  </a>

  <a class="place" class:on={isAt({ kind: 'graph' })} href={href({ kind: 'graph' })}>
    <span class="nm">Ties</span>
    <span class="sub">who is who to whom</span>
  </a>
  <a class="place" class:on={isAt({ kind: 'timeline' })} href={href({ kind: 'timeline' })}>
    <span class="nm">What happened</span>
    <span class="sub">{Object.values(app.records).filter((r) => r.kind === 'event').length || 'nothing'} so far</span>
  </a>

  <div class="group">Everything</div>
  <a class="place" class:on={isAt({ kind: 'all' })} href={href({ kind: 'all' })}>
    <span class="nm">All sheets</span>
    <span class="sub">one long page</span>
  </a>
  <button class="place find" onclick={onfind}>
    <span class="nm">Moves</span>
    <span class="sub">⌘K</span>
  </button>
</nav>

<style>
  .rail {
    grid-column: 1; grid-row: 2; min-height: 0; overflow-y: auto;
    border-right: 1px solid var(--border); background: var(--bg-elev);
    padding: .4em 0 1em; display: flex; flex-direction: column; gap: .05em;
  }
  .group {
    font-size: .72em; text-transform: uppercase; letter-spacing: .1em; color: var(--fg-muted);
    padding: .8em .8em .2em;
  }
  .group:first-child { padding-top: .3em; }
  .place {
    display: grid; grid-template-columns: auto 1fr; align-items: baseline; gap: 0 .4em;
    padding: .25em .8em; text-decoration: none; color: var(--fg);
    background: transparent; border: 0; border-left: 2px solid transparent; text-align: left; cursor: pointer; width: 100%;
  }
  .place:hover { background: var(--bg-sunken); }
  .place.on { background: var(--accent-soft); border-left-color: var(--accent); }
  .nm { grid-column: 2; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sub { grid-column: 2; font-size: .8em; color: var(--fg-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dot {
    grid-row: span 2; align-self: center; width: .5em; height: .5em; border-radius: 50%;
    background: var(--border);
  }
  .dot.lit { background: var(--who); }
  .find .sub { font-family: var(--mono); }

  @media (max-width: 900px) {
    /* A strip under the header rather than a column beside the sheet. */
    .rail {
      grid-column: 1 / -1; grid-row: 2; flex-direction: row; align-items: center; gap: .3em;
      overflow-x: auto; overflow-y: hidden; padding: .3em .5em;
      border-right: 0; border-bottom: 1px solid var(--border);
    }
    .group { display: none; }
    .place {
      grid-template-columns: auto auto; width: auto; flex: none; border-left: 0; border-radius: 999px;
      border: 1px solid var(--border); padding: .15em .7em;
    }
    .place.on { border-color: var(--accent); }
    .sub { display: none; }
    .nm { grid-column: auto; }
  }
</style>
