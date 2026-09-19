<script lang="ts">
  import { onMount } from 'svelte';
  import { api, ApiError } from '../lib/api';
  import { app } from '../lib/state.svelte';
  import { currentTheme, nextTheme, THEME_GLYPH } from '../lib/theme';

  let { onlogin }: { onlogin: () => void } = $props();
  let users = $state<{ name: string; role: string; has_password: boolean }[]>([]);
  let selected = $state<string>('');
  let password = $state('');
  let error = $state('');
  let busy = $state(false);
  let elsewhere = $state(false);
  let theme = $state(currentTheme());

  const needsPassword = $derived(users.find((u) => u.name === selected)?.has_password ?? false);

  onMount(async () => {
    users = await api.get('/api/users');
    try { selected = localStorage.getItem('st_vtt.lastUser') || ''; } catch {}
    if (!users.some((u) => u.name === selected)) selected = users[0]?.name ?? '';
  });

  async function submit(e: Event | null, force = false) {
    e?.preventDefault();
    error = '';
    elsewhere = false;
    app.loginNotice = '';
    busy = true;
    try {
      const me = await api.post<{ name: string; role: 'gm' | 'player' }>('/api/login', { name: selected, password: password || null, force });
      app.me = { name: me.name, role: me.role };
      try { localStorage.setItem('st_vtt.lastUser', selected); } catch {}
      onlogin();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) elsewhere = true;
      else error = err instanceof ApiError ? err.message : String(err);
    } finally {
      busy = false;
    }
  }
</script>

<div class="wrap">
  <form class="card box stack" onsubmit={submit}>
    <div class="row">
      <h1 class="grow">Shared Table <span class="muted small tagline">st_vtt</span></h1>
      <button type="button" class="ghost small" onclick={() => (theme = nextTheme())} title="Theme: light, dark, paper">{THEME_GLYPH[theme]}</button>
    </div>
    <p class="muted">Who are you?</p>
    <div class="who">
      {#each users as u}
        <label class="opt" class:sel={selected === u.name}>
          <input type="radio" name="user" value={u.name} bind:group={selected} onchange={() => (elsewhere = false)} />
          <span class="grow">{u.name}</span>
          <span class="tag">{u.role}</span>
          {#if u.has_password}<span class="muted small">🔒</span>{/if}
        </label>
      {/each}
    </div>
    {#if needsPassword}
      <input type="password" placeholder="Password" bind:value={password} autocomplete="current-password" />
    {/if}
    {#if app.loginNotice}<div class="notice">{app.loginNotice}</div>{/if}
    {#if error}<div class="err">{error}</div>{/if}
    {#if elsewhere}
      <div class="notice">
        <span><strong>{selected}</strong> is already signed in on another device.</span>
        <span class="row"><button type="button" class="small" onclick={() => submit(null, true)} disabled={busy}>Sign in here anyway</button>
        <span class="muted small">(signs the other device out)</span></span>
      </div>
    {/if}
    <button class="primary" disabled={!selected || busy}>Enter</button>
  </form>
</div>

<style>
  .wrap { display: grid; place-items: center; min-height: 100%; padding: 1em; }
  .box { width: min(26em, 100%); padding: 1.5em; }
  .who { display: flex; flex-direction: column; gap: .25em; }
  .opt { display: flex; gap: .5em; align-items: center; padding: .4em .6em; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; color: var(--fg); font-size: 1em; }
  .opt.sel { border-color: var(--accent); background: var(--accent-soft); }
  .opt input { margin: 0; }
  .tagline { font-weight: normal; font-family: var(--mono); }
  .err { color: var(--bad); }
  .notice { background: var(--accent-soft); border-radius: 6px; padding: .5em .7em; display: flex; flex-wrap: wrap; gap: .4em; align-items: center; }
</style>
