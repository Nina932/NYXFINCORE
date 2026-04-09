import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  root: resolve(__dirname),
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:9200',
        changeOrigin: true,
      },
      '/assets': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      }
    },
  },
  build: {
    outDir: resolve(__dirname, '../dist_marketing'),
    emptyOutDir: true,
  }
})
