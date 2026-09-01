import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies the backend so the app can use same-origin URLs and
// never has to know which port the simulator is on.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': { target, changeOrigin: true, ws: true },
      },
    },
  }
})
