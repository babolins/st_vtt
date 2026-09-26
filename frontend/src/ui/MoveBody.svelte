<script lang="ts">
  /** A move, printed.
   *
   *  The one place a move's text is rendered: on a sheet, in a search result, on a
   *  card shared to the table, under a roll. Fidelity to the printed playbook —
   *  the trigger in italic, tier labels set in the margin, the hold note last —
   *  is fixed here once rather than re-achieved in four components, which is what
   *  the three earlier copies of this markup kept failing to do.
   */
  import type { CharacterDoc, Move, Outcome, SharedDoc } from '../lib/types';
  import type { Patcher } from '../lib/patch';
  import { renderInline } from '../lib/markdown';
  import Markdown from './Markdown.svelte';
  import MoveOptions from '../sheet/sections/MoveOptions.svelte';

  let {
    move, density = 'full', doc, p, editable = false,
  }: {
    move: Move;
    /** 'full' prints everything; 'brief' is the trigger alone, for a list of results */
    density?: 'full' | 'brief';
    doc?: CharacterDoc | SharedDoc;
    p?: Patcher;
    editable?: boolean;
  } = $props();

  const outcomes = $derived(Object.entries(move.outcomes ?? {}) as [string, Outcome | string][]);
  const textOf = (o: Outcome | string) => (typeof o === 'string' ? o : (o?.text ?? ''));
</script>

{#if move.trigger}
  <p class="trigger">{@html renderInline(move.trigger)}</p>
{/if}

{#if density === 'full'}
  {#if move.text}<Markdown text={move.text} />{/if}

  {#if outcomes.length}
    <dl class="outcomes">
      {#each outcomes as [tier, outcome]}
        <dt>{tier}</dt>
        <dd><Markdown text={textOf(outcome)} /></dd>
      {/each}
    </dl>
  {/if}

  {#if move.options?.length && doc && p}
    <MoveOptions {move} {doc} {p} {editable} />
  {/if}

  {#if move.hold}
    <p class="hold"><span class="hold-name">Hold: {move.hold.name}</span>{#if move.hold.note} — {move.hold.note}{/if}</p>
  {/if}
{/if}

<style>
  .trigger { color: var(--fg-muted); font-style: italic; margin: 0 0 .4em; }
  .outcomes { display: grid; grid-template-columns: auto 1fr; gap: .15em .6em; margin: .3em 0 0; }
  .outcomes dt { font-weight: 600; color: var(--fg-muted); font-variant-numeric: tabular-nums; }
  .outcomes dd { margin: 0; }
  .hold { font-size: .9em; color: var(--fg-muted); margin: .4em 0 0; }
  .hold-name { font-weight: 600; }
</style>
