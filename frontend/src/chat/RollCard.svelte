<script lang="ts">
  import { timeShort, fmtMod } from '../lib/util';
  import { api } from '../lib/api';
  import { allMoves } from '../lib/moveindex';
  import { app, canEdit, isGm, toast } from '../lib/state.svelte';
  import Markdown from '../ui/Markdown.svelte';
  import MoveBody from '../ui/MoveBody.svelte';
  import type { Message, OutcomeAction } from '../lib/types';

  let { message }: { message: Message } = $props();
  const p = $derived(message.payload);
  const tierClass = $derived(p.tier === '10+' ? 'hit' : p.tier === '7-9' ? 'mixed' : p.tier ? 'miss' : '');

  // Outcomes can be applied to the sheet they were rolled for, by whoever may edit it.
  const actions = $derived((p.actions ?? []) as OutcomeAction[]);
  const applied = $derived((p.applied ?? {}) as Record<string, { by: string; detail: string }>);
  const character = $derived(p.character_id ? app.characters[p.character_id] : undefined);
  const mayApply = $derived(p.character_id ? !!character && canEdit(character) : !!p.shared_id && (isGm() || !!app.shared[p.shared_id]));
  const debilities = $derived(app.content?.pack.debilities ?? []);
  // The dice landing is exactly when the table wants the printed move in front of
  // them, so the card can show the whole thing — the pack already has it.
  const rolled = $derived(p.move_id && app.content ? allMoves(app.content).find((e) => e.move.id === p.move_id)?.move : undefined);
  let showMove = $state(false);
  let choosing = $state<number | null>(null);

  async function apply(index: number, choice?: string) {
    choosing = null;
    try {
      await api.post(`/api/messages/${message.id}/apply`, { index, choice: choice ?? null });
    } catch (e) {
      toast((e as Error).message, 'error');
    }
  }
  function click(index: number, action: OutcomeAction) {
    if (action.kind === 'debility' && !action.id) choosing = choosing === index ? null : index;
    else apply(index);
  }
</script>

<div class="rc {tierClass}">
  <div class="row top">
    <strong>{message.author}</strong>
    {#if p.character}<span class="muted small">as {p.character}</span>{/if}
    <span class="grow"></span>
    {#if p.gm_only}<span class="tag">GM only</span>{/if}
    <span class="muted small">{timeShort(message.ts)}</span>
  </div>
  <div class="row main">
    <span class="label">{p.label}</span>
    <span class="grow"></span>
    <span class="total">{p.total}</span>
    {#if p.tier}<span class="tier">{p.tier}</span>{/if}
  </div>
  <div class="detail muted small">
    {#each p.roll.dice as d, i}
      {#if i > 0 || d.sign < 0}<span>{d.sign < 0 ? '−' : '+'}</span>{/if}
      <span class="die" title={d.die}>{d.die}: [{d.results.map((r: number) => (d.kept.includes(r) ? r : `~${r}~`)).join(' ')}]</span>
    {/each}
    {#if p.roll.modifier}<span>{fmtMod(p.roll.modifier)}</span>{/if}
    {#if p.stat_label}<span>{fmtMod(p.stat_mod)} {p.stat_label}</span>{/if}
    {#each p.modifiers ?? [] as m}<span>{fmtMod(m.value)} {m.option}</span>{/each}
    {#if p.bonus}<span>{fmtMod(p.bonus)} total bonus</span>{/if}
    {#if p.mode && p.mode !== 'normal'}<span class="pill">{p.mode === 'both' ? 'adv + disadv' : p.mode}</span>{/if}
    {#if p.auto_disadvantage?.length}<span class="pill warn">{p.auto_disadvantage.join(', ')}</span>{/if}
  </div>
  {#if p.outcome}
    <Markdown text={p.outcome} class="outcome" />
  {/if}
  {#if rolled}
    <button class="ghost small showmove" onclick={() => (showMove = !showMove)} aria-expanded={showMove}>
      {showMove ? '▾' : '▸'} the move
    </button>
    {#if showMove}
      <div class="movebody"><MoveBody move={rolled} /></div>
    {/if}
  {/if}
  {#if actions.length}
    <div class="row actions">
      {#each actions as a, i}
        {#if applied[String(i)]}
          <span class="small done" title="applied by {applied[String(i)].by}">✓ {applied[String(i)].detail}</span>
        {:else if mayApply}
          <button class="small" onclick={() => click(i, a)}>{a.label}</button>
        {:else}
          <span class="small muted">{a.label}</span>
        {/if}
      {/each}
    </div>
    {#if choosing !== null}
      <div class="row actions">
        <span class="muted small">Which debility?</span>
        {#each debilities as d}
          <button class="small" disabled={!!character?.data.debilities[d.id]}
            onclick={() => apply(choosing!, d.id)}>{d.label}</button>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .showmove { padding: .1em .2em; margin-top: .2em; }
  .movebody { border-top: 1px solid var(--border); margin-top: .3em; padding-top: .3em; }
  .rc { border: 1px solid var(--border); border-left: 4px solid var(--border); border-radius: 6px; padding: .4em .6em; background: var(--bg); }
  .rc.hit { border-left-color: var(--ok); }
  .rc.mixed { border-left-color: var(--warn); }
  .rc.miss { border-left-color: var(--bad); }
  .top { gap: .4em; }
  .main { gap: .5em; margin: .15em 0; }
  .label { font-weight: 600; }
  .total { font-size: 1.4em; font-weight: 700; font-variant-numeric: tabular-nums; }
  .tier { font-weight: 600; padding: 0 .5em; border-radius: 999px; background: var(--bg-sunken); }
  .hit .tier { color: var(--ok); } .mixed .tier { color: var(--warn); } .miss .tier { color: var(--bad); }
  .detail { display: flex; gap: .4em; flex-wrap: wrap; font-family: var(--mono); }
  .pill.warn { color: var(--warn); border-color: var(--warn); }
  .actions { gap: .35em; margin-top: .35em; flex-wrap: wrap; }
  .done { color: var(--ok); font-weight: 600; }
  :global(.rc .outcome) { margin-top: .3em; padding-top: .3em; border-top: 1px dashed var(--border); }
</style>
