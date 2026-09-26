<script lang="ts">
  // One option: its checkbox/radio, an optional write-in box, its boxes, and — when selected —
  // its nested sub-choice, rendered recursively. A `note` option is prose instead: no control,
  // and its boxes and sub-choice are always shown.
  import type { Option, TrackKind, TrackState } from '../../lib/types';
  import { renderInline } from '../../lib/markdown';
  import type { Patcher } from '../../lib/patch';
  import DebouncedText from '../../ui/DebouncedText.svelte';
  import Tracks from '../../ui/Tracks.svelte';
  import OptionRow from './OptionRow.svelte';
  import { presence } from '../../lib/presence.svelte';

  let {
    option, sectionId, selected, editable, kind, group, basePath, presencePath,
    tracksOf, textOf, childrenOf, onselect, ontrack, ontext, onchild, depth = 0,
  }: {
    option: Option;
    sectionId: string;
    selected: boolean;
    editable: boolean;
    kind: 'radio' | 'checkbox';
    group: string;
    basePath: string;
    presencePath: { entity: string; id: string; path: string } | undefined;
    tracksOf: (id: string) => TrackState | undefined;
    textOf: (id: string) => string;
    childrenOf: (id: string) => string[];
    onselect: (id: string) => void;
    ontrack: (id: string, kind: TrackKind, v: number) => void;
    ontext: (id: string, v: string) => void;
    onchild: (parentId: string, childId: string, on: boolean, max: number | null) => void;
    depth?: number;
  } = $props();

  const chosen = $derived(childrenOf(option.id));
  const subKind = $derived(option.max === 1 ? 'radio' : 'checkbox');
  const subHint = $derived(
    option.min != null && option.max != null && option.min === option.max ? `pick ${option.min}`
      : option.max != null ? `up to ${option.max}`
      : option.min != null ? `pick ${option.min}+` : '',
  );
  const atMax = $derived(option.max != null && chosen.length >= option.max);
  // A note is prose, not a pick: it is always "open", so its boxes and children always show.
  const open = $derived(option.note || selected);
</script>

{#if option.note}
  <div class="opt note">
    <span class="body">
      <strong>{@html renderInline(option.label)}</strong>{#if option.text}<span class="muted">&nbsp;— {@html renderInline(option.text)}</span>{/if}
    </span>
    <Tracks tracks={option.tracks} state={tracksOf(option.id)}
      onchange={(kind, v) => ontrack(option.id, kind, v)} path={`${basePath}/${option.id}`} disabled={!editable} />
  </div>
{:else}
  <label class="opt" class:sel={selected} class:ro={!editable}>
    {#if kind === 'radio'}
      <input type="radio" name={group} checked={selected} disabled={!editable} use:presence={presencePath} onchange={() => onselect(option.id)} />
    {:else}
      <input type="checkbox" checked={selected} disabled={!editable} use:presence={presencePath} onchange={() => onselect(option.id)} />
    {/if}
    <span class="body">
      <strong>{@html renderInline(option.label)}</strong>{#if option.text}<span class="muted">&nbsp;— {@html renderInline(option.text)}</span>{/if}
    </span>
    {#if selected}
      <Tracks tracks={option.tracks} state={tracksOf(option.id)}
        onchange={(kind, v) => ontrack(option.id, kind, v)} path={`${basePath}/${option.id}`} disabled={!editable} />
    {/if}
  </label>
{/if}

{#if selected && option.write_in !== null}
  <div class="writein" style="--depth: {depth}">
    <DebouncedText value={textOf(option.id)} placeholder={option.write_in || '…'} readonly={!editable}
      onchange={(v) => ontext(option.id, v)} />
  </div>
{/if}

{#if open && option.options.length}
  <div class="subchoice" style="--depth: {depth}">
    {#if subHint}<div class="muted small hint">{subHint}</div>{/if}
    {#each option.options as child (child.id)}
      <OptionRow
        option={child}
        {sectionId}
        selected={chosen.includes(child.id)}
        editable={editable && (chosen.includes(child.id) || !atMax)}
        kind={subKind}
        group={`${group}.${option.id}`}
        {basePath}
        {presencePath}
        {tracksOf}
        {textOf}
        {childrenOf}
        onselect={(id) => onchild(option.id, id, !chosen.includes(id), option.max)}
        {ontrack}
        {ontext}
        {onchild}
        depth={depth + 1}
      />
    {/each}
  </div>
{/if}

<style>
  .opt { display: flex; gap: .5em; align-items: baseline; padding: .25em .5em; border-radius: var(--radius-sm); cursor: pointer; color: var(--fg); font-size: 1em; }
  .opt.sel { background: var(--accent-soft); }
  .opt.ro, .opt.note { cursor: default; }
  .opt.note { padding-top: .45em; }
  .opt input { margin: 0; position: relative; top: .1em; }
  .body { flex: 1; }
  .opt :global(.tracks) { margin-left: auto; }
  .writein { margin: .1em 0 .4em calc(1.6em + var(--depth) * 1.25em); max-width: 34em; }
  .writein :global(input) { width: 100%; }
  .subchoice { margin-left: calc(1.25em + var(--depth) * 1.25em); border-left: 2px solid var(--border); padding-left: .5em; }
  .hint { padding: 0 .5em .1em; }
</style>
