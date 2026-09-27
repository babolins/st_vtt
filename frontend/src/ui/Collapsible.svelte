<script lang="ts">
  import type { Snippet } from 'svelte';
  import { getPref, setPref } from '../lib/prefs';

  let {
    id, title, open = true, level = 3, children, right, subtitle,
  }: { id: string; title: string; open?: boolean; level?: 2 | 3; children: Snippet; right?: Snippet; subtitle?: string } = $props();

  // Follows the id (it can change, e.g. with a character's name); a toggle
  // overrides it until then, and is saved under that id.
  let isOpen = $derived(getPref(`collapse.${id}`, open));
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
  .coll.top { position: relative; border: 1px solid var(--sheet-border); border-radius: var(--radius); background: var(--bg-elev); box-shadow: var(--shadow); margin-bottom: .75em; }
  .head { display: flex; align-items: center; gap: .5em; padding: .35em .5em; }
  /* A sheet's own header stays put while the sheet scrolls under it: the name,
     and whatever the sheet puts beside it, are needed at every depth. */
  .top > .head {
    padding: .5em .75em calc(.5em + var(--heading-rule-height) / 2); position: sticky; top: 0; z-index: 3;
    border-radius: var(--radius) var(--radius) 0 0;
    /* The colour carries as much as any rule image: content scrolls under this
       header, and an image alone would let it show straight through. */
    background: var(--bg-elev) var(--heading-rule) left bottom / auto var(--heading-rule-height) repeat-x;
  }
  .toggle { display: flex; align-items: center; gap: .5em; flex: 1; text-align: left; padding: .1em .2em; color: var(--fg); }
  .toggle h3 { font-size: var(--section-size); text-transform: var(--section-case); letter-spacing: var(--section-tracking); color: var(--section-color); }
  .toggle h2 { font-size: var(--sheet-title-size); }
  .chev { display: inline-block; transition: transform .15s; color: var(--fg-muted); }
  .chev.open { transform: rotate(90deg); }
  .sub { font-weight: normal; }
  .right { display: flex; gap: .3em; align-items: center; }
  .body { padding: .25em .75em .75em; }
</style>
