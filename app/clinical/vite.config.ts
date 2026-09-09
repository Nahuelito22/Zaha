import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// La app clínica se sirve bajo /app. La landing (Astro) vive en la raíz.
const BASE = '/app/'

export default defineConfig({
  base: BASE,
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // La carga de signos vitales tiene que funcionar sin señal: se precachea
      // el shell entero. Los datos van por la cola offline de Dexie, no por
      // la caché del service worker — una toma pendiente no es un recurso
      // cacheado, es una escritura que todavía no ocurrió.
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        // Nunca cachear respuestas de la API: un score viejo mostrado como
        // actual es peor que no mostrar nada.
        navigateFallbackDenylist: [/^\/rest\//, /^\/auth\//],
        // Las tipografías vienen de Google Fonts (ver index.html: no pueden ir
        // por @import). Sin esto, el shell abre offline pero con las fuentes
        // del sistema, y el peso de los números del score cambia justo donde
        // la jerarquía visual importa.
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\//,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'zaha-fonts-css' },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'zaha-fonts-archivos',
              cacheableResponse: { statuses: [0, 200] },
              expiration: { maxEntries: 12, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
        ],
      },
      manifest: {
        name: 'Zaha — Soporte a la decisión clínica',
        short_name: 'Zaha',
        description:
          'Cálculo de NEWS2 y alertas tempranas de deterioro para enfermería.',
        lang: 'es-AR',
        start_url: BASE,
        scope: BASE,
        display: 'standalone',
        // Sin `orientation`: forzar vertical bloquea la rotacion en la PWA
        // instalada. La app es mobile-first, pero un telefono en un soporte o
        // un usuario que necesita apaisado no puede quedar trabado (WCAG 1.3.4).
        background_color: '#ffffff',
        theme_color: '#1f5fb8',
        // El icono es territorio de marca: la Z sola sobre el beige de
        // `theme.json`, sin el wordmark, que a 192 px seria ilegible. El
        // maskable lleva el glifo al 58% para sobrevivir el recorte circular
        // de Android, que come el 20% del borde.
        icons: [
          { src: 'icons/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/pwa-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'icons/pwa-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
          { src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
      },
    }),
  ],
})
