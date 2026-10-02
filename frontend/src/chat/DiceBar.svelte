<script lang="ts">
  import { app, isGm, myCharacters } from '../lib/state.svelte';
  import { send } from '../lib/ws';

  let characterId = $state<string | null>(null);
  let gmOnly = $state(false);
  let adv = $state(false);
  let disadv = $state(false);
  let custom = $state('');
  const mine = $derived(isGm() ? Object.values(app.characters) : myCharacters());

  $effect(() => {
    if (!characterId || !app.characters[characterId]) characterId = mine[0]?.id ?? null;
  });

  function rollExpr(expr: string, label: string) {
    let e = expr;
    if ((adv || disadv) && !(adv && disadv) && /^\s*2d6\s*$/.test(e)) e = adv ? '3d6kh2' : '3d6kl2';
    send({ type: 'roll', expr: e, label, character_id: characterId, gm_only: gmOnly }).catch(() => {});
  }
  function rollCustom(e: Event) {
    e.preventDefault();
    if (custom.trim()) rollExpr(custom.trim(), custom.trim());
  }
</script>

<div class="bar">
  <div class="row">
    {#each app.content?.pack.dice_presets ?? [] as p}
      <button class="small" onclick={() => rollExpr(p.expr, p.label)} title={p.expr}>{p.label}</button>
    {/each}
    {#each [20] as n}
      <button class="small" onclick={() => rollExpr(`1d${n}`, `d${n}`)}>d{n}</button>
    {/each}
    <form class="row custom" onsubmit={rollCustom}>
      <input type="text" placeholder="2d8kh1+2" bind:value={custom} class="kbd" />
      <button class="small">Roll</button>
    </form>
  </div>
  <div class="row opts">
    {#if mine.length > 1}
      <select bind:value={characterId}>
        {#each mine as c}<option value={c.id}>{c.data.name || '(unnamed)'}</option>{/each}
      </select>
    {/if}
    <label><input type="checkbox" bind:checked={adv} /> adv</label>
    <label><input type="checkbox" bind:checked={disadv} /> disadv</label>
    <label><input type="checkbox" bind:checked={gmOnly} /> GM only</label>
  </div>
</div>

<style>
  .bar {
    border-top: 1px solid var(--border);
    padding: 0.4em 0.75em;
    display: flex;
    flex-direction: column;
    gap: 0.3em;
    background: var(--bg);
  }
  .custom input {
    width: 7em;
  }
  .opts {
    font-size: 0.9em;
  }
  .opts label {
    display: inline-flex;
    gap: 0.25em;
    align-items: center;
  }
</style>
