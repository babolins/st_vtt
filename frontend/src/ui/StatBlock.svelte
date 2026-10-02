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
  import { balancedRows, fitCount, placements } from '../lib/statrows';

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

  // How many boxes fit a row is the CSS's call (--box-w, from the counts above);
  // a hidden probe reports it in pixels, and the rows are balanced from there.
  // Until then the CSS lays the boxes out alone (greedily, but never crushed).
  let el = $state<HTMLElement>();
  let row = $state<DOMRectReadOnly>();
  let probe = $state<DOMRectReadOnly>();
  const width = $derived(row?.width ?? 0);
  const box = $derived(probe?.width ?? 0); // a box's minimum width
  // Read again whenever either is measured: a font change moves all three.
  const gap = $derived.by(() => {
    void width; void box;
    return el ? parseFloat(getComputedStyle(el).columnGap) || 0 : 0;
  });
  const fit = $derived(fitCount(width, box, gap));
  const rows = $derived(fit === null ? null : balancedRows(stats.length, fit));
  const places = $derived(rows ? placements(rows) : []);
</script>

<div
  class="stats" bind:this={el} bind:contentRect={row}
  style:--value-ch={valueCh} style:--label-ch={labelCh}
  style:grid-template-columns={rows ? `repeat(${2 * (rows[0] ?? 1)}, minmax(0, 1fr))` : null}
>
  <div class="probes" aria-hidden="true"><div class="probe" bind:contentRect={probe}></div></div>
  {#each stats as s, i (s.id)}
    <div
      class="stat" class:dis={warn?.(s)} title={title?.(s) ?? ''}
      style:grid-row={places[i]?.row} style:grid-column={places[i] ? `${places[i].column} / span 2` : null}
    >
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
     whole row is narrower than one box (a phone), when the box takes the row.
     Once measured, the grid has two tracks per box so a short row can start
     half a box in; the script sets how many, and where each box goes. */
  .stats {
    --value-w: calc(var(--value-ch) * 1.45ch + .52em + 2px);
    --stepper-w: calc(var(--value-w) + 3.8em);
    --label-w: calc(var(--label-ch) * 1ch);
    --box-w: calc(max(var(--stepper-w), var(--label-w)) + .6em + 2 * var(--stat-border-width));
    --gap: .4em;
    display: grid; gap: var(--gap); margin: .25em 0; position: relative;
    grid-template-columns: repeat(auto-fill, minmax(min(var(--box-w), 100%), 1fr));
  }
  /* The probe is a box's minimum width, which can be wider than the row; its
     zero-size holder clips it so it measures without making the page scroll. */
  .probes { position: absolute; width: 0; height: 0; overflow: hidden; visibility: hidden; }
  .probe { width: var(--box-w); height: 0; }
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
