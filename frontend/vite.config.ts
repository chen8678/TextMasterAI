import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3009,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 确保在 Docker 环境中正常构建
    target: 'es2015',
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    minify: 'terser',
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('echarts')) return 'echarts'
            if (id.includes('element-plus') || id.includes('@element-plus/icons-vue')) return 'element'
            if (id.includes('marked')) return 'markdown'
            if (id.includes('vue-router')) return 'router'
            if (id.includes('pinia')) return 'pinia'
            if (id.includes('vue')) return 'vue'
            return 'vendor'
          }
        }
      }
    }
  },
  define: {
    // 确保 crypto 模块在构建时正确工作
    global: 'globalThis',
  }
})