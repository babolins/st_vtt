<script lang="ts">
  /** One record, editable in place — the same component whether it is peeked
   *  beside a sheet or opened as its own page.
   *
   *  Every field patches live over the same channel a character sheet uses, so
   *  two people writing down the same NPC during play merge rather than
   *  clobber. `secret` and the GM-only switch are the two things a player never
   *  sees: the secret is stripped server-side, not merely hidden here.
   */
  import { api } from '../lib/api';
  import { app, isGm, records, toast } from '../lib/state.svelte';
  import { recordPatcher } from '../lib/patch';
  import { peek } from '../lib/router.svelte';
  import type { RecordRow } from '../lib/types';
  import DebouncedText from './DebouncedText.svelte';

  let { row, dense = false }: { row: RecordRow; dense?: boolean } = $props();

  const p = $derived(recordPatcher(row.id));
  const doc = $derived(row.data);
  const others = $derived(records().filter((r) => r.id !== row.id));
  const characters = $derived(Object.values(app.characters));
  /** A tie points at a record or at a player's character; both are people. */
  const nameOf = (id: string) => app.records[id]?.data.name ?? app.characters[id]?.data.name ?? id;

  let tieType = $state('');
  let tieTo = $state('');

  async function addTie() {
    if (!tieType.trim() || !tieTo) return;
    await p('/ties', { type: tieType.trim(), to: tieTo, note: '' }, 'list_add');
    tieType = '';
    tieTo = '';
  }

  async function remove() {
    try { await api.del(`/api/records/${row.id}`); } catch (e) { toast((e as Error).message, 'error'); }
  }
</script>

<div class="rec" class:dense>
  <DebouncedText value={doc.name} onchange={(v) => p('/name', v)} class="name" placeholder="Name" />

  <div class="fields">
    <label>Pronouns<DebouncedText value={doc.pronouns} onchange={(v) => p('/pronouns', v)} placeholder="they/them" /></label>
    <label>Role<DebouncedText value={doc.role} onchange={(v) => p('/role', v)} placeholder="publican, smith…" /></label>
    <label>Home<DebouncedText value={doc.home} onchange={(v) => p('/home', v)} placeholder="Stonetop" /></label>
    <label>Standing<DebouncedText value={doc.status} onchange={(v) => p('/status', v)} placeholder="alive, dead, retired…" /></label>
  </div>

  <div class="ties">
    <span class="lbl">Ties</span>
    {#each doc.ties as t, i}
      <div class="row tie">
        <span class="ttype">{t.type.replace(/-/g, ' ')}</span>
        <button class="linky" onclick={() => peek(app.characters[t.to] ? { kind: 'character', id: t.to } : { kind: 'record', id: t.to })}>{nameOf(t.to)}</button>
        <DebouncedText value={t.note} onchange={(v) => p(`/ties/${i}/note`, v)} placeholder="how so?" class="tnote" />
        <button class="ghost small danger" title="Remove tie" onclick={() => p('/ties', doc.ties.filter((_, j) => j !== i))}>✕</button>
      </div>
    {/each}
    <div class="row addtie">
      <input class="small" bind:value={tieType} placeholder="deputy-of, sidekick-of…" aria-label="Tie type" />
      <select class="small" bind:value={tieTo} aria-label="Tie to">
        <option value="">…to whom</option>
        {#if characters.length}
          <optgroup label="Player characters">
            {#each characters as c}<option value={c.id}>{c.data.name || 'Unnamed'}</option>{/each}
          </optgroup>
        {/if}
        {#if others.length}
          <optgroup label="Written down">
            {#each others as o}<option value={o.id}>{o.data.name}</option>{/each}
          </optgroup>
        {/if}
      </select>
      <button class="small" onclick={addTie} disabled={!tieType.trim() || !tieTo}>Add tie</button>
    </div>
  </div>

  <label class="block">Notes<DebouncedText value={doc.notes} onchange={(v) => p('/notes', v)} multiline placeholder="What the table knows." /></label>

  {#if isGm()}
    <label class="block secret">What really happened <span class="muted small">— GM only</span>
      <DebouncedText value={doc.secret ?? ''} onchange={(v) => p('/secret', v)} multiline placeholder="The truth beside the tale." />
    </label>
    <div class="row gmbar">
      <label class="chk">
        <input type="checkbox" checked={doc.visibility === 'gm'} onchange={(e) => p('/visibility', (e.currentTarget as HTMLInputElement).checked ? 'gm' : 'table')} />
        Hide this record from the table entirely
      </label>
      <span class="grow"></span>
      <button class="ghost small danger" onclick={remove}>Delete</button>
    </div>
  {:else if doc.created_by === app.me?.name}
    <div class="row gmbar"><span class="grow"></span><button class="ghost small danger" onclick={remove}>Delete</button></div>
  {/if}
</div>

<style>
  .rec :global(.name) { font-size: 1.2em; font-weight: 600; width: 100%; }
  .fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(8.5em, 1fr)); gap: .4em; margin: .6em 0; }
  .fields label, .block { display: flex; flex-direction: column; gap: .15em; }
  .block { margin-top: .6em; }
  .lbl { font-size: .85em; color: var(--fg-muted); }
  .ties { margin-top: .5em; display: flex; flex-direction: column; gap: .25em; }
  .tie { gap: .35em; }
  .ttype { font-size: .85em; color: var(--fg-muted); min-width: 6em; }
  .tie :global(.tnote) { flex: 1; min-width: 6em; }
  .addtie { gap: .3em; margin-top: .2em; }
  .addtie input { width: 11em; }
  .linky { background: none; border: 0; padding: 0; color: var(--accent); cursor: pointer; font: inherit; }
  .secret :global(textarea) { border-color: var(--warn); }
  .gmbar { margin-top: .7em; gap: .5em; }
  .chk { display: inline-flex; align-items: center; gap: .35em; color: var(--fg); font-size: .9em; }
  .dense .fields { grid-template-columns: repeat(auto-fit, minmax(7em, 1fr)); }
</style>
