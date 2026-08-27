import { useEffect, useState, type FormEvent } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './lib/supabase'

/**
 * Pantalla de verificación del scaffold.
 *
 * No es el dashboard: es la prueba de que la cadena completa funciona —
 * Vite, React, el cliente de Supabase, el login, las políticas RLS y el
 * seed de desarrollo. El tablero real es SCRUM-33 / SCRUM-42.
 *
 * Si esta pantalla lista pacientes, entonces el usuario se autenticó, tiene
 * un profile activo y las políticas lo dejaron leer. Si devuelve una lista
 * vacía sin error, el RLS está denegando — que es su trabajo.
 */

type NivelRiesgo = 'Bajo' | 'Medio Bajo' | 'Medio' | 'Alto'

type FilaCama = {
  encounter_id: string
  bed: string | null
  paciente: string
  news2_score: number | null
  risk_level: NivelRiesgo | null
  recorded_at: string
}

const CLASE_RIESGO: Record<NivelRiesgo, string> = {
  Bajo: 'low',
  'Medio Bajo': 'lowmed',
  Medio: 'med',
  Alto: 'high',
}

// Orden clínico: lo urgente primero. Nunca alfabético ni por cama.
const PESO_RIESGO: Record<NivelRiesgo, number> = {
  Alto: 0,
  Medio: 1,
  'Medio Bajo': 2,
  Bajo: 3,
}

function ChipRiesgo({ nivel }: { nivel: NivelRiesgo | null }) {
  if (!nivel) return <span className="text-[13px] opacity-60">sin score</span>
  return (
    <span className={`risk risk-${CLASE_RIESGO[nivel]}`}>
      <span className="risk-glyph" aria-hidden="true" />
      {nivel}
    </span>
  )
}

function Login() {
  const [email, setEmail] = useState('vanina.aguero@zaha.dev')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(false)

  async function entrar(e: FormEvent) {
    e.preventDefault()
    setCargando(true)
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) setError(error.message)
    setCargando(false)
  }

  return (
    <form
      onSubmit={entrar}
      className="mx-auto mt-24 flex w-full max-w-sm flex-col gap-4 px-6"
    >
      <div>
        <h1>Zaha</h1>
        <p className="text-[15px] opacity-70">Verificación del scaffold</p>
      </div>

      <label className="flex flex-col gap-1 text-[13px] font-semibold">
        Correo
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="rounded border px-3 py-2 text-[15px] font-normal"
        />
      </label>

      <label className="flex flex-col gap-1 text-[13px] font-semibold">
        Contraseña
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="rounded border px-3 py-2 text-[15px] font-normal"
        />
      </label>

      <button
        type="submit"
        disabled={cargando}
        className="rounded px-3 py-2 text-[15px] font-semibold text-white disabled:opacity-50"
        style={{ background: 'var(--c-action)' }}
      >
        {cargando ? 'Entrando…' : 'Entrar'}
      </button>

      {error && (
        <p className="text-[13px]" style={{ color: 'var(--c-risk-high)' }}>
          {error}
        </p>
      )}
    </form>
  )
}

function Sala({ session }: { session: Session }) {
  const [filas, setFilas] = useState<FilaCama[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    ;(async () => {
      // Se lee de la VISTA de vigentes, no de vital_records: una toma
      // enmendada no debe aparecer como el valor actual del paciente.
      const { data, error } = await supabase
        .from('vital_records_vigentes')
        .select(
          'encounter_id, news2_score, risk_level, recorded_at, patients(first_name, last_name), encounters(bed)',
        )
        .order('recorded_at', { ascending: false })

      if (!vivo) return
      if (error) {
        setError(error.message)
        return
      }

      // Una fila por cama: la toma vigente más reciente de cada episodio.
      const porEpisodio = new Map<string, FilaCama>()
      for (const r of data as unknown as Array<Record<string, never>>) {
        const row = r as unknown as {
          encounter_id: string
          news2_score: number | null
          risk_level: NivelRiesgo | null
          recorded_at: string
          patients: { first_name: string; last_name: string } | null
          encounters: { bed: string | null } | null
        }
        if (porEpisodio.has(row.encounter_id)) continue
        porEpisodio.set(row.encounter_id, {
          encounter_id: row.encounter_id,
          bed: row.encounters?.bed ?? null,
          paciente: row.patients
            ? `${row.patients.last_name}, ${row.patients.first_name}`
            : '—',
          news2_score: row.news2_score,
          risk_level: row.risk_level,
          recorded_at: row.recorded_at,
        })
      }

      setFilas(
        [...porEpisodio.values()].sort(
          (a, b) =>
            PESO_RIESGO[a.risk_level ?? 'Bajo'] -
              PESO_RIESGO[b.risk_level ?? 'Bajo'] ||
            (a.bed ?? '').localeCompare(b.bed ?? ''),
        ),
      )
    })()
    return () => {
      vivo = false
    }
  }, [])

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-5 px-6 py-10">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1>Clínica Médica</h1>
          <p className="text-[13px] opacity-70">{session.user.email}</p>
        </div>
        <button
          onClick={() => supabase.auth.signOut()}
          className="text-[13px] font-semibold underline"
        >
          Salir
        </button>
      </header>

      {error && (
        <p className="text-[14px]" style={{ color: 'var(--c-risk-high)' }}>
          {error}
        </p>
      )}

      {filas === null && !error && <p className="text-[14px]">Cargando…</p>}

      {filas?.length === 0 && (
        <p className="text-[14px]">
          Sin camas visibles. Si esperabas datos, el RLS está denegando: revisá
          que el perfil exista y esté activo.
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {filas?.map((f) => (
          <li
            key={f.encounter_id}
            className={`flex items-center gap-4 rounded border px-4 py-3 risk-edge-${
              CLASE_RIESGO[f.risk_level ?? 'Bajo']
            }`}
          >
            <span className="w-16 shrink-0 font-mono text-[13px] font-semibold">
              {f.bed ?? '—'}
            </span>
            <span className="flex-1 text-[15px]">{f.paciente}</span>
            <span className="w-10 text-right text-[17px] font-bold tabular-nums">
              {f.news2_score ?? '—'}
            </span>
            <ChipRiesgo nivel={f.risk_level} />
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [listo, setListo] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setListo(true)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) =>
      setSession(s),
    )
    return () => sub.subscription.unsubscribe()
  }, [])

  if (!listo) return null

  return (
    <div className="zaha-clinical min-h-full">
      {session ? <Sala session={session} /> : <Login />}
    </div>
  )
}
