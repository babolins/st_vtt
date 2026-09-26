<script lang="ts">
  /** What happened, in the order it happened.
   *
   *  Time at this table is entirely relative — “nine years ago”, “a little before
   *  Glenys was born”, “last spring”. There is not one absolute date in the
   *  campaign's notes, so an event says *when* in its own words and sorts by a
   *  number nobody has to think about: move it up, move it down.
   */
  import { api } from '../lib/api';
  import { app, isGm, records, toast } from '../lib/state.svelte';
  import { recordPatcher } from '../lib/patch';
  import { peek } from '../lib/router.svelte';
  import type { RecordRow } from '../lib/types';
  import DebouncedText from '../ui/DebouncedText.svelte';
  import Markdown from '../ui/Markdown.svelte';

  let editing = $state<string | null>(null);
  let newTitle = $state('');
  let busy = $state(false);

  const events = $derived(
    records()
      .filter((r) => r.kind === 'event')
      .sort((a, b) => (a.data.order ?? 0) - (b.data.order ?? 0) || a.data.name.localeCompare(b.data.name)),
  );
  const people = $derived([
    ...Object.values(app.characters).map((c) => ({ id: c.id, name: c.data.name || 'Unnamed', character: true })),
    ...records().filter((r) => r.kind !== 'event').map((r) => ({ id: r.id, name: r.data.name, character: false })),
  ]);
  const nameOf = (id: string) => app.records[id]?.data.name ?? app.characters[id]?.data.name ?? id;

  async function add() {
    if (!newTitle.trim() || busy) return;
    busy = true;
    try {
      const row = await api.post<RecordRow>('/api/records', { kind: 'event', name: newTitle.trim() });
      // New events land at the end; the table nudges them into place.
      const last = events[events.length - 1]?.data.order ?? 0;
      await recordPatcher(row.id)('/order', last + 10);
      newTitle = '';
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally {
      busy = false;
    }
  }

  /** Swap this event with its neighbour, which is all “earlier” and “later” mean here. */
  async function move(i: number, by: -1 | 1) {
    const a = events[i];
    const b = events[i + by];
    if (!a || !b) return;
    const ao = a.data.order ?? 0;
    const bo = b.data.order ?? 0;
    await recordPatcher(a.id)('/order', bo === ao ? ao + by : bo);
    await recordPatcher(b.id)('/order', ao === bo ? bo - by : ao);
  }

  async function involve(row: RecordRow, id: string) {
    if (!id || row.data.involves?.includes(id)) return;
    await recordPatcher(row.id)('/involves', id, 'list_add');
  }
</script>

<div class="card page">
  <div class="row head">
    <h2>What happened</h2>
    <span class="muted small">{events.length} {events.length === 1 ? 'event' : 'events'}, earliest first</span>
    <span class="grow"></span>
    <input class="new" bind:value={newTitle} placeholder="Something that happened…" onkeydown={(e) => e.key === 'Enter' && add()} />
    <button class="small primary" onclick={add} disabled={!newTitle.trim() || busy}>Add</button>
  </div>

  {#if !events.length}
    <p class="muted empty">Nothing written down yet. “Pedr bested Ivan”, “the Forest Folk disappeared” — say when in whatever words the table uses, and order them by hand.</p>
  {:else}
    <ol class="line">
      {#each events as row, i (row.id)}
        {@const p = recordPatcher(row.id)}
        <li class="event" class:hidden={row.data.visibility === 'gm'}>
          <div class="when">
            <DebouncedText value={row.data.when ?? ''} onchange={(v) => p('/when', v)} placeholder="nine years ago…" class="whenin" />
            <div class="nudge">
              <button class="ghost small" disabled={i === 0} onclick={() => move(i, -1)} title="Earlier">↑</button>
              <button class="ghost small" disabled={i === events.length - 1} onclick={() => move(i, 1)} title="Later">↓</button>
            </div>
          </div>
          <div class="what">
            <div class="row title">
              <DebouncedText value={row.data.name} onchange={(v) => p('/name', v)} class="etitle" placeholder="What happened" />
              {#if row.data.visibility === 'gm'}<span class="tag gm">GM</span>{/if}
            </div>
            {#if editing === row.id}
              <DebouncedText value={row.data.notes} onchange={(v) => p('/notes', v)} multiline rows={2}
                placeholder="What happened, and to whom. Link anyone with [[their name]]." />
              <button class="ghost small" onclick={() => (editing = null)}>Done</button>
            {:else}
              <button class="asprose" onclick={() => (editing = row.id)} title="Click to edit">
                <Markdown text={row.data.notes || '_No detail yet._'} />
              </button>
            {/if}
            <div class="row who">
              {#each row.data.involves ?? [] as id}
                <button class="pill who-pill" onclick={() => peek(app.characters[id] ? { kind: 'character', id } : { kind: 'record', id })}>{nameOf(id)}</button>
              {/each}
              <select class="small" value="" onchange={(e) => { involve(row, (e.currentTarget as HTMLSelectElement).value); (e.currentTarget as HTMLSelectElement).value = ''; }} aria-label="Who was involved">
                <option value="">+ who</option>
                {#each people as person}
                  {#if !(row.data.involves ?? []).includes(person.id)}<option value={person.id}>{person.name}</option>{/if}
                {/each}
              </select>
              {#if isGm()}
                <span class="grow"></span>
                <label class="chk small">
                  <input type="checkbox" checked={row.data.visibility === 'gm'}
                    onchange={(e) => p('/visibility', (e.currentTarget as HTMLInputElement).checked ? 'gm' : 'table')} />
                  GM only
                </label>
              {/if}
            </div>
          </div>
        </li>
      {/each}
    </ol>
  {/if}
</div>

<style>
  .page { padding: .75em 1em 1em; }
  .head { gap: .5em; align-items: baseline; margin-bottom: .6em; }
  .head h2 { font-size: 1.3em; }
  .new { width: 14em; }
  .line { list-style: none; margin: 0; padding: 0; border-left: 2px solid var(--border); }
  .event { display: grid; grid-template-columns: minmax(7em, 10em) minmax(0, 1fr); gap: .3em .9em; padding: .6em .8em; position: relative; }
  .event::before { content: ''; position: absolute; left: -.42em; top: 1.1em; width: .55em; height: .55em; border-radius: 50%; background: var(--fg-muted); }
  .event.hidden::before { background: var(--accent); }
  .event + .event { border-top: 1px solid var(--border); }
  .when { display: flex; flex-direction: column; gap: .2em; }
  .when :global(.whenin) { width: 100%; font-style: italic; }
  .nudge { display: flex; gap: .2em; }
  .what :global(.etitle) { font-weight: 600; width: 100%; }
  .title { gap: .4em; }
  .asprose { display: block; width: 100%; text-align: left; background: none; border: 0; padding: 0; cursor: text; color: inherit; font: inherit; }
  .who { gap: .3em; margin-top: .3em; flex-wrap: wrap; }
  .who-pill { cursor: pointer; background: none; }
  .tag.gm { background: var(--accent-soft); color: var(--accent); }
  .chk { display: inline-flex; align-items: center; gap: .3em; color: var(--fg-muted); }
  .empty { padding: 1em 0; }
</style>
