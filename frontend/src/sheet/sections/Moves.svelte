<script lang="ts">
  import { app } from '../../lib/state.svelte';
  import { borrowedFrom, granted, moveIndex, packInserts, uid } from '../../lib/util';
  import type { CharacterDoc, Move, Playbook } from '../../lib/types';
  import type { Patcher } from '../../lib/patch';
  import Collapsible from '../../ui/Collapsible.svelte';
  import Stepper from '../../ui/Stepper.svelte';
  import MoveCard from './MoveCard.svelte';

  let { doc, p, editable, pb, characterId }: { doc: CharacterDoc; p: Patcher; editable: boolean; pb: Playbook | undefined; characterId: string } = $props();
  const content = $derived(app.content!);
  const index = $derived(moveIndex(content, doc));
  const sharedIds = $derived(new Set(Object.values(content.moves).flat().map((m) => m.id)));
  const mineInserts = $derived(packInserts(content, doc));
  // Insert moves live on their own insert, not in this list.
  const insertIds = $derived(new Set(mineInserts.flatMap((i) => i.moves.map((m) => m.id))));
  const taken = $derived(doc.moves.taken.map((id) => index.get(id)).filter((m): m is Move => !!m && !sharedIds.has(m.id) && !insertIds.has(m.id)));
  const available = $derived((pb?.moves ?? []).filter((m) => !doc.moves.taken.includes(m.id)));
  // A move with `grants` opens up another playbook's moves; those are extra, so they
  // are not counted against this playbook's own budget.
  const borrowed = $derived(granted(content, doc, pb));
  const borrowedCount = $derived(taken.filter((m) => borrowedFrom(content, m.id, pb)).length);
  const startingCount = $derived((pb?.starting_moves.fixed.length ?? 0) + (pb?.starting_moves.choose.reduce((a, c) => a + c.n, 0) ?? 0));
  const expected = $derived(startingCount + (doc.level - content.pack.xp.start_level) + borrowedCount);
  const holdNames = $derived.by(() => {
    const names = new Set<string>([...content.pack.hold_names, ...(pb?.hold_names ?? [])]);
    for (const i of mineInserts) for (const n of i.hold_names) names.add(n);
    for (const m of index.values()) if (m.hold) names.add(m.hold.name);
    for (const n of Object.keys(doc.moves.hold)) names.add(n);
    return [...names];
  });

  let picking = $state(false);
  let customOpen = $state(false);
  let cName = $state('');
  let cTrigger = $state('');
  let cText = $state('');
  let cStat = $state<string>('');

  function locked(m: Move): string | null {
    if (!m.requires) return null;
    const why: string[] = [];
    if (m.requires.level && doc.level < m.requires.level) why.push(`level ${m.requires.level}`);
    for (const r of m.requires.moves) if (!doc.moves.taken.includes(r)) why.push(index.get(r)?.name ?? r);
    return why.length ? `requires ${why.join(', ')}` : null;
  }
  function take(m: Move) {
    p('/moves/taken', m.id, 'list_add');
    if (m.replaces) p('/moves/taken', m.replaces, 'list_remove');
    grantInsert(m, 1);
    picking = false;
  }
  function remove(id: string) {
    p('/moves/taken', id, 'list_remove');
    const m = index.get(id);
    if (m) grantInsert(m, -1);
  }
  /** Some moves hand you a whole insert (an animal companion, say). */
  function grantInsert(m: Move, sign: 1 | -1) {
    const ins = m.insert ? content.inserts.find((i) => i.id === m.insert) : undefined;
    if (!ins) return;
    p('/inserts', ins.id, sign > 0 ? 'list_add' : 'list_remove');
    for (const id of ins.starting_moves.fixed) p('/moves/taken', id, sign > 0 ? 'list_add' : 'list_remove');
  }
  function addCustom() {
    if (!cName.trim()) return;
    const m: Move = {
      id: `custom_${uid()}`, name: cName.trim(), trigger: cTrigger, text: cText,
      roll: cStat === '' ? null : { stat: cStat === 'nothing' ? null : cStat === 'choose' ? 'choose' : cStat, bonus: 0, label: null, modifiers: [] },
      outcomes: {}, hold: null, tracks: { marks: null, bulk: null, uses: null, statuses: [] },
      requires: null, themes: [], tags: ['custom'], replaces: null, insert: null, grants: null,
      options: [], min: null, max: null,
    };
    p('/custom_moves/-', m);
    p('/moves/taken', m.id, 'list_add');
    cName = cTrigger = cText = ''; cStat = ''; customOpen = false;
  }
</script>

<Collapsible id="moves.{characterId}" title="Moves"
  subtitle={editable && taken.length < expected ? `pick ${expected - taken.length} more` : editable && borrowed.left > 0 ? `${borrowed.left} from another playbook` : ''}>
  {#snippet right()}
    {#if editable}
      <button class="small" onclick={() => (picking = !picking)}>{picking ? 'Close' : '+ Move'}</button>
      <button class="small" onclick={() => (customOpen = !customOpen)}>+ Custom</button>
    {/if}
  {/snippet}

  {#if picking}
    <div class="picker">
      {#if available.length === 0}<p class="muted">No more playbook moves.</p>{/if}
      {#each available as m}
        {@const why = locked(m)}
        <div class="row pick">
          <div class="grow">
            <strong>{m.name}</strong> {#if why}<span class="tag warn">{why}</span>{/if}
            {#if pb?.starting_moves.choose.some((c) => c.from.includes(m.id))}<span class="tag">starting option</span>{/if}
            <div class="muted small">{m.trigger || m.text.slice(0, 120)}</div>
          </div>
          <button class="small" onclick={() => take(m)}>Take</button>
        </div>
      {/each}
      {#if borrowed.offers.length}
        <h4 class="borrowed">From other playbooks <span class="muted small">{borrowed.left} to pick</span></h4>
        {#each borrowed.offers as { move: m, from } (m.id)}
          {@const why = locked(m)}
          <div class="row pick">
            <div class="grow">
              <strong>{m.name}</strong> <span class="tag">{from.name}</span>
              {#if why}<span class="tag warn">{why}</span>{/if}
              <div class="muted small">{m.trigger || m.text.slice(0, 120)}</div>
            </div>
            <button class="small" onclick={() => take(m)}>Take</button>
          </div>
        {/each}
      {/if}
    </div>
  {/if}
  {#if customOpen}
    <div class="picker stack">
      <input type="text" placeholder="Move name" bind:value={cName} />
      <input type="text" placeholder="Trigger (optional)" bind:value={cTrigger} />
      <textarea placeholder="Text (markdown)" bind:value={cText} rows="3"></textarea>
      <div class="row">
        <select bind:value={cStat}>
          <option value="">no roll</option>
          <option value="nothing">roll +nothing</option>
          <option value="choose">roll + chosen stat</option>
          {#each content.pack.stats as s}<option value={s.id}>roll +{s.label}</option>{/each}
        </select>
        <button class="small primary" onclick={addCustom} disabled={!cName.trim()}>Add</button>
      </div>
    </div>
  {/if}

  {#each taken as m (m.id)}
    {@const from = borrowedFrom(content, m.id, pb)}
    <MoveCard move={from ? { ...m, tags: [...m.tags, from.name] } : m} {characterId} {editable} {doc} {p} tracks={doc.moves.tracks[m.id]}
      ontrack={(kind, v) => p(`/moves/tracks/${m.id}/${kind}`, v)}
      onremove={() => remove(m.id)} />
  {/each}
  {#if taken.length === 0}<p class="muted small">No playbook moves yet.</p>{/if}

  {#if holdNames.length}
    <div class="row hold">
      <span class="muted small">Hold</span>
      {#each holdNames as h}
        <Stepper label={h} value={doc.moves.hold[h] ?? 0} min={0} onchange={(v) => p(`/moves/hold/${h}`, v)} path={`/moves/hold/${h}`} disabled={!editable} />
      {/each}
    </div>
  {/if}

  {#each Object.entries(content.moves) as [group, moves]}
    <Collapsible id="moves.{group}" title="{group} moves" open={false}>
      {#each moves as m (m.id)}
        <MoveCard move={m} {characterId} {editable} compact {doc} {p}
          tracks={doc.moves.tracks[m.id]} ontrack={(kind, v) => p(`/moves/tracks/${m.id}/${kind}`, v)} />
      {/each}
    </Collapsible>
  {/each}
</Collapsible>

<style>
  .picker { border: 1px dashed var(--border); border-radius: 6px; padding: .5em .75em; margin: .25em 0 .5em; }
  .pick { padding: .25em 0; border-bottom: 1px solid var(--border); }
  .pick:last-child { border-bottom: 0; }
  .tag.warn { color: var(--warn); }
  .borrowed { margin: .6em 0 .2em; font-size: .85em; text-transform: uppercase; letter-spacing: .04em; color: var(--fg-muted); }
  .hold { margin: .5em 0; gap: 1em; }
</style>
