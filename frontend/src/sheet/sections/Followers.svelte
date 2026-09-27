<script lang="ts">
  import { app } from '../../lib/state.svelte';
  import { uid } from '../../lib/util';
  import type { CharacterDoc, Follower } from '../../lib/types';
  import type { Patcher } from '../../lib/patch';
  import Collapsible from '../../ui/Collapsible.svelte';
  import DebouncedText from '../../ui/DebouncedText.svelte';
  import Pips from '../../ui/Pips.svelte';
  import Stepper from '../../ui/Stepper.svelte';

  let { doc, p, editable, characterId }: { doc: CharacterDoc; p: Patcher; editable: boolean; characterId: string } = $props();
  const rules = $derived(app.content!.followers);
  const list = $derived(doc.followers ?? []);

  function add() {
    const f: Follower = {
      id: uid(), name: '', tags: [], hp: { current: 3, max: 3 }, armor: 0, damage_die: '1d4', instinct: '', cost: '',
      loyalty: 0, moves: '', gear: '', notes: '', is_group: false, members: [], fields: {},
    };
    p('/followers/-', f);
  }
</script>

<Collapsible id="followers.{characterId}" title="Followers" subtitle={list.length ? `${list.length}` : ''}>
  {#snippet right()}
    {#if editable}<button class="small" onclick={add}>+ Follower</button>{/if}
  {/snippet}
  <datalist id="follower-tags">{#each rules.tags as t}<option value={t}></option>{/each}</datalist>
  <datalist id="follower-costs">{#each rules.costs as t}<option value={t}></option>{/each}</datalist>
  <datalist id="follower-instincts">{#each rules.instincts as t}<option value={t}></option>{/each}</datalist>

  {#each list as f, i (f.id ?? i)}
    {@const base = `/followers/${i}`}
    <div class="follower">
      <div class="row top">
        <DebouncedText class="fname" value={f.name} path={`${base}/name`} readonly={!editable} placeholder="Name" />
        <label class="small"><input type="checkbox" checked={!!f.is_group} disabled={!editable} onchange={(e) => p(`${base}/is_group`, (e.target as HTMLInputElement).checked)} /> group</label>
        <span class="grow"></span>
        {#if editable}<button class="ghost small danger" onclick={() => p(base, null, 'remove')}>✕</button>{/if}
      </div>
      <div class="grid2">
        <label>Tags <DebouncedText value={(f.tags ?? []).join(', ')} onchange={(v) => p(`${base}/tags`, v.split(',').map((t) => t.trim()).filter(Boolean))} readonly={!editable} placeholder="warrior, brave" /></label>
        <label>Instinct <DebouncedText value={f.instinct} path={`${base}/instinct`} readonly={!editable} /></label>
        <label>Cost <DebouncedText value={f.cost} path={`${base}/cost`} readonly={!editable} /></label>
        <span class="row">
          <span class="lbl">HP</span>
          <Stepper value={f.hp?.current ?? 0} min={0} max={Math.max(f.hp?.max ?? 0, f.hp?.current ?? 0)} onchange={(v) => p(`${base}/hp/current`, v)} path={`${base}/hp/current`} disabled={!editable} />
          <span class="muted">/</span>
          <Stepper value={f.hp?.max ?? 0} min={1} onchange={(v) => p(`${base}/hp/max`, v)} path={`${base}/hp/max`} disabled={!editable} />
          <span class="lbl">Armor</span><Stepper value={f.armor ?? 0} min={0} onchange={(v) => p(`${base}/armor`, v)} path={`${base}/armor`} disabled={!editable} />
          <span class="lbl">Dmg</span><DebouncedText class="dmg" value={f.damage_die ?? ''} path={`${base}/damage_die`} readonly={!editable} />
        </span>
        <span class="row">
          <span class="lbl">Loyalty</span>
          <Pips value={f.loyalty ?? 0} max={rules.loyalty_max} onchange={(v) => p(`${base}/loyalty`, v)} path={`${base}/loyalty`} disabled={!editable} />
        </span>
        {#each rules.fields as c}
          <label>{c.label} <DebouncedText value={String(f.fields?.[c.id] ?? '')} path={`${base}/fields/${c.id}`} readonly={!editable} /></label>
        {/each}
        <label class="wide">Moves <DebouncedText multiline rows={2} value={f.moves ?? ''} path={`${base}/moves`} readonly={!editable} /></label>
        <label class="wide">Gear <DebouncedText value={f.gear ?? ''} path={`${base}/gear`} readonly={!editable} /></label>
        <label class="wide">Notes <DebouncedText multiline rows={2} value={f.notes ?? ''} path={`${base}/notes`} readonly={!editable} /></label>
      </div>
      {#if f.is_group}
        <div class="members">
          <span class="muted small">Members</span>
          {#each f.members ?? [] as m, j}
            <span class="row member">
              <DebouncedText value={m.name} path={`${base}/members/${j}/name`} readonly={!editable} placeholder="Name" />
              <Stepper label="HP" value={m.hp ?? 0} min={0} onchange={(v) => p(`${base}/members/${j}/hp`, v)} path={`${base}/members/${j}/hp`} disabled={!editable} />
              {#if editable}<button class="ghost small danger" onclick={() => p(`${base}/members/${j}`, null, 'remove')}>✕</button>{/if}
            </span>
          {/each}
          {#if editable}<button class="small" onclick={() => p(`${base}/members/-`, { name: '', hp: f.hp?.max ?? 3 })}>+ Member</button>{/if}
        </div>
      {/if}
    </div>
  {/each}
  {#if list.length === 0}<p class="muted small">No followers.</p>{/if}
</Collapsible>

<style>
  .follower { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: .5em .75em; margin: .4em 0; background: var(--bg); }
  .top :global(.fname) { font-weight: 600; width: 14em; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: .35em .75em; margin-top: .35em; }
  .grid2 label { display: flex; flex-direction: column; gap: .1em; }
  .lbl { color: var(--label-color); font-size: .85em; }
  .wide { grid-column: 1 / -1; }
  :global(.dmg) { width: 4em; }
  .members { margin-top: .4em; display: flex; flex-direction: column; gap: .25em; }
  @media (max-width: 600px) { .grid2 { grid-template-columns: 1fr; } }
</style>
