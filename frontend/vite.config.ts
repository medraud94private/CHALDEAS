import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'robots.txt'],
      manifest: {
        name: 'CHALDEAS - World History Explorer',
        short_name: 'CHALDEAS',
        description: 'Explore world history through an interactive 3D globe. Discover events, people, and places across time.',
        theme_color: '#050810',
        background_color: '#050810',
        display: 'standalone',
        orientation: 'any',
        start_url: '/',
        icons: [
          {
            src: '/icons/icon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any',
          },
          {
            src: '/icons/icon.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Cache strategies
        runtimeCaching: [
          {
            // API calls - network first, fallback to cache
            urlPattern: /^https?:\/\/.*\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24, // 1 day
              },
              networkTimeoutSeconds: 10,
            },
          },
          {
            // Static assets - cache first
            urlPattern: /\.(?:js|css|woff2?|png|jpg|jpeg|svg|gif|ico)$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'static-assets',
              expiration: {
                maxEntries: 200,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
              },
            },
          },
        ],
        // Pre-cache essential files
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5200,  // Fixed port for Chaldeas
    host: true,
    strictPort: true,  // Fail if port is in use
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Three.js and globe rendering - largest chunk
          'three-globe': ['three', 'react-globe.gl'],
          // React core
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          // Data fetching and state
          'data-layer': ['@tanstack/react-query', 'zustand', 'axios'],
          // i18n
          'i18n': ['i18next', 'react-i18next', 'i18next-browser-languagedetector'],
        },
      },
    },
    chunkSizeWarningLimit: 600, // Raise limit slightly for three-globe chunk
  },
})
