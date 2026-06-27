import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
    // 明確指定副檔名解析順序：.ts / .tsx 優先於 .js，
    // 避免同名的 .js 舊檔遮蔽 .ts 新檔（Vite 預設 .js > .ts）
    extensions: ['.mts', '.ts', '.tsx', '.mjs', '.js', '.jsx', '.json', '.vue'],
  },
  build: {
    // 輸出到專案根目錄的 frontend-dist/，供 nginx volume 掛載
    outDir:     '../frontend-dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-vue':       ['vue', 'vue-router', 'pinia'],
          'vendor-bootstrap': ['bootstrap'],
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      // Dev 模式：API 請求代理至 Flask
      // 使用 trailing slash 避免攔截 /pos /kitchen /quick-io 等 SPA 路由
      '/auth/':           { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/user/':           { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/log/':            { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/product/':        { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/warehouse/':      { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/inventory/':      { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/inbound/':        { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/outbound/':       { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/analytics/':      { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/pos/':            { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/delivery/':       { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/menu/':           { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/settings/':       { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/store/':          { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/quick-io/':       { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/invoice/':        { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/docs/':           { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/customer-order/': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/apidocs/':        { target: 'http://127.0.0.1:5000', changeOrigin: true },
    },
  },
})
