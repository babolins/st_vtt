<script lang="ts">
  import { app } from '../../lib/state.svelte';
  import { uid } from '../../lib/util';
  import { at } from '../../lib/pointer';
  import type { ArcanumInstance, CharacterDoc } from '../../lib/types';
  import type { Patcher } from '../../lib/patch';
  import Collapsible from '../../ui/Collapsible.svelte';
  import DebouncedText from '../../ui/DebouncedText.svelte';
  import Markdown from '../../ui/Markdown.svelte';
  import Pips from '../../ui/Pips.svelte';
  import Stepper from '../../ui/Stepper.svelte';
  import MoveCard from './MoveCard.svelte';
  import { renderInline } from '../../lib/markdown';

  let { doc, p, editable, characterId }: { doc: CharacterDoc; p: Patcher; editable: boolean; characterId: string } =
    $props();
  const library = $derived(app.content!.arcana);
  const list = $derived(doc.arcana ?? []);
  let pick = $state('');

  function blank(): ArcanumInstance {
    return {
      id: uid(),
      ref: null,
      name: '',
      kind: 'minor',
      tags: [],
      description: '',
      questions: [],
      answers: {},
      prerequisites: '',
      moves: [],
      trackers: [],
      state: {},
      notes: '',
    };
  }
  function addFromLibrary() {
    const src = library.find((a) => a.id === pick);
    if (!src) return;
    const inst: ArcanumInstance = {
      ...blank(),
      ...JSON.parse(JSON.stringify(src)),
      id: uid(),
      ref: src.id,
      answers: {},
      notes: '',
    };
    inst.state = Object.fromEntries(src.trackers.map((t) => [t.id, t.type === 'toggle' ? false : 0]));
    p('/arcana/-', inst);
    pick = '';
  }
</script>

<Collapsible id="arcana.{characterId}" title="Arcana" subtitle={list.length ? `${list.length}` : ''}>
  {#snippet right()}
    {#if editable}
      {#if library.length}
        <select bind:value={pick} class="small">
          <option value="">from library…</option>
          {#each library as a}<option value={a.id}>{a.name} ({a.kind})</option>{/each}
        </select>
        <button class="small" onclick={addFromLibrary} disabled={!pick}>Add</button>
      {/if}
      <button class="small" onclick={() => p('/arcana/-', blank())}>+ Custom</button>
    {/if}
  {/snippet}

  {#each list as a (a.id)}
    {@const base = `/arcana/${at(a.id)}`}
    {@const custom = !a.ref}
    <div class="arc">
      <div class="row top">
        {#if custom}
          <DebouncedText class="aname" value={a.name} path={`${base}/name`} readonly={!editable} placeholder="Name" />
          <DebouncedText class="akind" value={a.kind} path={`${base}/kind`} readonly={!editable} placeholder="kind" />
        {:else}
          <strong>{a.name}</strong><span class="tag">{a.kind}</span>
        {/if}
        {#each a.tags ?? [] as t}<span class="tag">{t}</span>{/each}
        <span class="grow"></span>
        {#if editable}<button class="ghost small danger" onclick={() => p(base, null, 'remove')}>✕</button>{/if}
      </div>
      {#if custom}
        <DebouncedText
          multiline
          rows={3}
          value={a.description}
          path={`${base}/description`}
          readonly={!editable}
          placeholder="Description (markdown)"
        />
      {:else}
        <Markdown text={a.description} />
      {/if}
      {#if a.prerequisites}<p class="small"><strong>To learn:</strong> {@html renderInline(a.prerequisites)}</p>{/if}
      {#if a.questions?.length}
        <div class="qs">
          {#each a.questions as q, qi}
            <label class="q"
              >{q}
              <DebouncedText
                value={a.answers?.[String(qi)] ?? ''}
                path={`${base}/answers/${qi}`}
                readonly={!editable}
              />
            </label>
          {/each}
        </div>
      {/if}
      {#if a.trackers?.length}
        <div class="row trackers">
          {#each a.trackers as t}
            <span class="row tr">
              <span class="muted small">{t.label}</span>
              {#if t.type === 'pips'}
                <!-- an arcanum's boxes are charges: circles, like the book -->
                <Pips
                  shape="circle"
                  value={Number(a.state?.[t.id]) || 0}
                  max={t.max ?? 3}
                  onchange={(v) => p(`${base}/state/${t.id}`, v)}
                  path={`${base}/state/${t.id}`}
                  disabled={!editable}
                />
              {:else if t.type === 'counter'}
                <Stepper
                  value={Number(a.state?.[t.id]) || 0}
                  min={0}
                  max={t.max ?? Infinity}
                  onchange={(v) => p(`${base}/state/${t.id}`, v)}
                  path={`${base}/state/${t.id}`}
                  disabled={!editable}
                />
              {:else}
                <input
                  type="checkbox"
                  checked={!!a.state?.[t.id]}
                  disabled={!editable}
                  onchange={(e) => p(`${base}/state/${t.id}`, (e.target as HTMLInputElement).checked)}
                />
              {/if}
            </span>
          {/each}
        </div>
      {/if}
      {#each a.moves ?? [] as m (m.id)}
        <MoveCard
          move={m}
          {characterId}
          {editable}
          {doc}
          {p}
          tracks={doc.moves.tracks[m.id]}
          ontrack={(kind, v) => p(`/moves/tracks/${m.id}/${kind}`, v)}
        />
      {/each}
      <DebouncedText
        multiline
        rows={2}
        value={a.notes ?? ''}
        path={`${base}/notes`}
        readonly={!editable}
        placeholder="Notes"
      />
    </div>
  {/each}
  {#if list.length === 0}<p class="muted small">No arcana.</p>{/if}
</Collapsible>

<style>
  .arc {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.5em 0.75em;
    margin: 0.4em 0;
    background: var(--bg);
    display: flex;
    flex-direction: column;
    gap: 0.4em;
  }
  :global(.aname) {
    font-weight: 600;
    width: 14em;
  }
  :global(.akind) {
    width: 6em;
  }
  .qs {
    display: flex;
    flex-direction: column;
    gap: 0.25em;
  }
  .q {
    display: flex;
    flex-direction: column;
    gap: 0.1em;
    color: var(--fg);
    font-size: 0.95em;
  }
  .trackers {
    gap: 1em;
  }
  .tr {
    gap: 0.4em;
  }
</style>
