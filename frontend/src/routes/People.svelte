<script lang="ts">
  /** Everyone the campaign remembers, filterable.
   *
   *  The plainest possible first view of the record store, on purpose: a list
   *  proves the data before anything is drawn from it. Facets are the fields the
   *  session notes actually carry — role, home, status — plus free text over
   *  everything, including ties.
   */
  import { api } from '../lib/api';
  import { app, isGm, records, toast } from '../lib/state.svelte';
  import { peek } from '../lib/router.svelte';
  import type { RecordRow } from '../lib/types';

  let query = $state('');
  let facet = $state<{ role: string; home: string; status: string }>({ role: '', home: '', status: '' });
  let newName = $state('');
  let busy = $state(false);

  const all = $derived(records());
  const values = (pick: (r: RecordRow) => string) =>
    [...new Set(all.map(pick).map((v) => v.trim()).filter(Boolean))].sort();

  const roles = $derived(values((r) => r.data.role));
  const homes = $derived(values((r) => r.data.home));
  const statuses = $derived(values((r) => r.data.status));

  const shown = $derived.by(() => {
    const q = query.trim().toLowerCase();
    return all.filter((r) => {
      const d = r.data;
      if (facet.role && d.role !== facet.role) return false;
      if (facet.home && d.home !== facet.home) return false;
      if (facet.status && d.status !== facet.status) return false;
      if (!q) return true;
      const hay = [d.name, d.role, d.home, d.status, d.notes, d.secret ?? '', d.tags.join(' '),
        d.ties.map((t) => `${t.type} ${t.note}`).join(' ')].join(' ').toLowerCase();
      return hay.includes(q);
    });
  });

  const nameOf = (id: string) => app.records[id]?.data.name ?? app.characters[id]?.data.name ?? id;

  async function create() {
    if (!newName.trim() || busy) return;
    busy = true;
    try {
      await api.post('/api/records', { kind: 'npc', name: newName.trim() });
      newName = '';
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally {
      busy = false;
    }
  }
</script>

<div class="card page">
  <div class="row head">
    <h2>People</h2>
    <span class="muted small">{shown.length} of {all.length}</span>
    <span class="grow"></span>
    <input class="new" bind:value={newName} placeholder="Name someone new…" onkeydown={(e) => e.key === 'Enter' && create()} />
    <button class="small primary" onclick={create} disabled={!newName.trim() || busy}>Add</button>
  </div>

  <div class="row filters">
    <input class="q" bind:value={query} placeholder="Search names, roles, notes, ties…" aria-label="Search people" />
    {#each [['role', roles], ['home', homes], ['status', statuses]] as [key, list]}
      {#if (list as string[]).length}
        <select class="small" bind:value={facet[key as 'role' | 'home' | 'status']} aria-label={key as string}>
          <option value="">any {key}</option>
          {#each list as string[] as v}<option value={v}>{v}</option>{/each}
        </select>
      {/if}
    {/each}
  </div>

  {#if !all.length}
    <p class="muted empty">Nobody written down yet. The names from your session notes are a good place to start — anyone at the table can add them.</p>
  {:else}
    <table class="grid people">
      <thead>
        <tr><th>Name</th><th>Role</th><th>Home</th><th>Standing</th><th>Ties</th></tr>
      </thead>
      <tbody>
        {#each shown as row (row.id)}
          <tr>
            <td>
              <button class="linky" onclick={() => peek({ kind: 'record', id: row.id })}>{row.data.name}</button>
              {#if row.data.visibility === 'gm'}<span class="tag gm" title="Hidden from the table">GM</span>{/if}
              {#if row.data.pronouns}<span class="muted small"> {row.data.pronouns}</span>{/if}
            </td>
            <td>{row.data.role}</td>
            <td>{row.data.home}</td>
            <td>{row.data.status}</td>
            <td class="ties">
              {#each row.data.ties as t}
                <span class="tie">{t.type.replace(/-/g, ' ')} <button class="linky" onclick={() => peek(app.characters[t.to] ? { kind: 'character', id: t.to } : { kind: 'record', id: t.to })}>{nameOf(t.to)}</button></span>
              {/each}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
  {#if isGm() && all.some((r) => r.data.visibility === 'gm')}
    <p class="small muted foot">Records marked GM are invisible to players — they are not sent to their browsers at all.</p>
  {/if}
</div>

<style>
  .page { padding: .75em 1em 1em; }
  .head { gap: .5em; align-items: baseline; margin-bottom: .6em; }
  .head h2 { font-size: 1.3em; }
  .filters { gap: .4em; margin-bottom: .6em; }
  .q { flex: 1; min-width: 12em; }
  .new { width: 12em; }
  .people td { vertical-align: top; }
  .linky { background: none; border: 0; padding: 0; color: var(--accent); cursor: pointer; font: inherit; text-align: left; }
  .tie { display: block; font-size: .9em; color: var(--fg-muted); }
  .tag.gm { background: var(--accent-soft); color: var(--accent); }
  .empty { padding: 1em 0; }
  .foot { margin-top: .8em; }
</style>
