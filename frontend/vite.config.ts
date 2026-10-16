// Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    proxy: {
      '^/api/': {
        target: process.env.TIANSHU_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})
