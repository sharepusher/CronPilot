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
      entry: resolve(__dirname, 'src/mount/cron-form-validator.js'),
      name: 'CronFormValidator',
      fileName: () => 'cron-form-validator.js',
      formats: ['iife']
    },
    rollupOptions: {
      output: {
        entryFileNames: 'cron-form-validator.js',
        chunkFileNames: '[name].js',
        assetFileNames: function(info) {
          if (info.name && info.name.endsWith('.css')) return 'cron-form-validator.css'
          return '[name][extname]'
        }
      }
    }
  }
})
