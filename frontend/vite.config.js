import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'

// Em desenvolvimento, /api é encaminhado para o FastAPI (rodando em localhost:8000),
// então o navegador fala só com o Vite e não esbarra em CORS.
export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.js'],
    server: { deps: { inline: ['vuetify'] } },
  },
})
