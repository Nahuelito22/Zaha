import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'
import type { Perfil } from '../lib/tipos'

type EstadoSesion = {
  session: Session | null
  perfil: Perfil | null
  cargando: boolean
  salir: () => Promise<void>
}

const Ctx = createContext<EstadoSesion | null>(null)

/**
 * El rol NO se lee del JWT ni se guarda en el cliente como fuente de verdad:
 * se lee de `profiles`, que es lo que evalúan las políticas RLS. Acá solo se
 * usa para decidir qué mostrar. Si alguien manipulara este valor en el
 * navegador vería botones distintos, pero la base seguiría rechazando la
 * operación — el control está del lado del servidor, no de la interfaz.
 */
export function SesionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      if (!data.session) setCargando(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => {
      setSession(s)
      if (!s) {
        setPerfil(null)
        setCargando(false)
      }
    })
    return () => sub.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session) return
    let vivo = true
    setCargando(true)
    supabase
      .from('profiles')
      .select('id, full_name, role, license_id, active')
      .eq('id', session.user.id)
      .maybeSingle()
      .then(({ data }) => {
        if (!vivo) return
        setPerfil((data as Perfil) ?? null)
        setCargando(false)
      })
    return () => {
      vivo = false
    }
  }, [session])

  const valor = useMemo<EstadoSesion>(
    () => ({
      session,
      perfil,
      cargando,
      salir: async () => {
        await supabase.auth.signOut()
      },
    }),
    [session, perfil, cargando],
  )

  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>
}

export function useSesion() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useSesion tiene que usarse dentro de <SesionProvider>')
  return ctx
}
