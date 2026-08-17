import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devHost = env.VITE_DEV_HOST || '127.0.0.1'
  const devPort = Number(env.VITE_DEV_PORT || '3000')
  const apiHost = env.VITE_API_HOST || '127.0.0.1'
  const apiPort = env.VITE_API_PORT || '8240'
  const proxyTarget = env.VITE_API_PROXY_TARGET || `http://${apiHost}:${apiPort}`
  return {
    plugins: [vue()],
    build: {
      outDir: 'dist',
      emptyOutDir: true,
    },
    server: {
      host: devHost,
      port: devPort,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
