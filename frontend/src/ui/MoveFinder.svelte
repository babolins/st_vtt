<script lang="ts">
  /** Find a move: type, or browse by letter, theme or character.
   *
   *  Everything here runs against the pack already in memory — no index, no round
   *  trip. Results are keyboard-first, because during play this is opened mid-
   *  sentence: ↑↓ to walk, Enter to read, ⌘Enter to roll, ⇧Enter to show the table.
   */
  import { app, isGm, myCharacters } from '../lib/state.svelte';
  import { allMoves, alphabetical, byTheme, movesOf, type IndexedMove } from '../lib/moveindex';
  import { search, splitMarks } from '../lib/movesearch';
  import { openRoll } from '../lib/dialogs.svelte';
  import { send } from '../lib/ws';
  import { canEdit } from '../lib/state.svelte';
  import MoveBody from './MoveBody.svelte';

  let { onclose }: { onclose: () => void } = $props();

  type Scope = 'mine' | 'table' | 'all';
  type View = 'az' | 'theme' | 'character';

  let query = $state('');
  let scope = $state<Scope>(myCharacters().length ? 'mine' : 'all');
  let view = $state<View>('az');
  let cursor = $state(0);
  let input: HTMLInputElement | undefined = $state();

  const content = $derived(app.content!);
  const mine = $derived(myCharacters());
  // A GM browses everyone's sheets; a player browses their own and the table's.
  const characters = $derived(isGm() ? Object.values(app.characters) : [...mine, ...Object.values(app.characters).filter((c) => !canEdit(c))]);

  const pool = $derived.by((): IndexedMove[] => {
    if (scope === 'all') return allMoves(content);
    if (scope === 'table') return allMoves(content).filter((e) => e.source.kind === 'group' || e.source.kind === 'shared');
    return mine.flatMap((row) => movesOf(content, row));
  });

  const hits = $derived(query.trim() ? search(pool, query) : []);

  interface Group { label: string; note?: string; entries: IndexedMove[] }
  const groups = $derived.by((): Group[] => {
    if (query.trim()) return [{ label: `${hits.length} ${hits.length === 1 ? 'match' : 'matches'}`, entries: hits.map((h) => h.entry) }];
    if (view === 'theme') {
      return byTheme(pool).map((g) => ({ label: g.label, note: g.authored ? undefined : 'no themes authored — grouped by source', entries: g.entries }));
    }
    if (view === 'character') {
      return characters.map((row) => ({ label: `${row.data.name || 'Unnamed'} · ${row.owner ?? 'unowned'}`, entries: movesOf(content, row) }));
    }
    return alphabetical(pool);
  });

  const flat = $derived(groups.flatMap((g) => g.entries));
  const selected = $derived(flat[Math.min(cursor, flat.length - 1)]);
  const hitFor = $derived(query.trim() ? hits[Math.min(cursor, hits.length - 1)] : undefined);
  // Rolling needs a sheet the move belongs to; the first of mine that has it.
  const rollOn = $derived(selected ? mine.find((row) => movesOf(content, row).some((e) => e.move.id === selected.move.id)) ?? mine[0] : undefined);

  $effect(() => {
    query; scope; view;
    cursor = 0;
  });
  $effect(() => {
    input?.focus();
  });

  function roll() {
    if (!selected?.move.roll || !rollOn) return;
    openRoll({ characterId: rollOn.id, sharedId: null, move: selected.move });
    onclose();
  }

  function share() {
    if (!selected) return;
    send({ type: 'share_move', character_id: rollOn?.id ?? null, move_id: selected.move.id }).catch(() => {});
    onclose();
  }

  function onkey(e: KeyboardEvent) {
    if (e.key === 'Escape') return onclose();
    if (e.key === 'ArrowDown') { cursor = Math.min(cursor + 1, flat.length - 1); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { cursor = Math.max(cursor - 1, 0); e.preventDefault(); }
    else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { roll(); e.preventDefault(); }
    else if (e.key === 'Enter' && e.shiftKey) { share(); e.preventDefault(); }
  }
</script>

<svelte:window onkeydown={onkey} />

<div class="scrim" role="presentation" onclick={onclose}></div>
<div class="finder" role="dialog" aria-label="Find a move" aria-modal="true">
  <div class="row bar">
    <input bind:this={input} bind:value={query} placeholder="Find a move — name, or what it's about" aria-label="Search moves" />
    <div class="seg" role="group" aria-label="Which moves">
      {#each [['mine', 'Mine'], ['table', 'Table'], ['all', 'Everything']] as [id, label]}
        <button class="small" class:on={scope === id} onclick={() => (scope = id as Scope)}>{label}</button>
      {/each}
    </div>
  </div>

  {#if !query.trim()}
    <div class="row bar sub">
      <div class="seg" role="group" aria-label="Grouping">
        {#each [['az', 'A–Z'], ['theme', 'Theme'], ['character', 'Character']] as [id, label]}
          <button class="small" class:on={view === id} onclick={() => (view = id as View)}>{label}</button>
        {/each}
      </div>
      <span class="grow"></span>
      <span class="muted small">{pool.length} moves</span>
    </div>
  {/if}

  <div class="panes">
    <div class="results">
      {#each groups as g}
        {#if g.entries.length}
          <div class="ghead">
            {g.label}
            {#if g.note}<span class="muted small note">{g.note}</span>{/if}
          </div>
          {#each g.entries as e}
            {@const i = flat.indexOf(e)}
            <button class="hit" class:sel={i === cursor} onclick={() => (cursor = i)} onmouseenter={() => (cursor = i)}>
              <span class="hname">
                {#if hitFor && flat[cursor] === e && hitFor.marks.length}
                  {#each splitMarks(e.move.name, hitFor.marks) as part}<span class:mark={part.hit}>{part.text}</span>{/each}
                {:else}{e.move.name}{/if}
              </span>
              <span class="hwhere muted small">{e.source.label}</span>
              {#if query.trim()}
                {@const h = hits.find((x) => x.entry === e)}
                {#if h?.snippet}<span class="snip muted small">{h.snippet}</span>{/if}
              {:else if e.move.trigger}
                <span class="snip muted small">{e.move.trigger}</span>
              {/if}
            </button>
          {/each}
        {/if}
      {/each}
      {#if !flat.length}
        <p class="muted empty">Nothing matches “{query}”.</p>
      {/if}
    </div>

    <div class="preview">
      {#if selected}
        <div class="pname">{selected.move.name}</div>
        <div class="muted small pwhere">{selected.source.label}</div>
        <MoveBody move={selected.move} />
        <div class="row pactions">
          {#if selected.move.roll && rollOn}<button class="small primary" onclick={roll}>Roll</button>{/if}
          <button class="small" onclick={share}>Show the table</button>
        </div>
      {/if}
    </div>
  </div>

  <div class="row keys muted small">
    <span><span class="kbd">↑↓</span> walk</span>
    <span><span class="kbd">⌘↵</span> roll</span>
    <span><span class="kbd">⇧↵</span> show the table</span>
    <span><span class="kbd">esc</span> close</span>
  </div>
</div>

<style>
  .scrim { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); z-index: 40; }
  .finder {
    position: fixed; z-index: 41; inset: 4vh 50% auto auto; transform: translateX(50%);
    width: min(62rem, 94vw); max-height: 88vh; display: flex; flex-direction: column;
    background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow);
  }
  .bar { padding: .5em .6em; gap: .5em; border-bottom: 1px solid var(--border); }
  .bar.sub { padding: .35em .6em; }
  input { flex: 1; font-size: 1.05em; }
  .seg { display: inline-flex; gap: .15em; }
  .seg .on { background: var(--accent); color: var(--accent-fg); border-color: var(--accent); }
  .panes { display: grid; grid-template-columns: minmax(0, 20em) minmax(0, 1fr); min-height: 0; flex: 1; }
  .results { overflow-y: auto; border-right: 1px solid var(--border); padding-bottom: .5em; }
  .ghead {
    position: sticky; top: 0; background: var(--bg-sunken); padding: .25em .7em;
    font-size: .78em; text-transform: uppercase; letter-spacing: .08em; color: var(--fg-muted); z-index: 1;
  }
  .note { text-transform: none; letter-spacing: 0; margin-left: .5em; }
  .hit {
    display: grid; grid-template-columns: 1fr auto; gap: 0 .5em; width: 100%; text-align: left;
    background: transparent; border: 0; border-radius: 0; padding: .3em .7em; cursor: pointer;
  }
  .hit.sel { background: var(--accent-soft); }
  .hname { font-weight: 600; }
  .mark { text-decoration: underline; text-underline-offset: 2px; }
  .hwhere { justify-self: end; }
  .snip { grid-column: 1 / -1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .preview { overflow-y: auto; padding: .7em .9em; min-height: 0; }
  .pname { font-size: 1.15em; font-weight: 600; }
  .pwhere { margin-bottom: .5em; }
  .pactions { margin-top: .8em; gap: .4em; }
  .keys { gap: 1em; padding: .35em .7em; border-top: 1px solid var(--border); }
  .empty { padding: 1em .7em; }
  @media (max-width: 760px) {
    .panes { grid-template-columns: minmax(0, 1fr); }
    .preview { display: none; }
  }
</style>
