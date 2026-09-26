<script lang="ts">
  import { app } from '../../lib/state.svelte';
  import { fmtMod, levelUpCost } from '../../lib/util';
  import type { CharacterDoc, Playbook } from '../../lib/types';
  import type { Patcher } from '../../lib/patch';
  import Stepper from '../../ui/Stepper.svelte';
  import { getContext } from 'svelte';
  import { SHEET, type SheetContext } from '../../lib/patch';
  import { presence } from '../../lib/presence.svelte';

  let { doc, p, editable, pb }: { doc: CharacterDoc; p: Patcher; editable: boolean; pb: Playbook | undefined } = $props();
  const content = $derived(app.content!);
  const cost = $derived(levelUpCost(content.pack.xp.level_up_cost, doc.level));
  const canLevel = $derived(doc.xp >= cost);
  const array = $derived(pb?.stat_array ?? content.pack.stat_array);
  const sheet = getContext<SheetContext | undefined>(SHEET);
  const pres = (path: string) => (sheet ? { entity: sheet.entity, id: sheet.id, path } : undefined);

  function levelUp() {
    p('/xp', doc.xp - cost);
    p('/level', doc.level + 1);
  }
</script>

<div class="stats statblock">
  {#each content.pack.stats as s}
    {@const affected = content.pack.debilities.filter((d) => doc.debilities[d.id] && d.affects.includes(s.id))}
    <div class="stat" class:dis={affected.length > 0} title={affected.length ? `Disadvantage: ${affected.map((d) => d.label).join(', ')}` : ''}>
      <div class="lbl">{s.label}</div>
      {#if editable}
        <Stepper value={doc.stats?.[s.id] ?? 0} min={s.min} max={s.max} onchange={(v) => p(`/stats/${s.id}`, v)} path={`/stats/${s.id}`} big />
      {:else}
        <div class="val">{fmtMod(doc.stats?.[s.id] ?? 0)}</div>
      {/if}
    </div>
  {/each}
</div>
{#if array.length && editable && !doc.creation_done}
  <div class="muted small">Assign {array.map((n) => fmtMod(n)).join(', ')}</div>
{/if}

<div class="row vitals">
  <span class="vital">
    <span class="lbl">HP</span>
    <Stepper value={doc.hp.current} min={0} max={Math.max(doc.hp.max, doc.hp.current)} onchange={(v) => p('/hp/current', v)} path={'/hp/current'} disabled={!editable} big />
    <span class="muted">/</span>
    <Stepper value={doc.hp.max} min={1} onchange={(v) => p('/hp/max', v)} path={'/hp/max'} disabled={!editable} />
  </span>
  <span class="vital"><span class="lbl">Armor</span><Stepper value={doc.armor} min={0} onchange={(v) => p('/armor', v)} path={'/armor'} disabled={!editable} /></span>
  <span class="vital"><span class="lbl">Damage</span><span class="kbd">{pb?.damage_die ?? '—'}</span></span>
  <span class="vital">
    <span class="lbl">XP</span>
    <Stepper value={doc.xp} min={0} max={content.pack.xp.max_xp ?? Infinity} onchange={(v) => p('/xp', v)} path={'/xp'} disabled={!editable} />
    <span class="muted small">/ {cost}</span>
  </span>
  <span class="vital">
    <span class="lbl">Level</span>
    <Stepper value={doc.level} min={1} onchange={(v) => p('/level', v)} path={'/level'} disabled={!editable} />
    {#if editable && canLevel}<button class="small primary" onclick={levelUp} title="Spend {cost} XP">Level up!</button>{/if}
  </span>
</div>

<div class="row debils">
  {#each content.pack.debilities as d}
    <label class="deb" title={d.text}>
      <input type="checkbox" checked={doc.debilities[d.id]} disabled={!editable} use:presence={pres(`/debilities/${d.id}`)} onchange={(e) => p(`/debilities/${d.id}`, (e.target as HTMLInputElement).checked)} />
      {d.label}
    </label>
  {/each}
</div>

<style>
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(6.5em, 1fr)); gap: .4em; margin: .25em 0; }
  .stat { text-align: center; border: 1px solid var(--border); border-radius: 6px; padding: .3em; background: var(--bg); }
  .stat.dis { border-color: var(--warn); }
  .lbl { font-size: .75em; letter-spacing: .06em; color: var(--fg-muted); text-transform: uppercase; }
  .val { font-size: 1.4em; font-weight: 700; }
  .vitals { margin: .5em 0; gap: 1em; }
  .vital { display: inline-flex; align-items: center; gap: .3em; }
  .debils { gap: 1em; margin-bottom: .5em; }
  .deb { display: inline-flex; align-items: center; gap: .3em; color: var(--fg); cursor: pointer; }
</style>
