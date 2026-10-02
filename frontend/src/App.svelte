<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from './lib/api';
  import { app } from './lib/state.svelte';
  import { connect } from './lib/ws';
  import Login from './routes/Login.svelte';
  import Table from './routes/Table.svelte';
  import type { ContentPack, User } from './lib/types';

  onMount(async () => {
    try {
      app.me = await api.get<User | null>('/api/me');
      if (app.me) {
        app.content = await api.get<ContentPack>('/api/content');
        connect();
      }
    } catch {
      app.me = null;
    } finally {
      app.loading = false;
    }
  });

  async function onLogin() {
    app.content = await api.get<ContentPack>('/api/content');
    connect();
  }
</script>

{#if app.loading}
  <div class="center muted">Loading…</div>
{:else if !app.me}
  <Login onlogin={onLogin} />
{:else if !app.content}
  <div class="center muted">Loading content…</div>
{:else}
  <Table />
{/if}

{#if app.toast}
  <div class="toast {app.toast.kind}">{app.toast.text}</div>
{/if}

<style>
  .center {
    display: grid;
    place-items: center;
    height: 100%;
  }
  .toast {
    position: fixed;
    bottom: 1em;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.5em 1em;
    box-shadow: var(--shadow);
    z-index: 100;
    max-width: 90vw;
  }
  .toast.error {
    border-color: var(--bad);
    color: var(--bad);
  }
</style>
