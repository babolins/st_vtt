<script lang="ts">
  import { isGm } from '../../lib/state.svelte';
  import type { CharacterDoc, SharedDoc } from '../../lib/types';
  import type { Patcher } from '../../lib/patch';
  import Collapsible from '../../ui/Collapsible.svelte';
  import DebouncedText from '../../ui/DebouncedText.svelte';
  import Markdown from '../../ui/Markdown.svelte';

  let { doc, p, editable, id }: { doc: CharacterDoc | SharedDoc; p: Patcher; editable: boolean; id: string } = $props();
  let preview = $state(false);
  let gmPreview = $state(false);
</script>

<Collapsible id="notes.{id}" title="Notes">
  {#snippet right()}
    <button class="ghost small" onclick={() => (preview = !preview)}>{preview ? 'Edit' : 'Preview'}</button>
  {/snippet}
  {#if preview || !editable}
    <Markdown text={doc.notes || '_No notes._'} />
  {:else}
    <DebouncedText
      multiline
      rows={6}
      value={doc.notes ?? ''}
      path={'/notes'}
      placeholder="Notes (markdown). Everyone at the table can read these."
    />
  {/if}
</Collapsible>

{#if isGm()}
  <Collapsible id="gmnotes.{id}" title="GM notes" open={false}>
    {#snippet right()}
      <button class="ghost small" onclick={() => (gmPreview = !gmPreview)}>{gmPreview ? 'Edit' : 'Preview'}</button>
    {/snippet}
    {#if gmPreview}
      <Markdown text={doc.gm_notes || '_No GM notes._'} />
    {:else}
      <DebouncedText
        multiline
        rows={4}
        value={doc.gm_notes ?? ''}
        path={'/gm_notes'}
        placeholder="Only the GM sees these."
      />
    {/if}
  </Collapsible>
{/if}
