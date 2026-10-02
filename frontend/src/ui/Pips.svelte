<script lang="ts">
  // A row of boxes. The shape carries the meaning, as it does in the book: a diamond is one box
  // of carried load, a circle is a use or an ammo status, a square is a plain tick.
  import { getContext } from 'svelte';
  import { SHEET, type SheetContext } from '../lib/patch';
  import { presence } from '../lib/presence.svelte';

  let {
    value,
    max,
    onchange,
    disabled = false,
    path,
    shape = 'diamond',
    labels,
  }: {
    value: number;
    max: number;
    onchange: (v: number) => void;
    disabled?: boolean;
    path?: string;
    shape?: 'diamond' | 'circle' | 'square';
    /** one label per box, shown beside it (ammo statuses) */
    labels?: string[];
  } = $props();
  const sheet = getContext<SheetContext | undefined>(SHEET);
  const pres = $derived(path && sheet ? { entity: sheet.entity, id: sheet.id, path } : undefined);
  function click(i: number) {
    onchange(value === i + 1 ? i : i + 1);
  }
</script>

<span class="pips" class:labelled={!!labels} title="{value}/{max}" use:presence={pres} tabindex="-1">
  {#each Array(max) as _, i}
    {#if labels}
      <span class="labelled-pip">
        <button class="pip {shape}" class:on={i < value} onclick={() => click(i)} {disabled} aria-label={labels[i]}
        ></button>
        <span class="small muted">{labels[i]}</span>
      </span>
    {:else}
      <button class="pip {shape}" class:on={i < value} onclick={() => click(i)} {disabled} aria-label="pip {i + 1}"
      ></button>
    {/if}
  {/each}
</span>

<style>
  .pips.labelled {
    gap: 0.5em;
  }
  .labelled-pip {
    display: inline-flex;
    align-items: baseline;
    gap: 0.25em;
    white-space: nowrap;
  }
</style>
