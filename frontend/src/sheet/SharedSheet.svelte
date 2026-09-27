<script lang="ts">
  import { setContext } from 'svelte';
  import { app, isGm, toast } from '../lib/state.svelte';
  import { sharedPatcher, SHEET } from '../lib/patch';
  import { api } from '../lib/api';
  import { download, pickFile } from '../lib/util';
  import type { SharedRow } from '../lib/types';
  import Collapsible from '../ui/Collapsible.svelte';
  import Confirm from '../ui/Confirm.svelte';
  import DebouncedText from '../ui/DebouncedText.svelte';
  import Stepper from '../ui/Stepper.svelte';
  import StatBlock from '../ui/StatBlock.svelte';
  import GenericSection from './sections/GenericSection.svelte';
  import MoveCard from './sections/MoveCard.svelte';
  import Notes from './sections/Notes.svelte';
  import { presence } from '../lib/presence.svelte';

  let { row }: { row: SharedRow } = $props();
  const def = $derived(app.content!.shared_sheets.find((t) => t.id === row.data.template));
  const doc = $derived(row.data);
  // An instance is one sheet for life: every caller keys it on row.id.
  // svelte-ignore state_referenced_locally
  const p = sharedPatcher(row.id);
  // svelte-ignore state_referenced_locally
  setContext(SHEET, { entity: 'shared', id: row.id, p });
  const editable = true;
  let confirmDelete = $state(false);
  const holdNames = $derived.by(() => {
    const names = new Set<string>();
    for (const m of def?.moves ?? []) if (m.hold) names.add(m.hold.name);
    for (const n of Object.keys(doc.moves.hold)) names.add(n);
    return [...names];
  });
  const subtitle = $derived([def?.visibility === 'gm' ? 'GM only' : 'shared', def?.name, doc.size].filter(Boolean).join(' · '));

  async function exportJson() {
    try { download(`${doc.name || 'shared'}.json`, await api.get(`/api/shared/${row.id}/export`)); } catch (e) { toast((e as Error).message, 'error'); }
  }
  async function importJson() {
    try { await api.post(`/api/shared/${row.id}/import`, await pickFile()); toast('Sheet replaced'); } catch (e) { toast((e as Error).message, 'error'); }
  }
  async function remove() {
    try { await api.del(`/api/shared/${row.id}`); } catch (e) { toast((e as Error).message, 'error'); }
  }
</script>

<Collapsible id="shared.{row.id}" title={doc.name || def?.name || 'Shared sheet'} level={2} {subtitle}>
  {#snippet right()}
    <button class="ghost small" onclick={exportJson} title="Export JSON">⇩</button>
    {#if isGm()}
      <button class="ghost small" onclick={importJson} title="Replace from JSON">⇧</button>
      <button class="ghost small danger" onclick={() => (confirmDelete = true)} title="Delete">🗑</button>
    {/if}
  {/snippet}

  {#if !def}
    <p class="muted">Unknown template <code>{doc.template}</code>: the content pack no longer defines it, so only notes are shown.</p>
  {:else}
    {#if def.blurb}<p class="muted small">{def.blurb}</p>{/if}
    <div class="row head">
      <label class="f grow">Name <DebouncedText value={doc.name} path="/name" /></label>
      {#if def.sizes.length}
        <label class="f">Size
          <select value={doc.size} use:presence={{ entity: 'shared', id: row.id, path: '/size' }} onchange={(e) => p('/size', (e.target as HTMLSelectElement).value)}>
            {#each def.sizes as s}<option value={s}>{s}</option>{/each}
          </select>
        </label>
      {/if}
    </div>

    {#if def.stats.length}
      <div class="stats">
        <StatBlock stats={def.stats} title={(s) => s.help}>
          {#snippet value(s)}
            <Stepper value={doc.stats?.[s.id] ?? s.start} min={s.min} max={s.max} onchange={(v) => p(`/stats/${s.id}`, v)} path={`/stats/${s.id}`} big />
          {/snippet}
        </StatBlock>
      </div>
    {/if}

    {#if def.debilities.length}
      <div class="row debils">
        {#each def.debilities as d}
          <label class="deb" title={d.text}>
            <input type="checkbox" checked={!!doc.debilities?.[d.id]} use:presence={{ entity: 'shared', id: row.id, path: `/debilities/${d.id}` }} onchange={(e) => p(`/debilities/${d.id}`, (e.target as HTMLInputElement).checked)} />
            {d.label}
          </label>
        {/each}
      </div>
    {/if}

    {#each def.sections as sec (sec.id)}
      <GenericSection section={sec} value={doc.sections?.[sec.id]} {editable} basePath={`/sections/${sec.id}`} {doc} {p} idPrefix="shared.{row.id}." />
    {/each}

    {#if def.moves.length}
      <Collapsible id="shared.{row.id}.moves" title="Moves" open={false}>
        {#each def.moves as m (m.id)}
          <MoveCard move={m} characterId={null} sharedId={row.id} {editable} compact {doc} {p}
            tracks={doc.moves.tracks[m.id]} ontrack={(kind, v) => p(`/moves/tracks/${m.id}/${kind}`, v)} />
        {/each}
        {#if holdNames.length}
          <div class="row" style="gap:1em;margin-top:.5em">
            <span class="muted small">Hold</span>
            {#each holdNames as h}
              <Stepper label={h} value={doc.moves.hold[h] ?? 0} min={0} onchange={(v) => p(`/moves/hold/${h}`, v)} path={`/moves/hold/${h}`} />
            {/each}
          </div>
        {/if}
      </Collapsible>
    {/if}
  {/if}

  <Notes {doc} {p} {editable} id="shared.{row.id}" />
</Collapsible>

{#if confirmDelete}
  <Confirm title="Delete {doc.name}?" text="Export it first if you want a backup. Everyone loses it." onyes={remove} onclose={() => (confirmDelete = false)} />
{/if}

<style>
  .head { padding: .5em 0; }
  .f { display: flex; flex-direction: column; gap: .15em; }
  .stats { margin-bottom: .5em; }
  .debils { gap: 1em; margin-bottom: .5em; }
  .deb { display: inline-flex; align-items: center; gap: .3em; color: var(--fg); cursor: pointer; font-style: var(--debility-style); }
</style>
