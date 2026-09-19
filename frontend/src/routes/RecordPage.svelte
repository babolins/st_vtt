<script lang="ts">
  /** A record at its own address, for linking to and reloading into. */
  import { app } from '../lib/state.svelte';
  import { go } from '../lib/router.svelte';
  import RecordCard from '../ui/RecordCard.svelte';

  let { id }: { id: string } = $props();
  const row = $derived(app.records[id]);
</script>

<div class="card page">
  {#if row}
    <RecordCard {row} />
  {:else}
    <p class="muted">No record with the id <code>{id}</code> — it may have been deleted, or be the GM's alone.</p>
    <button class="small" onclick={() => go({ kind: 'people' })}>Back to people</button>
  {/if}
</div>

<style>
  .page { padding: .75em 1em 1em; max-width: 46em; }
</style>
