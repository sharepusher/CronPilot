import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  define: {
    'process.env.NODE_ENV': '"production"'
  },
  build: {
    outDir: resolve(__dirname, '../app/static/dist'),
    emptyOutDir: false,
    lib: {
      entry: resolve(__dirname, 'src/mount/cron-status-cell.js'),
      name: 'CronStatusCell',
      fileName: () => 'cron-status-cell.js',
      formats: ['iife']
    },
    rollupOptions: {
      output: {
        entryFileNames: 'cron-status-cell.js',
        chunkFileNames: '[name].js',
        assetFileNames: '[name][extname]'
      }
    }
  }
})
