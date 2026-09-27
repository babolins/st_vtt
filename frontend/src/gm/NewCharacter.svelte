<script lang="ts">
  import Modal from '../ui/Modal.svelte';
  import { api } from '../lib/api';
  import { app, isGm, toast } from '../lib/state.svelte';
  import { pickFile } from '../lib/util';

  let { onclose }: { onclose: () => void } = $props();
  const content = $derived(app.content!);
  // A starting choice for the form, not a binding to the content pack.
  // svelte-ignore state_referenced_locally
  let playbook = $state(content.playbooks[0]?.id ?? '');
  let name = $state('');
  let owner = $state(app.me!.name);
  let busy = $state(false);

  async function create() {
    busy = true;
    try {
      await api.post('/api/characters', { playbook, name, owner: isGm() ? owner : null });
      onclose();
    } catch (e) { toast(String((e as Error).message), 'error'); } finally { busy = false; }
  }
  async function importFile() {
    try {
      const doc = await pickFile();
      const r = await api.post<{ warnings: string[] }>('/api/characters/import', { character: doc, owner: isGm() ? owner : null });
      for (const w of r.warnings) toast(w, 'error');
      onclose();
    } catch (e) { toast(String((e as Error).message), 'error'); }
  }
</script>

<Modal title="New character" {onclose}>
  <div class="stack">
    <label>Playbook
      <select bind:value={playbook}>
        {#each content.playbooks as p}<option value={p.id}>{p.name}</option>{/each}
      </select>
    </label>
    {#if content.playbooks.find((p) => p.id === playbook)?.blurb}
      <p class="muted small">{content.playbooks.find((p) => p.id === playbook)?.blurb}</p>
    {/if}
    <label>Name <input type="text" bind:value={name} placeholder="(pick later)" /></label>
    {#if isGm()}
      <label>Owner
        <select bind:value={owner}>
          {#each app.users as u}<option value={u.name}>{u.name}</option>{/each}
        </select>
      </label>
    {/if}
    <div class="row" style="justify-content:space-between">
      <button onclick={importFile}>Import JSON…</button>
      <span class="row">
        <button onclick={onclose}>Cancel</button>
        <button class="primary" disabled={!playbook || busy} onclick={create}>Create</button>
      </span>
    </div>
  </div>
</Modal>

<style>
  label { display: flex; flex-direction: column; gap: .2em; }
</style>
