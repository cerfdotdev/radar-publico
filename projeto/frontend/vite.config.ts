import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Porta do servidor de desenvolvimento, diferente da 8080 do container de produção.
const DEV_PORT = 5173
// Backend local para o proxy de desenvolvimento; sobrescreva com API_PROXY_TARGET.
const DEFAULT_API_TARGET = 'http://localhost:5000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: DEV_PORT,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET ?? DEFAULT_API_TARGET,
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
  },
})
