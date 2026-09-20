<script lang="ts">
  /** Who is who to whom.
   *
   *  A view of the ties already on the records — nothing here is stored. Layout is
   *  a small force simulation seeded from each node's id, so the same table draws
   *  the same picture every time rather than shuffling on every visit.
   *
   *  Clicking a node peeks it, which is the whole reason peek was built first: a
   *  graph you have to leave in order to read anything is a picture, not a tool.
   */
  import { app, records } from '../lib/state.svelte';
  import { peek, type Place } from '../lib/router.svelte';
  import { userColor } from '../lib/util';

  interface Node { id: string; name: string; place: Place; kind: 'record' | 'character'; hidden: boolean; x: number; y: number; vx: number; vy: number }
  interface Edge { from: string; to: string; type: string }

  const W = 900;
  const H = 560;

  let hover = $state<string | null>(null);

  /** Stable pseudo-random from an id, so the same graph lands the same way twice. */
  function seeded(id: string): number {
    let h = 2166136261;
    for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
    return ((h >>> 0) % 10000) / 10000;
  }

  const graph = $derived.by(() => {
    const edges: Edge[] = [];
    const wanted = new Set<string>();
    const people = records().filter((r) => r.kind !== 'event');
    for (const row of people) {
      for (const tie of row.data.ties) {
        if (!tie.to) continue;
        edges.push({ from: row.id, to: tie.to, type: tie.type });
        wanted.add(row.id);
        wanted.add(tie.to);
      }
    }
    const nodes: Node[] = [];
    const add = (id: string, name: string, place: Place, kind: Node['kind'], hidden: boolean) => {
      const a = seeded(id) * Math.PI * 2;
      const r = 120 + seeded(id + 'r') * 150;
      nodes.push({ id, name, place, kind, hidden, x: W / 2 + Math.cos(a) * r, y: H / 2 + Math.sin(a) * r, vx: 0, vy: 0 });
    };
    for (const row of people) {
      add(row.id, row.data.name || 'Unnamed', { kind: 'record', id: row.id }, 'record', row.data.visibility === 'gm');
    }
    for (const row of Object.values(app.characters)) {
      if (!wanted.has(row.id)) continue;
      add(row.id, row.data.name || 'Unnamed', { kind: 'character', id: row.id }, 'character', false);
    }
    const index = new Map(nodes.map((n) => [n.id, n]));
    const live = edges.filter((e) => index.has(e.from) && index.has(e.to));

    // Fruchterman–Reingold, briefly: repel everything, pull ties together, cool.
    const k = Math.sqrt((W * H) / Math.max(nodes.length, 1)) * 0.6;
    for (let step = 0; step < 260; step++) {
      const heat = 18 * (1 - step / 260);
      for (const a of nodes) {
        a.vx = 0;
        a.vy = 0;
        for (const b of nodes) {
          if (a === b) continue;
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d = Math.hypot(dx, dy) || 0.01;
          const push = (k * k) / d;
          a.vx += (dx / d) * push;
          a.vy += (dy / d) * push;
        }
      }
      for (const e of live) {
        const a = index.get(e.from)!;
        const b = index.get(e.to)!;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d = Math.hypot(dx, dy) || 0.01;
        const pull = (d * d) / k;
        const fx = (dx / d) * pull;
        const fy = (dy / d) * pull;
        a.vx -= fx; a.vy -= fy;
        b.vx += fx; b.vy += fy;
      }
      for (const n of nodes) {
        const speed = Math.hypot(n.vx, n.vy) || 0.01;
        n.x += (n.vx / speed) * Math.min(speed, heat);
        n.y += (n.vy / speed) * Math.min(speed, heat);
        n.x = Math.max(60, Math.min(W - 60, n.x));
        n.y = Math.max(34, Math.min(H - 24, n.y));
      }
    }
    // Fit to the frame: the simulation's absolute coordinates are arbitrary, and
    // clamping alone leaves everyone shoved against one side.
    if (nodes.length > 1) {
      const xs = nodes.map((n) => n.x);
      const ys = nodes.map((n) => n.y);
      const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      const pad = 70;
      const scale = Math.min((W - pad * 2) / Math.max(x1 - x0, 1), (H - pad * 2) / Math.max(y1 - y0, 1), 1.6);
      const offX = (W - (x1 - x0) * scale) / 2 - x0 * scale;
      const offY = (H - (y1 - y0) * scale) / 2 - y0 * scale;
      for (const n of nodes) {
        n.x = n.x * scale + offX;
        n.y = n.y * scale + offY;
      }
    }
    return { nodes, edges: live, index };
  });

  const near = (id: string) =>
    hover === null || hover === id || graph.edges.some((e) => (e.from === hover && e.to === id) || (e.to === hover && e.from === id));
</script>

<div class="card page">
  <div class="row head">
    <h2>Ties</h2>
    <span class="muted small">{graph.nodes.length} people · {graph.edges.length} ties</span>
  </div>

  {#if !graph.edges.length}
    <p class="muted empty">No ties yet. Open anyone under People and say who they are to someone — “deputy-of”, “sidekick-of”, “sweet-on” — and they will appear here.</p>
  {:else}
    <svg viewBox="0 0 {W} {H}" class="graph" role="img" aria-label="Relationships between the people this campaign remembers">
      {#each graph.edges as e}
        {@const a = graph.index.get(e.from)}
        {@const b = graph.index.get(e.to)}
        {#if a && b}
          <g class="edge" class:dim={!(near(e.from) && near(e.to))}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
            <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} text-anchor="middle">{e.type.replace(/-/g, ' ')}</text>
          </g>
        {/if}
      {/each}
      {#each graph.nodes as n}
        <g class="node" class:dim={!near(n.id)} class:character={n.kind === 'character'}
           onmouseenter={() => (hover = n.id)} onmouseleave={() => (hover = null)}
           onclick={() => peek(n.place)} role="button" tabindex="0"
           onkeydown={(e) => e.key === 'Enter' && peek(n.place)}>
          <circle cx={n.x} cy={n.y} r={n.kind === 'character' ? 9 : 6}
                  style={n.kind === 'character' ? `fill: ${userColor(n.name)}` : ''} />
          <text x={n.x} y={n.y - 13} text-anchor="middle">{n.name}{#if n.hidden}&nbsp;·&nbsp;GM{/if}</text>
        </g>
      {/each}
    </svg>
    <p class="small muted key">Larger marks are player characters. Hover to isolate someone's ties; click to open them.</p>
  {/if}
</div>

<style>
  .page { padding: .75em 1em 1em; }
  .head { gap: .5em; align-items: baseline; margin-bottom: .5em; }
  .head h2 { font-size: 1.3em; }
  .graph { width: 100%; height: auto; display: block; }
  .edge line { stroke: var(--border); stroke-width: 1.5; }
  .edge text { fill: var(--fg-muted); font-size: 11px; }
  .node circle { fill: var(--fg); stroke: var(--bg-elev); stroke-width: 2; cursor: pointer; }
  .node text { fill: var(--fg); font-size: 13px; font-weight: 600; cursor: pointer; }
  .node:hover circle { stroke: var(--accent); }
  .dim { opacity: .25; }
  .empty { padding: 1em 0; }
  .key { margin-top: .5em; }
</style>
