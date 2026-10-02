<script lang="ts">
  import { api } from '../lib/api';
  import { app, toast } from '../lib/state.svelte';
  import { download } from '../lib/util';
  import { requestableMoves, type IndexedMove } from '../lib/moveindex';
  import { search, splitMarks } from '../lib/movesearch';
  import Confirm from '../ui/Confirm.svelte';

  const content = $derived(app.content!);
  let reqUser = $state(app.users.find((u) => u.role !== 'gm')?.name ?? app.users[0]?.name ?? '');
  let reqLabel = $state('');
  let reqStat = $state<string>('');
  // What this player can be asked to roll: the table's moves and their own characters'.
  const theirs = $derived(Object.values(app.characters).filter((c) => c.owner === reqUser));
  const requestable = $derived(requestableMoves(content, theirs));
  // A label that names one of those moves asks for the move itself, so the player rolls it with its outcomes.
  // Anything else stays a plain roll, with the label saying what it is for.
  const linked = $derived(requestable.find((e) => e.move.name.toLowerCase() === reqLabel.trim().toLowerCase()));
  // A rolled move from the pack makes a better hint than a made-up one, which may not exist in this game.
  const labelHint = $derived(requestable[0]?.move.name);

  // Moves to suggest as the GM types. The label stays free text: Tab fills in the marked move (the first,
  // or one walked to with the arrows), and Enter sends what they typed unless they've walked down the list.
  let suggesting = $state(false);
  let cursor = $state(-1);
  // Only name and trigger hits: the label is often a plain description, and a word from deep in some
  // move's rules text ("climbing the wall") is no reason to offer that move.
  const suggestions = $derived(
    suggesting && reqLabel.trim()
      ? search(requestable, reqLabel)
          .filter((h) => h.field === 'name' || h.field === 'trigger')
          .slice(0, 8)
      : [],
  );

  // The list hangs from the input; on a narrow screen that can run it off the right edge, so pull it back in.
  let list: HTMLDivElement | undefined = $state();
  $effect(() => {
    void suggestions;
    if (!list) return;
    list.style.translate = '';
    const over = list.getBoundingClientRect().right - (document.documentElement.clientWidth - 8);
    if (over > 0) list.style.translate = `${-over}px`;
  });

  function typed() {
    suggesting = true;
    cursor = -1;
  }
  function pick(e: IndexedMove) {
    reqLabel = e.move.name;
    suggesting = false;
  }
  function onLabelKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown' && suggestions.length) {
      cursor = Math.min(cursor + 1, suggestions.length - 1);
      e.preventDefault();
    } else if (e.key === 'ArrowUp' && suggestions.length) {
      cursor = Math.max(cursor - 1, -1);
      e.preventDefault();
    } else if (e.key === 'Tab' && !e.shiftKey && suggestions.length) {
      pick(suggestions[Math.max(cursor, 0)].entry);
      e.preventDefault();
    } else if (e.key === 'Escape') {
      suggesting = false;
    } else if (e.key === 'Enter') {
      if (cursor >= 0 && suggestions[cursor]) pick(suggestions[cursor].entry);
      else requestRoll();
      e.preventDefault();
    }
  }
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
    const text = reqLabel;
    if (!text.trim()) return;
    const body = {
      user: reqUser,
      label: linked?.move.name ?? text.trim(),
      stat: reqStat || null,
      move_id: linked?.move.id ?? null,
    };
    // Cleared now, not after the round trip, which would wipe whatever the GM has started typing since.
    reqLabel = '';
    suggesting = false;
    try {
      await api.post('/api/request_roll', body);
    } catch (e) {
      if (!reqLabel) reqLabel = text; // not sent: give it back, unless they have started another
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
    <span class="muted small">to roll for</span>
    <span class="suggest">
      <input
        type="text"
        role="combobox"
        aria-label="What the roll is for"
        aria-expanded={suggestions.length > 0}
        aria-controls="roll-suggestions"
        aria-autocomplete="list"
        aria-activedescendant={cursor >= 0 ? `roll-suggestion-${cursor}` : undefined}
        placeholder={labelHint ? `e.g. ${labelHint}` : 'what for?'}
        title="What the roll is for: a move, or what they're attempting. The player sees this in the chat."
        bind:value={reqLabel}
        oninput={typed}
        onkeydown={onLabelKey}
        onblur={() => (suggesting = false)}
        style="width:10em"
      />
      {#if suggestions.length}
        <div class="popup" bind:this={list}>
          <ul id="roll-suggestions" role="listbox" aria-label="Moves">
            {#each suggestions as h, i}
              <!-- mousedown, not click: picking must happen before the input's blur closes the list -->
              <li
                id="roll-suggestion-{i}"
                role="option"
                aria-selected={i === cursor}
                class:sel={i === cursor}
                onmousedown={(e) => {
                  e.preventDefault();
                  pick(h.entry);
                }}
                onmouseenter={() => (cursor = i)}
              >
                <span class="hname"
                  >{#each splitMarks(h.entry.move.name, h.marks) as part}<span class:mark={part.hit}>{part.text}</span
                    >{/each}</span
                >
                <span class="muted small">{h.entry.source.label}</span>
                <kbd class:off={i !== Math.max(cursor, 0)}>Tab</kbd>
                {#if h.snippet}<span class="snip muted small">{h.snippet}</span>{/if}
              </li>
            {/each}
          </ul>
          <div class="hint muted small"><kbd>Tab</kbd> fills in the move · <kbd>Enter</kbd> sends what you typed</div>
        </div>
      {/if}
    </span>
    {#if linked}
      <span class="tag" title="{reqUser} rolls the move itself, with its outcomes">move</span>
    {/if}
    <select bind:value={reqStat}>
      <option value="">{linked ? "the move's stat" : 'any stat'}</option>
      {#each content.pack.stats as s}<option value={s.id}>+{s.label}</option>{/each}
    </select>
    <button class="small" onclick={requestRoll} disabled={!reqLabel.trim()}>Request</button>
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
  .suggest {
    position: relative;
  }
  .popup {
    position: absolute;
    top: calc(100% + 2px);
    left: 0;
    z-index: 30;
    width: max-content;
    min-width: 100%;
    max-width: min(28em, calc(100vw - 16px));
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    box-shadow: var(--shadow);
  }
  ul {
    margin: 0;
    padding: 0.2em 0;
    list-style: none;
  }
  li {
    display: grid;
    grid-template-columns: 1fr auto auto;
    align-items: baseline;
    gap: 0 0.75em;
    padding: 0.3em 0.7em;
    cursor: pointer;
  }
  li.sel {
    background: var(--accent-soft);
  }
  .hname {
    font-weight: 600;
  }
  .mark {
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  kbd {
    font-family: var(--mono);
    font-size: 0.75em;
    color: var(--fg-muted);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 0 0.35em;
  }
  kbd.off {
    visibility: hidden;
  }
  .hint {
    padding: 0.3em 0.7em;
    border-top: 1px solid var(--border);
  }
  .snip {
    grid-column: 1 / -1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
