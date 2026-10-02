<script lang="ts">
  // The checklist some moves carry: "each time you take this move, pick 1". Unlike the lists a
  // move prints for a choice made at roll time, these picks stay on the sheet — so they are
  // stored the way a section's are, keyed by the move instead of by a section.
  import { getContext } from 'svelte';
  import type { CharacterDoc, Move, SharedDoc, TrackKind, TrackState } from '../../lib/types';
  import { SHEET, type Patcher, type SheetContext } from '../../lib/patch';
  import OptionRow from './OptionRow.svelte';

  let {
    move,
    doc,
    p,
    editable,
  }: {
    move: Move;
    doc: CharacterDoc | SharedDoc;
    p: Patcher;
    editable: boolean;
  } = $props();

  const sheet = getContext<SheetContext | undefined>(SHEET);
  const path = $derived(`/moves/options/${move.id}`);
  const picks = $derived(doc.moves.options[move.id] ?? []);
  const single = $derived(move.max === 1);
  const atMax = $derived(move.max != null && picks.length >= move.max);
  const hint = $derived(
    move.min != null && move.max != null && move.min === move.max
      ? `pick ${move.min}`
      : move.max != null
        ? `up to ${move.max}`
        : move.min != null
          ? `pick ${move.min}+`
          : '',
  );
  const group = $derived(sheet ? `${sheet.entity}.${sheet.id}.${move.id}` : move.id);
  const pres = $derived(sheet ? { entity: sheet.entity, id: sheet.id, path } : undefined);

  function toggle(id: string) {
    if (!editable) return;
    const on = picks.includes(id);
    if (single) return void p(path, on ? [] : [id]);
    if (!on && atMax) return;
    p(path, id, on ? 'list_remove' : 'list_add');
  }
  const tracksOf = (oid: string) => doc.option_tracks[move.id]?.[oid] as TrackState | undefined;
  const textOf = (oid: string) => String(doc.option_text[move.id]?.[oid] ?? '');
  const childrenOf = (oid: string) => doc.sub_choices[move.id]?.[oid] ?? [];
  const setTrack = (oid: string, kind: TrackKind, v: number) => p(`/option_tracks/${move.id}/${oid}/${kind}`, v);
  const setText = (oid: string, v: string) => p(`/option_text/${move.id}/${oid}`, v);
  function setChild(parentId: string, childId: string, on: boolean, max: number | null) {
    if (!editable) return;
    const sub = `/sub_choices/${move.id}/${parentId}`;
    if (max === 1) p(sub, on ? [childId] : []);
    else p(sub, childId, on ? 'list_add' : 'list_remove');
  }
</script>

<div class="moveopts">
  {#if hint}<div class="muted small hint">{hint}</div>{/if}
  {#each move.options as o (o.id)}
    <OptionRow
      option={o}
      sectionId={move.id}
      selected={picks.includes(o.id)}
      editable={editable && (single || picks.includes(o.id) || !atMax)}
      kind={single ? 'radio' : 'checkbox'}
      {group}
      basePath={`/option_tracks/${move.id}`}
      presencePath={pres}
      {tracksOf}
      {textOf}
      {childrenOf}
      onselect={toggle}
      ontrack={setTrack}
      ontext={setText}
      onchild={setChild}
    />
  {/each}
</div>

<style>
  .moveopts {
    display: flex;
    flex-direction: column;
    gap: 0.1em;
    margin: 0.3em 0 0.1em;
  }
  .hint {
    padding: 0 0.5em;
  }
</style>
