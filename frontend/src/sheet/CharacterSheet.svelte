<script lang="ts">
  import { setContext } from 'svelte';
  import { app, canEdit, isGm } from '../lib/state.svelte';
  import { characterPatcher, SHEET } from '../lib/patch';
  import { api } from '../lib/api';
  import { toast } from '../lib/state.svelte';
  import { download, packInserts, playbookOf } from '../lib/util';
  import type { CharacterRow, Option, Section } from '../lib/types';
  import Collapsible from '../ui/Collapsible.svelte';
  import Confirm from '../ui/Confirm.svelte';
  import Identity from './sections/Identity.svelte';
  import Stats from './sections/Stats.svelte';
  import Moves from './sections/Moves.svelte';
  import Inserts from './sections/Inserts.svelte';
  import Gear from './sections/Gear.svelte';
  import Followers from './sections/Followers.svelte';
  import Arcana from './sections/Arcana.svelte';
  import Notes from './sections/Notes.svelte';
  import GenericSection from './sections/GenericSection.svelte';

  let { row }: { row: CharacterRow } = $props();
  const content = $derived(app.content!);
  const doc = $derived(row.data);
  const pb = $derived(playbookOf(content, doc));
  const editable = $derived(canEdit(row));
  const p = characterPatcher(row.id);
  setContext(SHEET, { entity: 'character', id: row.id, p });
  let confirmDelete = $state(false);

  /** Everything the sheet renders as a section: the playbook's, then each insert's. */
  const sheetSections = $derived.by((): Section[] => [
    ...(pb?.sections ?? []),
    ...packInserts(content, doc).flatMap((i) => i.sections),
  ]);

  /** A picked option (or a note) can require picks of its own; report what is still short. */
  function subChoiceGaps(sec: Section): string[] {
    const value = doc.sections?.[sec.id];
    const picked = Array.isArray(value) ? (value as string[]) : typeof value === 'string' ? [value] : [];
    const out: string[] = [];
    for (const o of sec.options as Option[]) {
      if (o.min == null || !o.options.length) continue;
      if (!o.note && !picked.includes(o.id)) continue;
      const have = (doc.sub_choices[sec.id]?.[o.id] ?? []).length;
      if (have < o.min) out.push(`${sec.title} — ${o.label}: pick ${o.min - have} more`);
    }
    return out;
  }

  const checklist = $derived.by((): string[] => {
    const items: string[] = [];
    if (!doc.name?.trim()) items.push('Choose a name');
    const arr = pb?.stat_array ?? content.pack.stat_array;
    if (arr.length) {
      const have = Object.values(doc.stats ?? {}).slice().sort((a, b) => a - b).join(',');
      const want = arr.slice().sort((a, b) => a - b).join(',');
      if (have !== want) items.push(`Assign stats from ${arr.map((n) => (n >= 0 ? '+' + n : n)).join(', ')}`);
    }
    for (const sec of sheetSections) {
      if (!sec.required) continue;
      const v = doc.sections?.[sec.id];
      if (sec.type === 'choose' && (v === null || v === undefined || v === '')) items.push(`Choose ${sec.title.toLowerCase()}`);
      else if (sec.type === 'multichoose') {
        const need = (sec.min ?? 1) - ((v as string[])?.length ?? 0);
        if (need > 0) items.push(`${sec.title}: pick ${need} more`);
      } else if (sec.type === 'checklist' && !((v as string[])?.length)) items.push(`${sec.title}: check at least one`);
      else if (sec.type === 'lines') {
        const picks = (v ?? {}) as Record<string, string | null>;
        const missing = sec.lines.filter((ln) => !picks[ln.id] && !(doc.option_text[sec.id]?.[ln.id] ?? '').trim()).length;
        if (missing) items.push(`${sec.title}: choose 1 on ${missing} more line${missing > 1 ? 's' : ''}`);
      } else if (sec.type === 'names' && !String((v as { name?: string })?.name ?? '').trim()) {
        items.push(`Choose ${sec.title.toLowerCase()}`);
      } else if (sec.type === 'text' && !String(v ?? '').trim()) items.push(`Fill in ${sec.title.toLowerCase()}`);
      else if (sec.type === 'table' && !((v as unknown[])?.length)) items.push(`${sec.title}: add at least one row`);
      items.push(...subChoiceGaps(sec));
    }
    for (const c of pb?.starting_moves.choose ?? []) {
      const have = c.from.filter((id) => doc.moves.taken.includes(id)).length;
      if (have < c.n) items.push(`Choose ${c.n - have} more starting move${c.n - have > 1 ? 's' : ''} (${c.from.map((id) => pb?.moves.find((m) => m.id === id)?.name ?? id).join(' / ')}) using + Move in the Moves section`);
    }
    return items;
  });

  // Once every creation item is satisfied, mark creation done so the checklist stays hidden.
  $effect(() => {
    if (editable && !doc.creation_done && checklist.length === 0) p('/creation_done', true);
  });

  async function exportJson() {
    try { download(`${doc.name || 'character'}.json`, await api.get(`/api/characters/${row.id}/export`)); } catch (e) { toast((e as Error).message, 'error'); }
  }
  async function remove() {
    try { await api.del(`/api/characters/${row.id}`); } catch (e) { toast((e as Error).message, 'error'); }
  }
  async function setOwner(e: Event) {
    const owner = (e.target as HTMLSelectElement).value || null;
    try { await api.post(`/api/characters/${row.id}/owner`, { owner }); } catch (err) { toast((err as Error).message, 'error'); }
  }
  const inserts = $derived(doc.inserts);
</script>

<Collapsible id="char.{row.id}" title={doc.name || '(unnamed)'} level={2} subtitle="{pb?.name ?? doc.playbook} · {row.owner ?? 'unowned'}">
  {#snippet right()}
    <!-- The numbers consulted constantly, kept on screen while the sheet scrolls
         past: on a 4,400px sheet the stat block is otherwise long gone. -->
    <span class="vitals small" title="HP, armor, level, XP">
      <span class:hurt={doc.hp.current <= doc.hp.max / 3}>{doc.hp.current}/{doc.hp.max} hp</span>
      {#if doc.armor}<span>{doc.armor} armor</span>{/if}
      <span>lvl {doc.level}</span>
      <span>{doc.xp} xp</span>
      {#each app.content?.pack.debilities ?? [] as d}
        {#if doc.debilities[d.id]}<span class="deb">{d.label}</span>{/if}
      {/each}
    </span>
    {#if isGm()}
      <select class="small" value={row.owner ?? ''} onchange={setOwner} title="Owner">
        <option value="">(nobody)</option>
        {#each app.users as u}<option value={u.name}>{u.name}</option>{/each}
      </select>
    {/if}
    <button class="ghost small" onclick={exportJson} title="Export JSON">⇩</button>
    {#if editable}<button class="ghost small danger" onclick={() => (confirmDelete = true)} title="Delete">🗑</button>{/if}
  {/snippet}

  {#if !pb}
    <p class="muted">Unknown playbook <code>{doc.playbook}</code>: the content pack has no definition for it, so only core sections are shown.</p>
  {/if}

  {#if editable && !doc.creation_done && checklist.length}
    <div class="checklist">
      <strong>Character creation</strong>
      <ul>{#each checklist as item}<li>{item}</li>{/each}</ul>
      <button class="small" onclick={() => p('/creation_done', true)}>Hide checklist</button>
    </div>
  {/if}

  <Identity {doc} {p} {editable} {pb} />
  <Stats {doc} {p} {editable} {pb} />

  {#each pb?.sections ?? [] as sec (sec.id)}
    <GenericSection section={sec} value={doc.sections?.[sec.id]} {editable} basePath={`/sections/${sec.id}`} {doc} {p} />
  {/each}

  <Moves {doc} {p} {editable} {pb} characterId={row.id} />
  <Inserts {doc} {p} {editable} {pb} characterId={row.id} />
  {#if inserts.includes('gear')}<Gear {doc} {p} {editable} {pb} />{/if}
  {#if inserts.includes('followers')}<Followers {doc} {p} {editable} />{/if}
  {#if inserts.includes('arcana')}<Arcana {doc} {p} {editable} characterId={row.id} />{/if}
  <Notes {doc} {p} {editable} id={row.id} />
</Collapsible>

{#if confirmDelete}
  <Confirm title="Delete {doc.name || 'this character'}?" text="Export it first if you want a backup." onyes={remove} onclose={() => (confirmDelete = false)} />
{/if}

<style>
  .vitals { display: inline-flex; gap: .55em; color: var(--fg-muted); font-variant-numeric: tabular-nums; }
  .vitals .hurt { color: var(--bad); font-weight: 600; }
  .vitals .deb { color: var(--warn); font-style: italic; }
  @media (max-width: 700px) { .vitals { display: none; } }
  .checklist { background: var(--accent-soft); border-radius: 6px; padding: .5em .75em; margin: .25em 0 .5em; }
  .checklist ul { margin: .25em 0 .5em; }
</style>
