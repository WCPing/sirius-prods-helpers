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
    host: '0.0.0.0',
    port: 5173,
    // 代理后端 API，解决跨域问题（开发环境）
    proxy: {
      // SSE 流式端点：需要关闭缓冲以支持逐 chunk 推送
      '/api/conversations': {
        target: 'http://127.0.0.1:5174',
        changeOrigin: true,
        timeout: 300000, // 与 Axios 超时保持一致：300s
        // 关键：为 SSE 连接配置 http-proxy，避免响应被缓冲
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              // 确保 SSE 不被缓冲
              proxyRes.headers['cache-control'] = 'no-cache'
              proxyRes.headers['x-accel-buffering'] = 'no'
            }
          })
        }
      },
      '/api': {
        target: 'http://127.0.0.1:5174',
        changeOrigin: true,
        timeout: 300000, // 与 Axios 超时保持一致：300s
        rewrite: (path) => path
      }
    }
  }
})
