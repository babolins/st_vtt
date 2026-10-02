<script lang="ts">
  import type { Snippet } from 'svelte';
  let { title, onclose, children }: { title: string; onclose: () => void; children: Snippet } = $props();
  function key(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }
</script>

<svelte:window onkeydown={key} />
<div class="overlay" onclick={onclose} onkeydown={key} role="presentation">
  <div
    class="card dlg"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
    role="dialog"
    aria-label={title}
    tabindex="-1"
  >
    <div class="row head">
      <h3 class="grow">{title}</h3>
      <button class="ghost small" onclick={onclose} aria-label="close">✕</button>
    </div>
    <div class="body">{@render children()}</div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    display: grid;
    place-items: center;
    z-index: 50;
    padding: 1em;
  }
  .dlg {
    width: min(30em, 100%);
    max-height: 90vh;
    overflow: auto;
  }
  .head {
    padding: 0.6em 0.9em;
    border-bottom: 1px solid var(--border);
  }
  .body {
    padding: 0.9em;
  }
</style>
