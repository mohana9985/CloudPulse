import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development (`npm run dev`) Vite proxies /api to the FastAPI backend,
// so the browser sees a single origin, exactly like Nginx does in Docker.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
