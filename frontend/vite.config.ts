import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { execSync } from 'node:child_process'

function runGit(cmd: string): string {
  try {
    return execSync(cmd, { cwd: __dirname, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    return ''
  }
}

function getBuildMeta() {
  const commit =
    process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 7) ||
    runGit('git rev-parse --short HEAD') ||
    'unknown'

  const date =
    (process.env.VERCEL_GIT_COMMIT_TIMESTAMP
      ? new Date(process.env.VERCEL_GIT_COMMIT_TIMESTAMP).toISOString().slice(0, 10)
      : '') ||
    runGit('git show -s --format=%cd --date=format:%Y-%m-%d HEAD') ||
    new Date().toISOString().slice(0, 10)

  return {
    commit,
    date,
    version: `${date}+${commit}`,
  }
}

const buildMeta = getBuildMeta()
const devProxyTarget = process.env.TA_DEV_PROXY_TARGET || 'http://127.0.0.1:22222'

export default defineConfig({
  define: {
    __APP_BUILD_COMMIT__: JSON.stringify(buildMeta.commit),
    __APP_BUILD_DATE__: JSON.stringify(buildMeta.date),
    __APP_BUILD_VERSION__: JSON.stringify(buildMeta.version),
  },
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: devProxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/v1': {
        target: devProxyTarget,
        changeOrigin: true,
      },
      '/healthz': {
        target: devProxyTarget,
        changeOrigin: true,
      },
      '/openapi.json': {
        target: devProxyTarget,
        changeOrigin: true,
      },
      '/docs': {
        target: devProxyTarget,
        changeOrigin: true,
      },
    },
  },
})
