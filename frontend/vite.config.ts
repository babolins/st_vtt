/// <reference types="vitest" />
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  // Unit tests for the pure logic — ranking, link parsing, grouping. Anything
  // that needs the DOM or a running table is tested against the real app.
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
});
