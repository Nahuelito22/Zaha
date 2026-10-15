// @ts-check
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

// El motor de IA vive en un Space de Hugging Face. La demostración de la landing
// lo consulta en /api/motor, en su propio dominio: en producción esa ruta la
// reenvía Vercel (ver vercel.json) y en desarrollo, este proxy. Así el navegador
// nunca habla con otro dominio y no dependemos de la configuración de CORS de
// Gradio, que no está documentada.
const MOTOR = 'https://zaha-cdss-inferencia.hf.space';

// https://astro.build/config
export default defineConfig({
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: {
        '/api/motor': {
          target: MOTOR,
          changeOrigin: true,
          rewrite: (ruta) => ruta.replace(/^\/api\/motor/, '/api'),
        },
      },
    },
  },
});
