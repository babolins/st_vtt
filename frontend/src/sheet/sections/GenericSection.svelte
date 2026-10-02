<script lang="ts">
  // Renders a declarative content-pack section against a value stored in doc.sections[id].
  import type { CharacterDoc, Effects, Section, SharedDoc, TrackKind, TrackState } from '../../lib/types';
  import { app } from '../../lib/state.svelte';
  import { send } from '../../lib/ws';
  import type { Patcher } from '../../lib/patch';
  import Collapsible from '../../ui/Collapsible.svelte';
  import DebouncedText from '../../ui/DebouncedText.svelte';
  import Pips from '../../ui/Pips.svelte';
  import OptionRow from './OptionRow.svelte';
  import { getContext } from 'svelte';
  import { SHEET, type SheetContext } from '../../lib/patch';
  import { presence } from '../../lib/presence.svelte';
  import { renderInline } from '../../lib/markdown';
  import { at } from '../../lib/pointer';
  import { uid } from '../../lib/util';

  let {
    section,
    value,
    editable,
    basePath,
    doc,
    p,
    idPrefix = '',
  }: {
    section: Section;
    value: unknown;
    editable: boolean;
    basePath: string;
    doc?: CharacterDoc | SharedDoc;
    p: Patcher;
    idPrefix?: string;
  } = $props();
  const onchange = (v: unknown) => p(basePath, v);

  const s = $derived(section);
  const sheet = getContext<SheetContext | undefined>(SHEET);
  const pres = (path: string) => (sheet ? { entity: sheet.entity, id: sheet.id, path } : undefined);
  const arr = $derived(Array.isArray(value) ? (value as any[]) : []);
  const obj = $derived(
    value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, any>) : null,
  );

  /** Apply (+1) or undo (-1) an option's effects on the character document. */
  function effects(e: Effects | null | undefined, sign: 1 | -1) {
    if (!e || !p || !doc || !('moves' in doc) || !('taken' in (doc as CharacterDoc).moves)) return;
    const c = doc as CharacterDoc;
    for (const id of e.moves) p('/moves/taken', id, sign > 0 ? 'list_add' : 'list_remove');
    for (const id of e.inserts ?? []) {
      p('/inserts', id, sign > 0 ? 'list_add' : 'list_remove');
      const ins = app.content?.inserts.find((i) => i.id === id);
      for (const mid of ins?.starting_moves.fixed ?? []) p('/moves/taken', mid, sign > 0 ? 'list_add' : 'list_remove');
    }
    if (e.armor) p('/armor', Math.max(0, (c.armor ?? 0) + sign * e.armor));
    if (e.hp) {
      p('/hp/max', Math.max(1, c.hp.max + sign * e.hp));
      p('/hp/current', Math.max(0, c.hp.current + sign * e.hp));
    }
  }

  function choose(id: string) {
    if (!editable) return;
    const prev = s.options.find((o) => o.id === value);
    const next = s.options.find((o) => o.id === id);
    if (prev?.id === id) return;
    effects(prev?.effects, -1);
    if (prev?.options.length) p(`/sub_choices/${s.id}/${prev.id}`, []);
    onchange(id);
    effects(next?.effects, 1);
  }
  function toggle(id: string, applyEffects: boolean) {
    if (!editable) return;
    const on = arr.includes(id);
    const opt = s.options.find((o) => o.id === id);
    if (!on && s.max != null && arr.length >= s.max) return;
    p(basePath, id, on ? 'list_remove' : 'list_add');
    if (on && opt?.options.length) p(`/sub_choices/${s.id}/${id}`, []);
    if (applyEffects) effects(opt?.effects, on ? -1 : 1);
  }
  const lineOf = (lid: string) => (obj?.[lid] as string | null) ?? null;
  function setLine(lid: string, oid: string | null) {
    if (!editable) return;
    p(`${basePath}/${lid}`, oid);
  }
  const names = $derived({ origin: String(obj?.origin ?? ''), name: String(obj?.name ?? '') });
  function setNames(origin: string, name: string) {
    if (!editable) return;
    p(basePath, { origin, name });
  }
  const rowPath = (row: { id: string }) => `${basePath}/${at(row.id)}`;
  function setCell(row: { id: string }, col: string, v: unknown) {
    p(`${rowPath(row)}/${col}`, v);
  }
  function addRow() {
    const row: Record<string, unknown> = { id: uid() };
    for (const c of s.columns) row[c.id] = c.type === 'check' ? false : c.type === 'number' ? 0 : '';
    p(`${basePath}/-`, row);
  }
  function removeRow(row: { id: string }) {
    p(rowPath(row), null, 'remove');
  }
  function rollCell(row: Record<string, unknown>, col: { id: string; label: string }) {
    const expr = String(row[col.id] ?? '').trim();
    if (!expr) return;
    const first = s.columns.find((c) => c.type === 'text');
    const who = first ? String(row[first.id] ?? '').trim() : '';
    send({ type: 'roll', expr, label: [who, col.label].filter(Boolean).join(' · ') }).catch(() => {});
  }
  const optionTracks = (oid: string) => doc?.option_tracks[s.id]?.[oid] as TrackState | undefined;
  const optionText = (oid: string) => String(doc?.option_text[s.id]?.[oid] ?? '');
  const subChoices = (oid: string) => (doc?.sub_choices[s.id]?.[oid] as string[] | undefined) ?? [];
  const setTrack = (oid: string, kind: TrackKind, v: number) => p(`/option_tracks/${s.id}/${oid}/${kind}`, v);
  const setText = (oid: string, v: string) => p(`/option_text/${s.id}/${oid}`, v);
  function setChild(parentId: string, childId: string, on: boolean, max: number | null) {
    if (!editable) return;
    const path = `/sub_choices/${s.id}/${parentId}`;
    if (max === 1) {
      p(path, on ? [childId] : []);
      return;
    }
    p(path, childId, on ? 'list_add' : 'list_remove');
  }
  const groupName = $derived(sheet ? `${sheet.entity}.${sheet.id}.${s.id}` : `${idPrefix}${s.id}`);
  const pickHint = $derived(
    s.type === 'multichoose'
      ? s.min != null && s.max != null && s.min === s.max
        ? `pick ${s.min}`
        : s.min != null
          ? `pick ${s.min}+`
          : s.max != null
            ? `up to ${s.max}`
            : ''
      : '',
  );
</script>

<Collapsible id="{idPrefix}sec.{s.id}" title={s.title} subtitle={pickHint} open={!s.collapsed}>
  {#if s.help}<p class="muted small help">{@html renderInline(s.help)}</p>{/if}

  {#if s.type === 'choose'}
    <div class="opts">
      {#each s.options as o (o.id)}
        <OptionRow
          option={o}
          sectionId={s.id}
          selected={value === o.id}
          {editable}
          kind="radio"
          group={groupName}
          basePath={`/option_tracks/${s.id}`}
          presencePath={pres(basePath)}
          tracksOf={optionTracks}
          textOf={optionText}
          childrenOf={subChoices}
          onselect={choose}
          ontrack={setTrack}
          ontext={setText}
          onchild={setChild}
        />
      {/each}
    </div>
  {:else if s.type === 'multichoose' || s.type === 'checklist'}
    <div class="opts">
      {#each s.options as o (o.id)}
        <OptionRow
          option={o}
          sectionId={s.id}
          selected={arr.includes(o.id)}
          editable={editable && (arr.includes(o.id) || s.max == null || arr.length < s.max)}
          kind="checkbox"
          group={groupName}
          basePath={`/option_tracks/${s.id}`}
          presencePath={pres(basePath)}
          tracksOf={optionTracks}
          textOf={optionText}
          childrenOf={subChoices}
          onselect={(id) => toggle(id, s.type === 'multichoose')}
          ontrack={setTrack}
          ontext={setText}
          onchild={setChild}
        />
      {/each}
    </div>
  {:else if s.type === 'lines'}
    <div class="stack">
      {#each s.lines as ln (ln.id)}
        <div class="row lineRow">
          {#if ln.label}<span class="muted small listlbl">{@html renderInline(ln.label)}</span>{/if}
          {#each ln.options as o (o.id)}
            <label class="chip" class:sel={lineOf(ln.id) === o.id} class:ro={!editable}>
              <input
                type="radio"
                name="{groupName}.{ln.id}"
                checked={lineOf(ln.id) === o.id}
                disabled={!editable}
                use:presence={pres(`${basePath}/${ln.id}`)}
                onchange={() => setLine(ln.id, o.id)}
              />
              <span>{@html renderInline(o.label)}</span>
            </label>
          {/each}
          {#if ln.write_in !== null}
            <DebouncedText
              class="linewrite"
              value={optionText(ln.id)}
              placeholder={ln.write_in || '…'}
              readonly={!editable}
              onchange={(v) => setText(ln.id, v)}
            />
          {/if}
          {#if editable && lineOf(ln.id)}
            <button class="ghost small" title="Clear this line" onclick={() => setLine(ln.id, null)}>✕</button>
          {/if}
        </div>
      {/each}
    </div>
  {:else if s.type === 'pips'}
    <Pips
      shape="circle"
      value={Number(value) || 0}
      max={s.max ?? 1}
      onchange={(v) => onchange(v)}
      disabled={!editable}
      path={basePath}
    />
  {:else if s.type === 'text'}
    <DebouncedText
      multiline
      value={String(value ?? '')}
      path={basePath}
      readonly={!editable}
      placeholder={s.placeholder}
    />
  {:else if s.type === 'names'}
    <div class="stack">
      {#each s.lists as l}
        <div class="row">
          <label class="chip" class:sel={names.origin === l.label} class:ro={!editable}>
            <input
              type="radio"
              name="{groupName}.origin"
              checked={names.origin === l.label}
              disabled={!editable}
              use:presence={pres(`${basePath}/origin`)}
              onchange={() => setNames(l.label, names.name)}
            />
            <span class="listlbl">{l.label}</span>
          </label>
          {#each l.names as n}
            <button
              class="small"
              class:primary={names.name === n}
              disabled={!editable}
              onclick={() => {
                setNames(l.label, n);
                p?.('/name', n);
              }}>{n}</button
            >
          {/each}
        </div>
      {/each}
    </div>
  {:else if s.type === 'table'}
    <div style="overflow-x:auto">
      <table class="grid">
        <thead
          ><tr
            >{#each s.columns as c}<th>{c.label}</th>{/each}{#if editable}<th></th>{/if}</tr
          ></thead
        >
        <tbody>
          {#each arr as row (row.id)}
            {@const rp = rowPath(row)}
            <tr>
              {#each s.columns as c}
                <td>
                  {#if c.type === 'check'}
                    <input
                      type="checkbox"
                      checked={!!row[c.id]}
                      disabled={!editable}
                      use:presence={pres(`${rp}/${c.id}`)}
                      onchange={(e) => setCell(row, c.id, (e.target as HTMLInputElement).checked)}
                    />
                  {:else if c.type === 'number'}
                    <input
                      type="number"
                      value={row[c.id] ?? 0}
                      disabled={!editable}
                      use:presence={pres(`${rp}/${c.id}`)}
                      onchange={(e) => setCell(row, c.id, Number((e.target as HTMLInputElement).value))}
                    />
                  {:else if c.type === 'dice'}
                    <span class="row" style="gap:.3em;flex-wrap:nowrap">
                      <DebouncedText
                        class="kbd dice"
                        value={String(row[c.id] ?? '')}
                        path={`${rp}/${c.id}`}
                        readonly={!editable}
                        placeholder="1d6"
                      />
                      <button
                        class="small primary"
                        onclick={() => rollCell(row, c)}
                        disabled={!String(row[c.id] ?? '').trim()}>Roll</button
                      >
                    </span>
                  {:else if c.type === 'select'}
                    <select
                      value={row[c.id] ?? ''}
                      disabled={!editable}
                      use:presence={pres(`${rp}/${c.id}`)}
                      onchange={(e) => setCell(row, c.id, (e.target as HTMLSelectElement).value)}
                    >
                      <option value=""></option>
                      {#each c.options as o}<option value={o}>{o}</option>{/each}
                    </select>
                  {:else}
                    <DebouncedText value={String(row[c.id] ?? '')} path={`${rp}/${c.id}`} readonly={!editable} />
                  {/if}
                </td>
              {/each}
              {#if editable}<td
                  ><button class="ghost small danger" onclick={() => removeRow(row)} title="Remove row">✕</button></td
                >{/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if editable}<button class="small" onclick={addRow} style="margin-top:.4em">+ Row</button>{/if}
  {/if}
</Collapsible>

<style>
  .help {
    margin-bottom: 0.4em;
  }
  .opts {
    display: flex;
    flex-direction: column;
    gap: 0.25em;
  }
  .listlbl {
    min-width: 5em;
  }
  .lineRow {
    gap: 0.15em 0.4em;
  }
  .chip {
    display: inline-flex;
    align-items: baseline;
    gap: 0.3em;
    padding: 0.1em 0.45em;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }
  .chip.sel {
    background: var(--accent-soft);
  }
  .chip.ro {
    cursor: default;
  }
  .chip input {
    margin: 0;
    position: relative;
    top: 0.1em;
  }
  :global(input.linewrite) {
    width: 12em;
  }
  :global(input.dice) {
    width: 6em;
  }
</style>
