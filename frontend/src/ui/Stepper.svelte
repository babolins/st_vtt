<script lang="ts">
  import { getContext } from 'svelte';
  import { SHEET, type SheetContext } from '../lib/patch';
  import { presence } from '../lib/presence.svelte';

  let {
    value, min = -Infinity, max = Infinity, onchange, disabled = false, label = '', big = false, path,
  }: { value: number; min?: number; max?: number; onchange: (v: number) => void; disabled?: boolean; label?: string; big?: boolean; path?: string } = $props();
  const sheet = getContext<SheetContext | undefined>(SHEET);
  const pres = $derived(path && sheet ? { entity: sheet.entity, id: sheet.id, path } : undefined);

  function set(v: number) {
    if (Number.isNaN(v)) return;
    v = Math.max(min, Math.min(max, v));
    if (v !== value) onchange(v);
  }
</script>

<span class="stepper" class:big>
  {#if label}<span class="lbl">{label}</span>{/if}
  <button class="small" onclick={() => set(value - 1)} disabled={disabled || value <= min} aria-label="decrease">−</button>
  <input type="number" value={value} {min} {max} {disabled} use:presence={pres} onchange={(e) => set(Number((e.target as HTMLInputElement).value))} />
  <button class="small" onclick={() => set(value + 1)} disabled={disabled || value >= max} aria-label="increase">+</button>
</span>

<style>
  .stepper { display: inline-flex; align-items: center; gap: .15em; }
  .lbl { color: var(--label-color); font-size: .85em; margin-right: .25em; }
  input { width: 3.2em; text-align: center; padding: .15em .2em; -moz-appearance: textfield; appearance: textfield; }
  input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
  .big input { font-size: 1.3em; width: 2.6em; font-weight: 600; }
</style>
