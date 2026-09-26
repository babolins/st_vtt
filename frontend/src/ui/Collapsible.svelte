<script lang="ts">
  import type { Snippet } from 'svelte';
  import { getPref, setPref } from '../lib/prefs';

  let {
    id, title, open = true, level = 3, children, right, subtitle,
  }: { id: string; title: string; open?: boolean; level?: 2 | 3; children: Snippet; right?: Snippet; subtitle?: string } = $props();

  let isOpen = $state(getPref(`collapse.${id}`, open));
  function toggle() {
    isOpen = !isOpen;
    setPref(`collapse.${id}`, isOpen);
  }
</script>

<section class="coll" class:top={level === 2}>
  <div class="head">
    <button class="ghost toggle" onclick={toggle} aria-expanded={isOpen}>
      <span class="chev" class:open={isOpen}>▸</span>
      {#if level === 2}<h2>{title}</h2>{:else}<h3>{title}</h3>{/if}
      {#if subtitle}<span class="muted small sub">{subtitle}</span>{/if}
    </button>
    {#if right}<div class="right">{@render right()}</div>{/if}
  </div>
  {#if isOpen}
    <div class="body">{@render children()}</div>
  {/if}
</section>

<style>
  .coll { border-top: 1px solid var(--border); }
  .coll.top { position: relative; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg-elev); box-shadow: var(--shadow); margin-bottom: .75em; }
  .head { display: flex; align-items: center; gap: .5em; padding: .35em .5em; }
  /* A sheet's own header stays put while the sheet scrolls under it: the name,
     and whatever the sheet puts beside it, are needed at every depth. */
  .top > .head {
    padding: .5em .75em; position: sticky; top: 0; z-index: 3;
    background: var(--bg-elev); border-radius: var(--radius) var(--radius) 0 0;
  }
  .toggle { display: flex; align-items: center; gap: .5em; flex: 1; text-align: left; padding: .1em .2em; color: var(--fg); }
  .toggle h3 { font-size: .95em; text-transform: uppercase; letter-spacing: .04em; color: var(--fg-muted); }
  .toggle h2 { font-size: 1.1em; }
  .chev { display: inline-block; transition: transform .15s; color: var(--fg-muted); }
  .chev.open { transform: rotate(90deg); }
  .sub { font-weight: normal; }
  .right { display: flex; gap: .3em; align-items: center; }
  .body { padding: .25em .75em .75em; }
</style>
