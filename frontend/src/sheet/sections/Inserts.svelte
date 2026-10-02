<script lang="ts">
  // The half-sheets a PC slips inside their playbook: a warband, a spellbook, the ghost you
  // become. Each brings its own sections and moves; `gear`, `followers` and `arcana` are engine
  // sections and are rendered by their own components instead.
  import { app } from '../../lib/state.svelte';
  import { moveIndex, movePreview, packInserts } from '../../lib/util';
  import type { CharacterDoc, InsertDef, Move, Playbook } from '../../lib/types';
  import type { Patcher } from '../../lib/patch';
  import Collapsible from '../../ui/Collapsible.svelte';
  import Markdown from '../../ui/Markdown.svelte';
  import { renderInline } from '../../lib/markdown';
  import GenericSection from './GenericSection.svelte';
  import MoveCard from './MoveCard.svelte';

  let { doc, p, editable, pb, characterId }: {
    doc: CharacterDoc; p: Patcher; editable: boolean; pb: Playbook | undefined; characterId: string;
  } = $props();

  const content = $derived(app.content!);
  const mine = $derived(packInserts(content, doc));
  const index = $derived(moveIndex(content, doc));
  const available = $derived(content.inserts.filter((i) => !doc.inserts.includes(i.id)));
  let pick = $state('');

  const takenOf = (ins: InsertDef) => ins.moves.filter((m) => doc.moves.taken.includes(m.id));
  const offeredBy = (ins: InsertDef) => ins.moves.filter((m) => !doc.moves.taken.includes(m.id));

  function add() {
    const ins = content.inserts.find((i) => i.id === pick);
    if (!ins) return;
    p('/inserts', ins.id, 'list_add');
    for (const id of ins.starting_moves.fixed) p('/moves/taken', id, 'list_add');
    pick = '';
  }
  function remove(ins: InsertDef) {
    p('/inserts', ins.id, 'list_remove');
    for (const m of ins.moves) p('/moves/taken', m.id, 'list_remove');
  }
  function locked(m: Move): string | null {
    if (!m.requires) return null;
    const why: string[] = [];
    if (m.requires.level && doc.level < m.requires.level) why.push(`level ${m.requires.level}`);
    for (const r of m.requires.moves) if (!doc.moves.taken.includes(r)) why.push(index.get(r)?.name ?? r);
    return why.length ? `requires ${why.join(', ')}` : null;
  }
</script>

{#if mine.length || (editable && available.length)}
  <Collapsible id="inserts.{characterId}" title="Inserts" subtitle={mine.length ? `${mine.length}` : ''}>
    {#snippet right()}
      {#if editable && available.length}
        <select bind:value={pick} class="small">
          <option value="">add an insert…</option>
          {#each available as i}<option value={i.id}>{i.name}</option>{/each}
        </select>
        <button class="small" onclick={add} disabled={!pick}>Add</button>
      {/if}
    {/snippet}

    {#each mine as ins (ins.id)}
      <div class="insert">
        <div class="row top">
          <strong>{ins.name}</strong><span class="tag">{ins.kind}</span>
          <span class="grow"></span>
          {#if editable}<button class="ghost small danger" title="Remove insert" onclick={() => remove(ins)}>✕</button>{/if}
        </div>
        {#if ins.blurb}<p class="muted small">{@html renderInline(ins.blurb)}</p>{/if}
        {#if ins.description}<Markdown text={ins.description} />{/if}

        {#each ins.sections as sec (sec.id)}
          <GenericSection section={sec} value={doc.sections?.[sec.id]} {editable}
            basePath={`/sections/${sec.id}`} {doc} {p} idPrefix="{characterId}.{ins.id}." />
        {/each}

        {#each takenOf(ins) as m (m.id)}
          <MoveCard move={m} {characterId} {editable} {doc} {p} tracks={doc.moves.tracks[m.id]}
            ontrack={(kind, v) => p(`/moves/tracks/${m.id}/${kind}`, v)}
            onremove={ins.starting_moves.fixed.includes(m.id) ? undefined : () => p('/moves/taken', m.id, 'list_remove')} />
        {/each}

        {#if editable && offeredBy(ins).length}
          <Collapsible id="insert.more.{characterId}.{ins.id}" title="More from this insert" open={false}>
            {#each offeredBy(ins) as m (m.id)}
              {@const why = locked(m)}
              <div class="row pick">
                <div class="grow">
                  <strong>{m.name}</strong> {#if why}<span class="tag warn">{why}</span>{/if}
                  <div class="muted small">{movePreview(m)}</div>
                </div>
                <button class="small" onclick={() => p('/moves/taken', m.id, 'list_add')}>Take</button>
              </div>
            {/each}
          </Collapsible>
        {/if}
      </div>
    {/each}
  </Collapsible>
{/if}

<style>
  .insert { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: .5em .75em; margin-bottom: .5em; }
  .insert .top { margin-bottom: .25em; }
  .pick { padding: .25em 0; border-bottom: 1px solid var(--border); }
  .pick:last-child { border-bottom: 0; }
  .tag.warn { color: var(--warn); }
</style>
