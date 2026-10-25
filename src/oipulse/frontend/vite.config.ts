/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// CUTOVER DONE: the React app is the root UI. FastAPI serves ./dist at "/"
// (and keeps a /new alias); the legacy vanilla UI lives at /legacy.
// In dev, Vite proxies /api and /ws to the FastAPI backend on :8000.
export default defineConfig({
  base: '/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      // SSE endpoint — disable buffering so EventSource frames stream through.
      '/api/stream': { target: 'http://localhost:8000', changeOrigin: true, ws: false },
      // WebSocket live stream.
      '/ws': { target: 'ws://localhost:8000', ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Split heavy libs into their own chunks so the initial tab payload
        // stays small. Charts/grid load only when their tab mounts (lazy()),
        // but vendor splitting keeps the shared shell chunk lean too.
        manualChunks: {
          antd: ['antd', '@ant-design/icons'],
          aggrid: ['ag-grid-community', 'ag-grid-react'],
          echarts: ['echarts'],
          lwc: ['lightweight-charts'],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
