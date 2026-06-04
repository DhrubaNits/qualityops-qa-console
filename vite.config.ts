import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/orchestrator-api': {
        target: 'https://staging.uipath.com/hackathon26_182/DefaultTenant/orchestrator_',
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/orchestrator-api/, ''),
      },
    },
  },
})