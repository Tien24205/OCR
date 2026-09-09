import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Proxy /api sang backend FastAPI khi chay dev.
// Nho vay frontend goi duong dan tuong doi "/api/..." => khong dinh CORS,
// va cung khong can nhung URL backend vao ma nguon.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
