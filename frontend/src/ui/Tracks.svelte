<script lang="ts">
  // Every box an option or a move declares, each drawn as its own glyph and stored under its own
  // key: {"bulk": 1, "uses": 2, "statuses": 1} counts how many of each are marked.
  import Pips from './Pips.svelte';
  import { trackKinds, type TrackKind, type TrackState, type Tracks } from '../lib/types';

  let {
    tracks,
    state,
    onchange,
    disabled = false,
    path,
  }: {
    tracks: Tracks | undefined;
    state: TrackState | undefined;
    onchange: (kind: TrackKind, v: number) => void;
    disabled?: boolean;
    path?: string;
  } = $props();

  const kinds = $derived(trackKinds(tracks));
  const SHAPE = { marks: 'square', bulk: 'diamond', uses: 'circle', statuses: 'circle' } as const;
  const TITLE = { marks: 'progress', bulk: 'bulk (carried load)', uses: 'uses', statuses: 'ammo' } as const;
</script>

{#if kinds.length}
  <span class="tracks">
    {#each kinds as k (k.kind)}
      <span class="track" title={TITLE[k.kind]}>
        <Pips
          value={state?.[k.kind] ?? 0}
          max={k.boxes}
          shape={SHAPE[k.kind]}
          labels={k.labels}
          onchange={(v) => onchange(k.kind, v)}
          {disabled}
          path={path ? `${path}/${k.kind}` : undefined}
        />
      </span>
    {/each}
  </span>
{/if}

<style>
  .tracks {
    display: inline-flex;
    gap: 0.7em;
    align-items: baseline;
    flex-wrap: wrap;
  }
</style>
