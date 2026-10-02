/// <reference types="vitest" />
import { defineConfig } from 'vite';
import type { Plugin } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { writeFileSync } from 'node:fs';
import { inkTextures } from './src/textures/ink';

// The paper theme's ink textures are generated, not committed: written into
// src/textures/ before anything resolves app.css, on every dev server and build.
function inkTexturesPlugin(): Plugin {
  return {
    name: 'ink-textures',
    buildStart() {
      for (const [name, svg] of Object.entries(inkTextures())) {
        writeFileSync(new URL(`./src/textures/${name}`, import.meta.url), svg);
      }
    },
  };
}

// VITE_BASE serves the app under a sub-path (e.g. `/stonetop/` behind a reverse
// proxy that strips the prefix). It lands in import.meta.env.BASE_URL, which
// lib/api.ts and lib/ws.ts prepend to every request they make.
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [inkTexturesPlugin(), svelte()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  // Unit tests for the pure logic — ranking, link parsing, grouping — and for
  // lib/ws.ts against a fake WebSocket. Anything that needs the DOM or a running
  // table is tested against the real app.
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
});
