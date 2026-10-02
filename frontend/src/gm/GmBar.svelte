<script lang="ts">
  import { api } from '../lib/api';
  import { app, toast } from '../lib/state.svelte';
  import { download } from '../lib/util';
  import Confirm from '../ui/Confirm.svelte';

  const content = $derived(app.content!);
  let reqUser = $state(app.users.find((u) => u.role !== 'gm')?.name ?? app.users[0]?.name ?? '');
  let reqLabel = $state('');
  let reqStat = $state<string>('');
  let confirmClear = $state(false);
  // A starting choice for the form, not a binding to the content pack.
  // svelte-ignore state_referenced_locally
  let newTemplate = $state(content.shared_sheets[0]?.id ?? '');
  let newName = $state('');

  async function createShared() {
    try {
      await api.post('/api/shared', { template: newTemplate, name: newName || null });
      newName = '';
    } catch (e) {
      toast((e as Error).message, 'error');
    }
  }

  async function requestRoll() {
    try {
      await api.post('/api/request_roll', { user: reqUser, label: reqLabel || 'a roll', stat: reqStat || null });
      reqLabel = '';
    } catch (e) {
      toast((e as Error).message, 'error');
    }
  }
  async function exportCampaign() {
    try {
      download('campaign.json', await api.get('/api/export/campaign'));
    } catch (e) {
      toast((e as Error).message, 'error');
    }
  }
  async function clearChat() {
    try {
      await api.del('/api/messages');
    } catch (e) {
      toast((e as Error).message, 'error');
    }
  }
</script>

<div class="gmbar row">
  <span class="group row">
    <span class="muted small">Ask</span>
    <select bind:value={reqUser}
      >{#each app.users as u}<option value={u.name}>{u.name}</option>{/each}</select
    >
    <span class="muted small">to roll</span>
    <input type="text" placeholder="what to roll" bind:value={reqLabel} style="width:10em" />
    <select bind:value={reqStat}>
      <option value="">any stat</option>
      {#each content.pack.stats as s}<option value={s.id}>+{s.label}</option>{/each}
    </select>
    <button class="small" onclick={requestRoll}>Request</button>
  </span>
  <span class="group row">
    <span class="muted small">New shared sheet</span>
    <select bind:value={newTemplate}>
      {#each content.shared_sheets as t}<option value={t.id}>{t.name}{t.visibility === 'gm' ? ' (GM only)' : ''}</option
        >{/each}
    </select>
    <input type="text" placeholder="name (optional)" bind:value={newName} style="width:10em" />
    <button class="small" onclick={createShared} disabled={!newTemplate}>Create</button>
  </span>
  <span class="grow"></span>
  <span class="group row">
    <button class="small" onclick={exportCampaign}>Export campaign</button>
    <button class="small danger" onclick={() => (confirmClear = true)}>Clear chat</button>
  </span>
</div>
{#if confirmClear}
  <Confirm
    title="Clear the chat log?"
    text="This deletes all messages and rolls for everyone."
    onyes={clearChat}
    onclose={() => (confirmClear = false)}
  />
{/if}

<style>
  .gmbar {
    padding: 0.4em 0.75em;
    border-top: 1px solid var(--border);
    background: var(--bg-sunken);
  }
  .group {
    gap: 0.3em;
  }
</style>
