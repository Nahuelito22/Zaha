import { createClient } from '@supabase/supabase-js'

// La clave publicable es pública por diseño: no otorga ningún acceso por sí
// sola. Todo el control está en las políticas RLS de la base, que evalúan el
// JWT del usuario autenticado. Nunca poner acá la service_role key: esa
// saltea RLS y en el navegador equivale a publicar la historia clínica.
const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

if (!url || !key) {
  throw new Error(
    'Faltan VITE_SUPABASE_URL o VITE_SUPABASE_PUBLISHABLE_KEY. Copiá .env.example a .env.local.',
  )
}

export const supabase = createClient(url, key, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
})
