import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// VITE_BASE serves the app under a sub-path (e.g. `/stonetop/` behind a reverse
// proxy that strips the prefix). It lands in import.meta.env.BASE_URL, which
// lib/api.ts and lib/ws.ts prepend to every request they make.
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
});
