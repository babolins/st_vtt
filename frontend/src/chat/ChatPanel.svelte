<script lang="ts">
  import { tick } from 'svelte';
  import { app, isGm } from '../lib/state.svelte';
  import { send, sendEphemeral } from '../lib/ws';
  import { timeShort } from '../lib/util';
  import { openRoll } from '../lib/dialogs.svelte';
  import { myCharacters } from '../lib/state.svelte';
  import RollCard from './RollCard.svelte';
  import MoveChatCard from './MoveChatCard.svelte';
  import DiceBar from './DiceBar.svelte';
  import Markdown from '../ui/Markdown.svelte';
  import type { RequestMessage } from '../lib/types';

  let { onclose }: { onclose: () => void } = $props();
  let text = $state('');
  let log: HTMLDivElement;
  let atBottom = true;
  let lastTyping = 0;
  let now = $state(Date.now());
  const typers = $derived(Object.entries(app.typing).filter(([u, t]) => t > now && u !== app.me?.name).map(([u]) => u));
  $effect(() => {
    const iv = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(iv);
  });
  function onInput() {
    if (!text.trim()) { setTyping(false); return; }
    const t = Date.now();
    if (t - lastTyping > 2000) { lastTyping = t; sendEphemeral({ type: 'typing', active: true }); }
  }
  function setTyping(active: boolean) {
    lastTyping = active ? Date.now() : 0;
    sendEphemeral({ type: 'typing', active });
  }

  $effect(() => {
    app.messages.length; // track
    tick().then(() => { if (atBottom && log) log.scrollTop = log.scrollHeight; });
  });

  function onscroll() {
    atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  }

  async function submit(e: Event) {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    text = '';
    setTyping(false);
    await send({ type: 'chat', text: t }).catch(() => {
      if (!text) text = t; // not sent: give it back, unless they have started another
    });
  }

  function answerRequest(m: RequestMessage) {
    const mine = myCharacters();
    openRoll({ characterId: mine[0]?.id ?? null, move: null, stat: m.payload.stat ?? null, label: m.payload.label });
  }
</script>

<div class="panel">
  <div class="row head">
    <strong class="grow">Table chat</strong>
    <span class="muted small kbd">/roll 2d6+1 · /w name · /gmroll</span>
    <button class="ghost small closer" onclick={onclose}>✕</button>
  </div>
  <div class="log" bind:this={log} onscroll={onscroll}>
    {#each app.messages as m (m.id)}
      <div class="msg {m.kind}">
        {#if m.kind === 'system'}
          <span class="muted small">{m.payload.text}</span>
        {:else if m.kind === 'roll'}
          <RollCard message={m} />
        {:else if m.kind === 'move'}
          <MoveChatCard message={m} />
        {:else if m.kind === 'request'}
          <div class="req">
            <span><strong>{m.author}</strong> asks <strong>{m.payload.to}</strong> to roll <em>{m.payload.label}</em>{#if m.payload.stat} (+{m.payload.stat.toUpperCase()}){/if}</span>
            {#if m.payload.to === app.me?.name}
              <button class="small primary" onclick={() => answerRequest(m)}>Roll</button>
            {/if}
          </div>
        {:else}
          <div class="row meta">
            <strong>{m.author}</strong>
            {#if m.kind === 'whisper'}<span class="tag">to {m.payload.to.join(', ')}</span>{/if}
            <span class="muted small">{timeShort(m.ts)}</span>
          </div>
          <Markdown text={m.payload.text} />
        {/if}
      </div>
    {/each}
    {#if app.messages.length === 0}<p class="muted small">Nothing yet. Say hello.</p>{/if}
  </div>
  <div class="typing muted small" aria-live="polite">
    {#if typers.length === 1}{typers[0]} is typing…{:else if typers.length > 1}{typers.slice(0, -1).join(', ')} and {typers[typers.length - 1]} are typing…{/if}
  </div>
  <form class="input" onsubmit={submit}>
    <input type="text" placeholder="Say something, or /roll 2d6" bind:value={text} oninput={onInput} onblur={() => setTyping(false)} />
    <button class="primary">Send</button>
  </form>
  <DiceBar />
</div>

<style>
  .panel { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  .head { padding: .5em .75em; border-bottom: 1px solid var(--border); }
  .closer { display: none; }
  .log { flex: 1; overflow-y: auto; padding: .5em .75em; display: flex; flex-direction: column; gap: .5em; }
  .msg { border-radius: var(--radius-sm); }
  .msg.whisper { background: var(--accent-soft); padding: .3em .5em; }
  .msg.chat .meta, .msg.whisper .meta { gap: .4em; }
  .req { display: flex; gap: .5em; align-items: center; justify-content: space-between; background: var(--bg-sunken); padding: .4em .6em; border-radius: var(--radius-sm); }
  .typing { height: 1.3em; padding: 0 .75em; border-top: 1px solid var(--border); }
  .input { display: flex; gap: .4em; padding: .5em .75em; }
  .input input { flex: 1; }
  @media (max-width: 900px) { .closer { display: inline; } }
</style>
