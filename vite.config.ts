import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import mkcert from 'vite-plugin-mkcert'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [
      react(),
      mkcert(),
      VitePWA({
        registerType: 'autoUpdate',
        injectRegister: 'auto',
        includeAssets: ['icon-192.png', 'icon-512.png'],
        devOptions: {
          enabled: true
        },
        manifestFilename: 'manifest.webmanifest',
        manifest: {
          name: 'AgroDron - Sistema de Riego Autónomo',
          short_name: 'AgroDron',
          description: 'Sistema de control para dron autónomo de riego de cultivos agrícolas',
          start_url: '/',
          display: 'standalone',
          background_color: '#0d0d14',
          theme_color: '#0d0d14',
          orientation: 'portrait-primary',
          icons: [
            {
              src: '/icon-192.png',
              sizes: '192x192',
              type: 'image/png',
              purpose: 'any maskable'
            },
            {
              src: '/icon-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'any maskable'
            }
          ],
          categories: ['agriculture', 'productivity', 'utilities'],
          lang: 'es',
          dir: 'ltr'
        }
      })
    ],
    server: {
      port: Number(env.VITE_PORT) || 3000,
      host: true,
    },
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') }
    }
  }
})
