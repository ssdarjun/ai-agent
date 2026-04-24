import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      // Vite's inotify-based watcher doesn't work on Windows Docker bind mounts.
      // Polling ensures HMR detects file changes from the Windows host.
      usePolling: true,
      interval: 1000,
    },
  },
})
