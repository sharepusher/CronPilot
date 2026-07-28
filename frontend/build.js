/**
 * Vite programmatic multi-build script.
 * Builds each mount entry as a self-contained IIFE bundle.
 * Run with: node build.js  (or via npm run build)
 */
import { build } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

const entries = [
  { varName: 'CronStatusCell', file: 'cron-status-cell' },
  { varName: 'CronFilterBar',  file: 'cron-filter-bar'  },
]

for (const { varName, file } of entries) {
  console.log(`Building ${file}...`)
  await build({
    plugins: [vue()],
    define: { 'process.env.NODE_ENV': '"production"' },
    build: {
      outDir: resolve(__dirname, '../app/static/dist'),
      emptyOutDir: false,
      lib: {
        entry: resolve(__dirname, `src/mount/${file}.js`),
        name: varName,
        fileName: () => `${file}.js`,
        formats: ['iife'],
      },
      rollupOptions: {
        output: {
          entryFileNames: `${file}.js`,
          chunkFileNames: '[name].js',
          assetFileNames: '[name][extname]',
        },
      },
    },
    logLevel: 'warn',
  })
  console.log(`  -> app/static/dist/${file}.js`)
}
console.log('Done.')
