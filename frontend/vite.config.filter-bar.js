import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [vue()],
  define: {
    'process.env.NODE_ENV': '"production"'
  },
  build: {
    outDir: resolve(__dirname, '../app/static/dist'),
    emptyOutDir: false,
    lib: {
      entry: resolve(__dirname, 'src/mount/cron-filter-bar.js'),
      name: 'CronFilterBar',
      fileName: () => 'cron-filter-bar.js',
      formats: ['iife']
    },
    rollupOptions: {
      output: {
        entryFileNames: 'cron-filter-bar.js',
        chunkFileNames: '[name].js',
        assetFileNames: '[name][extname]'
      }
    }
  }
})
