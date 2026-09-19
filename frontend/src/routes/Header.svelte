<script lang="ts">
  import { api } from '../lib/api';
  import { app, isGm } from '../lib/state.svelte';
  import { currentTheme, toggleTheme } from '../lib/theme';
  import { disconnect } from '../lib/ws';
  import GmBar from '../gm/GmBar.svelte';

  let { onnew, onfind }: { onnew: () => void; onfind: () => void } = $props();
  let theme = $state(currentTheme());
  let gmOpen = $state(false);

  async function logout() {
    await api.post('/api/logout');
    disconnect();
    app.me = null;
  }
</script>

<header>
  <div class="row bar">
    <h1 class="title">{app.campaignName}</h1>
    <span class="muted small">{app.content?.pack.name}</span>
    <span class="grow"></span>
    <span class="presence" title="online">
      {#each app.users as u}
        <span class="who" class:on={app.online.includes(u.name)} class:me={u.name === app.me?.name} title="{u.name} ({u.role}){app.online.includes(u.name) ? ', online' : ''}">
          <span class="dot"></span>{u.name}
        </span>
      {/each}
    </span>
    {#if !app.connected}<span class="pill bad">reconnecting…</span>{/if}
    <button class="small" onclick={onfind} title="Find a move (⌘K)">Moves</button>
    <button class="small" onclick={onnew}>+ Character</button>
    {#if isGm()}
      <button class="small" class:primary={gmOpen} onclick={() => (gmOpen = !gmOpen)}>GM tools</button>
    {/if}
    <button class="ghost small" onclick={() => (theme = toggleTheme())} title="Toggle light/dark">{theme === 'dark' ? '☀' : '☾'}</button>
    <button class="ghost small" onclick={logout} title="Log out">Log out</button>
  </div>
  {#if gmOpen && isGm()}
    <GmBar />
  {/if}
</header>

<style>
  header { grid-column: 1 / -1; grid-row: 1; border-bottom: 1px solid var(--border); background: var(--bg-elev); }
  .bar { padding: .4em .75em; }
  .title { font-size: 1.1em; }
  .presence { display: inline-flex; gap: .5em; flex-wrap: wrap; }
  .who { display: inline-flex; align-items: center; gap: .3em; font-size: .85em; color: var(--fg-muted); }
  .who.on { color: var(--fg); }
  .who.me { font-weight: 600; }
  .dot { width: .55em; height: .55em; border-radius: 50%; background: var(--border); }
  .on .dot { background: var(--ok); }
  .pill.bad { color: var(--bad); border-color: var(--bad); }
  @media (max-width: 700px) { .presence { display: none; } }
</style>
