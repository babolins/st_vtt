<script lang="ts">
  // Text input that keeps local state while typing and emits after a pause / on blur.
  // With a `path` and a sheet context it sends diff patches (text_patch) and merges
  // remote edits into the local text while focused, preserving the caret.
  import { getContext, tick } from 'svelte';
  import DiffMatchPatch from 'diff-match-patch';
  import { SHEET, type SheetContext } from '../lib/patch';
  import { presence } from '../lib/presence.svelte';

  let {
    value, onchange, path, multiline = false, placeholder = '', readonly = false, delay = 400, rows = 3, mono = false, class: klass = '',
  }: {
    value: string; onchange?: (v: string) => void; path?: string; multiline?: boolean; placeholder?: string;
    readonly?: boolean; delay?: number; rows?: number; mono?: boolean; class?: string;
  } = $props();

  const sheet = getContext<SheetContext | undefined>(SHEET);
  const pres = $derived(path && sheet ? { entity: sheet.entity, id: sheet.id, path } : undefined);
  const dmp = new DiffMatchPatch();

  // svelte-ignore state_referenced_locally
  let local = $state(value ?? '');
  // The last value both sides agreed on; the effect below keeps it current.
  // svelte-ignore state_referenced_locally
  let base = value ?? '';
  let focused = $state(false);
  let timer: ReturnType<typeof setTimeout> | null = null;
  let el: HTMLTextAreaElement | HTMLInputElement | undefined = $state();

  $effect(() => {
    const remote = value ?? '';
    if (!focused) {
      local = remote;
      base = remote;
      return;
    }
    if (remote === base) return;
    // Merge the remote change into what is being typed.
    const before = local;
    const [merged] = dmp.patch_apply(dmp.patch_make(base, remote), before);
    base = remote;
    if (merged !== before) {
      const selStart = el?.selectionStart ?? 0;
      const selEnd = el?.selectionEnd ?? 0;
      const diffs = dmp.diff_main(before, merged);
      local = merged;
      tick().then(() => {
        if (el && document.activeElement === el) {
          el.setSelectionRange(dmp.diff_xIndex(diffs, selStart), dmp.diff_xIndex(diffs, selEnd));
        }
      });
    }
  });

  function schedule() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(flush, delay);
  }
  function flush() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (local === base) return;
    if (path && sheet) {
      const patchText = dmp.patch_toText(dmp.patch_make(base, local));
      base = local;
      sheet.p(path, local, 'text_patch', patchText);
    } else if (onchange) {
      base = local;
      onchange(local);
    }
  }
</script>

{#if multiline}
  <textarea class={klass} class:mono bind:this={el} bind:value={local} {placeholder} {readonly} {rows} use:presence={pres}
    onfocus={() => (focused = true)} onblur={() => { flush(); focused = false; }} oninput={schedule}></textarea>
{:else}
  <input type="text" class={klass} bind:this={el} bind:value={local} {placeholder} {readonly} use:presence={pres}
    onfocus={() => (focused = true)} onblur={() => { flush(); focused = false; }} oninput={schedule} />
{/if}

<style>
  .mono { font-family: var(--mono); }
</style>
