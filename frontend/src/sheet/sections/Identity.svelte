<script lang="ts">
  import type { CharacterDoc, Playbook } from '../../lib/types';
  import type { Patcher } from '../../lib/patch';
  import DebouncedText from '../../ui/DebouncedText.svelte';
  import { renderInline } from '../../lib/markdown';

  let { doc, p, editable, pb }: { doc: CharacterDoc; p: Patcher; editable: boolean; pb: Playbook | undefined } =
    $props();
</script>

<div class="identity">
  <label class="f name"
    >Name <DebouncedText value={doc.name} path={'/name'} readonly={!editable} placeholder="Name" /></label
  >
  <label class="f">Pronouns <DebouncedText value={doc.pronouns} path={'/pronouns'} readonly={!editable} /></label>
  <label class="f look"
    >Look <DebouncedText value={doc.look} path={'/look'} readonly={!editable} placeholder="How do they look?" /></label
  >
  {#if pb?.blurb}<p class="muted small blurb">{@html renderInline(pb.blurb)}</p>{/if}
</div>

<style>
  .identity {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 0.5em;
    padding: 0.5em 0;
  }
  .f {
    display: flex;
    flex-direction: column;
    gap: 0.15em;
  }
  .look,
  .blurb {
    grid-column: 1 / -1;
  }
  .name :global(input) {
    font-size: 1.15em;
    font-weight: 600;
  }
  @media (max-width: 600px) {
    .identity {
      grid-template-columns: 1fr;
    }
  }
</style>
