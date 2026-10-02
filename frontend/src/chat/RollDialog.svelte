<script lang="ts">
  import Modal from '../ui/Modal.svelte';
  import Stepper from '../ui/Stepper.svelte';
  import { app, isGm, myCharacters } from '../lib/state.svelte';
  import { send } from '../lib/ws';
  import { fmtMod } from '../lib/util';
  import type { RollRequest } from '../lib/dialogs.svelte';

  let { req, onclose }: { req: RollRequest; onclose: () => void } = $props();

  const MIN_BONUS = -10;
  const MAX_BONUS = 10;

  const content = $derived(app.content!);
  // svelte-ignore state_referenced_locally
  const sharedId = req.sharedId ?? null;
  const sheet = $derived(sharedId ? app.shared[sharedId] : null);
  const sheetDef = $derived(sheet ? content.shared_sheets.find((t) => t.id === sheet.data.template) : undefined);

  const candidates = $derived(isGm() ? Object.values(app.characters) : myCharacters());
  // svelte-ignore state_referenced_locally
  let characterId = $state(sharedId ? null : (req.characterId ?? null));
  const doc = $derived(sharedId ? sheet?.data : characterId ? app.characters[characterId]?.data : undefined);

  /** The stats this roll can use: a shared sheet's own, or the pack's character stats. */
  const statList = $derived(
    sheetDef
      ? sheetDef.stats.map((s) => ({ id: s.id, label: s.label }))
      : content.pack.stats.map((s) => ({ id: s.id, label: s.label })),
  );
  const statLabel = (id: string) => statList.find((s) => s.id === id)?.label ?? id;

  // svelte-ignore state_referenced_locally
  const spec = req.move?.roll ?? null;
  const statChoices = $derived.by((): string[] => {
    if (req.stat !== undefined && req.stat !== null) return [req.stat];
    if (!spec) return req.stat === null ? [] : statList.map((s) => s.id);
    if (spec.stat === null) return [];
    if (spec.stat === 'choose') return statList.map((s) => s.id);
    return Array.isArray(spec.stat) ? spec.stat : [spec.stat];
  });
  let stat = $state<string | null>(null);
  $effect(() => {
    if (stat === null || !statChoices.includes(stat)) stat = statChoices[0] ?? null;
  });

  const modifiers = $derived(spec?.modifiers ?? []);
  let picks = $state<Record<string, number>>({});
  $effect(() => {
    for (const m of modifiers) if (!(m.id in picks)) picks[m.id] = m.default;
  });
  const modTotal = $derived(modifiers.reduce((sum, m) => sum + (picks[m.id] ?? m.default), 0));

  let adv = $state(false);
  let disadv = $state(false);
  // svelte-ignore state_referenced_locally
  let bonus = $state(req.bonus ?? 0);
  let gmOnly = $state(false);

  // Debilities only apply to characters, never to a shared sheet.
  const autoDis = $derived(
    !sharedId && doc && stat
      ? content.pack.debilities.filter((d) => doc.debilities[d.id] && d.affects.includes(stat!)).map((d) => d.label)
      : [],
  );
  const statMod = $derived(doc && stat ? (doc.stats[stat] ?? 0) : 0);
  const label = $derived(req.label ?? req.move?.name ?? 'Roll');
  const total = $derived(statMod + bonus + modTotal + (spec?.bonus ?? 0));

  async function go() {
    await send({
      type: 'roll',
      character_id: sharedId ? null : characterId,
      shared_id: sharedId,
      move_id: req.move?.id ?? null,
      stat,
      advantage: adv,
      disadvantage: disadv,
      bonus,
      modifiers: modifiers.length ? picks : null,
      label,
      gm_only: gmOnly,
      request_id: req.requestId ?? null,
    }).then(onclose, () => {}); // on failure (toasted), stay open to try again
  }
</script>

<Modal title={label} {onclose}>
  <div class="stack">
    {#if req.move?.trigger}<p class="muted"><em>{req.move.trigger}</em></p>{/if}

    {#if sharedId}
      <div class="muted small">Rolling for <strong>{sheet?.data.name ?? 'a shared sheet'}</strong></div>
    {:else if candidates.length > 1}
      <label class="field"
        >Character
        <select bind:value={characterId}>
          {#each candidates as c}<option value={c.id}>{c.data.name || '(unnamed)'}</option>{/each}
        </select>
      </label>
    {/if}

    {#if statChoices.length > 1}
      <div class="row">
        <span class="muted small lbl">Stat</span>
        {#each statChoices as s}
          <button class="small" class:primary={stat === s} onclick={() => (stat = s)}
            >{statLabel(s)} {fmtMod(doc?.stats[s] ?? 0)}</button
          >
        {/each}
      </div>
    {:else if statChoices.length === 1}
      <div class="muted">Rolling {content.pack.roll.base} {fmtMod(statMod)} {statLabel(stat!)}</div>
    {:else}
      <div class="muted">Rolling {content.pack.roll.base} + nothing</div>
    {/if}

    {#each modifiers as m (m.id)}
      <label class="field">
        {m.label}
        <select
          value={picks[m.id] ?? m.default}
          onchange={(e) => (picks[m.id] = Number((e.target as HTMLSelectElement).value))}
        >
          {#each m.options as o}<option value={o.value}>{o.label} ({fmtMod(o.value)})</option>{/each}
        </select>
        {#if m.help}<span class="muted small">{m.help}</span>{/if}
      </label>
    {/each}

    {#if autoDis.length}
      <div class="warn">Disadvantage from {autoDis.join(', ')}</div>
    {/if}

    <div class="row opts">
      <label><input type="checkbox" bind:checked={adv} /> advantage</label>
      <label><input type="checkbox" bind:checked={disadv} /> disadvantage</label>
      <span class="row"
        ><span class="muted small">bonus</span><Stepper
          value={bonus}
          min={MIN_BONUS}
          max={MAX_BONUS}
          onchange={(v) => (bonus = v)}
        /></span
      >
      <label><input type="checkbox" bind:checked={gmOnly} /> GM only</label>
    </div>

    <div class="row total muted small">
      {content.pack.roll.base}{#if adv !== disadv}
        ({adv ? 'advantage' : 'disadvantage'}){/if}
      {fmtMod(total)} total modifier
    </div>

    <div class="row" style="justify-content:flex-end">
      {#if req.move}
        <button
          class="ghost"
          onclick={() => {
            send({ type: 'share_move', character_id: sharedId ? null : characterId, move_id: req.move!.id }).catch(
              () => {},
            );
          }}>Share text</button
        >
      {/if}
      <span class="grow"></span>
      <button onclick={onclose}>Cancel</button>
      <button class="primary" onclick={go}>Roll</button>
    </div>
  </div>
</Modal>

<style>
  .warn {
    color: var(--warn);
  }
  label {
    display: inline-flex;
    gap: 0.3em;
    align-items: center;
    color: var(--fg);
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.2em;
    align-items: stretch;
  }
  .lbl {
    min-width: 2.5em;
    color: var(--label-color);
  }
  .opts {
    gap: 0.75em;
  }
  .total {
    border-top: 1px dashed var(--border);
    padding-top: 0.4em;
  }
</style>
