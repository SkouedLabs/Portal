import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { load as parseYaml } from 'js-yaml'

const require = createRequire(import.meta.url)

// Builds the Font Awesome Free icon index from the installed package metadata,
// so the icon picker works offline (no request to fontawesome.com).
function fontAwesomeIndex() {
  const id = 'virtual:fa-icons'
  return {
    name: 'fa-icons-index',
    resolveId: (source) => (source === id ? '\0' + id : null),
    load(resolved) {
      if (resolved !== '\0' + id) return null
      const root = dirname(require.resolve('@fortawesome/fontawesome-free/package.json'))
      const meta = parseYaml(readFileSync(join(root, 'metadata', 'icons.yml'), 'utf8'))
      // [name, label, styles ("s" solid, "r" regular, "b" brands), search terms]
      const icons = Object.entries(meta)
        .map(([name, m]) => [
          name,
          m.label || name,
          (m.styles || []).map((s) => s[0]).join(''),
          (m.search?.terms || []).join(' ').toLowerCase(),
        ])
        .filter((i) => i[2])
      return `export default ${JSON.stringify(icons)}`
    },
  }
}

export default defineConfig({
  plugins: [vue(), fontAwesomeIndex()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.API_URL || 'http://localhost:8000', changeOrigin: false },
    },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
})
