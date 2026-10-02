<script lang="ts">
  import { app } from '../../lib/state.svelte';
  import { carriedLoad, loadLabel, uid } from '../../lib/util';
  import { at } from '../../lib/pointer';
  import type { CharacterDoc, GearItem, Playbook } from '../../lib/types';
  import type { Patcher } from '../../lib/patch';
  import Collapsible from '../../ui/Collapsible.svelte';
  import DebouncedText from '../../ui/DebouncedText.svelte';
  import Pips from '../../ui/Pips.svelte';
  import Stepper from '../../ui/Stepper.svelte';

  let {
    doc,
    p,
    editable,
    pb,
    characterId,
  }: { doc: CharacterDoc; p: Patcher; editable: boolean; pb: Playbook | undefined; characterId: string } = $props();
  const content = $derived(app.content!);
  const items = $derived(doc.gear.items);
  // One budget: gear plus any load box marked on a possession.
  const load = $derived(carriedLoad(content, doc, pb));
  const label = $derived(loadLabel(content, load));

  function add() {
    const item: GearItem = {
      id: uid(),
      name: '',
      tags: [],
      bulk: 1,
      uses: null,
      statuses: [],
      statuses_marked: 0,
      notes: '',
    };
    p('/gear/items/-', item);
  }
  const itemPath = (item: GearItem) => `/gear/items/${at(item.id)}`;
  function remove(item: GearItem) {
    p(itemPath(item), null, 'remove');
  }
  function setTags(item: GearItem, text: string) {
    p(
      `${itemPath(item)}/tags`,
      text
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    );
  }
  function toggleUses(item: GearItem) {
    p(`${itemPath(item)}/uses`, item.uses ? null : { max: 3, used: 0 });
  }
  /** Ammo: the book's plenty left / low ammo / all out, marked left to right (p94). */
  function toggleAmmo(item: GearItem) {
    const on = item.statuses?.length;
    p(`${itemPath(item)}/statuses`, on ? [] : ['low ammo', 'all out']);
    if (on) p(`${itemPath(item)}/statuses_marked`, 0);
  }
</script>

<Collapsible
  id="gear.{characterId}"
  title="Gear"
  subtitle={content.pack.load ? `load ${load} (${label})` : `load ${load}`}
>
  {#snippet right()}
    {#if editable}<button class="small" onclick={add}>+ Item</button>{/if}
  {/snippet}
  {#if content.pack.gear_tags.length}
    <datalist id="gear-tags"
      >{#each content.pack.gear_tags as t}<option value={t}></option>{/each}</datalist
    >
  {/if}
  <div style="overflow-x:auto">
    <table class="grid">
      <thead
        ><tr
          ><th>Item</th><th>Tags</th><th>Bulk</th><th>Uses</th><th>Ammo</th><th>Notes</th>{#if editable}<th
            ></th>{/if}</tr
        ></thead
      >
      <tbody>
        {#each items as item (item.id)}
          {@const base = itemPath(item)}
          <tr>
            <td><DebouncedText value={item.name} path={`${base}/name`} readonly={!editable} placeholder="Item" /></td>
            <td
              ><DebouncedText
                value={(item.tags ?? []).join(', ')}
                onchange={(v) => setTags(item, v)}
                readonly={!editable}
                placeholder="hand, close"
              /></td
            >
            <td
              ><Stepper
                value={Number(item.bulk) || 0}
                min={0}
                onchange={(v) => p(`${base}/bulk`, v)}
                path={`${base}/bulk`}
                disabled={!editable}
              /></td
            >
            <td>
              {#if item.uses}
                <span class="row" style="gap:.3em">
                  <Pips
                    shape="circle"
                    value={item.uses.used}
                    max={item.uses.max}
                    onchange={(v) => p(`${base}/uses/used`, v)}
                    path={`${base}/uses/used`}
                    disabled={!editable}
                  />
                  {#if editable}
                    <Stepper
                      value={item.uses.max}
                      min={1}
                      max={20}
                      onchange={(v) => p(`${base}/uses/max`, v)}
                      path={`${base}/uses/max`}
                    />
                    <button class="ghost small" onclick={() => toggleUses(item)} title="No uses">✕</button>
                  {/if}
                </span>
              {:else if editable}
                <button class="ghost small" onclick={() => toggleUses(item)}>+ uses</button>
              {/if}
            </td>
            <td>
              {#if item.statuses?.length}
                <span class="row" style="gap:.3em">
                  <Pips
                    shape="circle"
                    labels={item.statuses}
                    value={item.statuses_marked ?? 0}
                    max={item.statuses.length}
                    onchange={(v) => p(`${base}/statuses_marked`, v)}
                    path={`${base}/statuses_marked`}
                    disabled={!editable}
                  />
                  {#if editable}<button class="ghost small" onclick={() => toggleAmmo(item)} title="No ammo track"
                      >✕</button
                    >{/if}
                </span>
              {:else if editable}
                <button class="ghost small" onclick={() => toggleAmmo(item)}>+ ammo</button>
              {/if}
            </td>
            <td><DebouncedText value={item.notes ?? ''} path={`${base}/notes`} readonly={!editable} /></td>
            {#if editable}<td><button class="ghost small danger" onclick={() => remove(item)}>✕</button></td>{/if}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if items.length === 0}<p class="muted small">Nothing carried.</p>{/if}
</Collapsible>
