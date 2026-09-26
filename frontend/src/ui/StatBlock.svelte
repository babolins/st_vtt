<script lang="ts" generics="S extends Stat">
  // The row of stat boxes across the top of a sheet, character or shared.
  //
  // How narrow a box may get depends on the content pack, not the stylesheet:
  // the widest value a stat can hold (from its min and max) and the longest word
  // in any label. Both are counted here and handed to the CSS in characters, so
  // a pack with a 0..12 stat or a "Fortifications" label gets wide enough boxes
  // without anyone tuning a number.
  import type { Snippet } from 'svelte';
  import type { Stat } from '../lib/types';
  import { fmtMod } from '../lib/util';

  let { stats, value, warn, title }: {
    stats: S[];
    /** The box's content under the label: a stepper, or the value read-only. */
    value: Snippet<[S]>;
    /** Box this stat in the warn colour (a debility gives its rolls disadvantage). */
    warn?: (s: S) => boolean;
    title?: (s: S) => string;
  } = $props();

  const valueCh = $derived(Math.max(1, ...stats.flatMap((s) => [fmtMod(s.min).length, fmtMod(s.max).length])));
  // Labels wrap between words, so only the longest word needs to fit on a line.
  const labelCh = $derived(Math.max(1, ...stats.flatMap((s) => s.label.split(/\s+/).map((w) => w.length))));
</script>

<div class="stats" style:--value-ch={valueCh} style:--label-ch={labelCh}>
  {#each stats as s (s.id)}
    <div class="stat" class:dis={warn?.(s)} title={title?.(s) ?? ''}>
      <div class="lbl">{s.label}</div>
      {@render value(s)}
    </div>
  {/each}
</div>

<style>
  /* Widths in the .stats font, measured against the stepper: its two buttons and
     gaps take about 3.7em; the value sits in a 1.3em input with .2em padding a
     side and a 1px border; a bold digit runs a little over 1ch at that size, and
     an uppercase label letter at .75em a little under it. Each estimate is
     rounded up, so a box is never narrower than what it holds -- unless the
     whole row is narrower than one box (a phone), when the box takes the row. */
  .stats {
    --value-w: calc(var(--value-ch) * 1.45ch + .52em + 2px);
    --stepper-w: calc(var(--value-w) + 3.8em);
    --label-w: calc(var(--label-ch) * 1ch);
    --box-w: calc(max(var(--stepper-w), var(--label-w)) + .6em + 2 * var(--stat-border-width));
    display: grid; grid-template-columns: repeat(auto-fit, minmax(min(var(--box-w), 100%), 1fr)); gap: .4em; margin: .25em 0;
  }
  .stat {
    text-align: center; border: var(--stat-border-width) solid var(--border); border-radius: var(--radius-sm); padding: .3em;
    border-image: var(--stat-border-image) 8 / var(--stat-border-width) round; background: var(--stat-bg);
    min-width: 0;
  }
  .stat.dis { border-color: var(--warn); border-image-source: var(--stat-border-image-warn); }
  /* A single word too long for any box breaks rather than spilling out. */
  .lbl { font-size: .75em; letter-spacing: .06em; color: var(--label-color); text-transform: var(--label-case); overflow-wrap: anywhere; }
  /* The stepper centres in its box and its input gives up width before anything
     overflows, down to what the widest value needs. */
  .stat :global(.stepper) { max-width: 100%; }
  .stat :global(.stepper button) { flex: none; }
  .stat :global(.stepper.big input) { flex: 0 1 2.6em; min-width: calc(var(--value-ch) * 1.1ch + .4em + 2px); }
</style>
