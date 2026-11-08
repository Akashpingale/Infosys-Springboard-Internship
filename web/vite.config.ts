/// <reference types="vitest" />
import path from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Section 11: the API base URL comes from VITE_API_URL; no key or secret is ever read here.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    strictPort: true,
    host: '127.0.0.1',
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    /*
     * The interaction tests drive a real combobox and chip input through userEvent, which is slow
     * in jsdom; with every test file running at once they can pass the 5 s default on a loaded
     * machine. The limit is raised rather than the waiting being hidden, so a test that genuinely
     * hangs still fails.
     */
    testTimeout: 20_000,
    hookTimeout: 20_000,
  },
});
