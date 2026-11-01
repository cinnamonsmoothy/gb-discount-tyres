import { defineConfig } from 'vite';

// Keep localhost on the same lookup backend as the deployed website.
const apiTarget = 'https://gb-discount-tyres-quxl24etta-nw.a.run.app';

export default defineConfig({
  base: './',
  server: {
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
  preview: {
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
});
