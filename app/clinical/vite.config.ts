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
        globPatterns: ['**/*.{js,css,html,svg,woff2}'],
        // Nunca cachear respuestas de la API: un score viejo mostrado como
        // actual es peor que no mostrar nada.
        navigateFallbackDenylist: [/^\/rest\//, /^\/auth\//],
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
        orientation: 'portrait',
        background_color: '#ffffff',
        theme_color: '#1f5fb8',
        // TODO(SCRUM-43): reemplazar por los PNG 192/512 exportados del
        // logo de marca. El SVG alcanza para desarrollo pero algunos
        // instaladores de Android prefieren PNG rasterizado.
        icons: [
          { src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml' },
          {
            src: 'favicon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
})
