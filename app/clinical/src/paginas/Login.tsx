import { useState, type FormEvent } from 'react'
import { supabase } from '../lib/supabase'

export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(false)

  async function entrar(e: FormEvent) {
    e.preventDefault()
    setCargando(true)
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    // El mensaje se traduce: "Invalid login credentials" no le dice nada a una
    // enfermera a las 4 de la mañana. Y no se distingue entre usuario
    // inexistente y contraseña incorrecta, para no filtrar qué correos existen.
    if (error) {
      setError(
        error.message === 'Invalid login credentials'
          ? 'Correo o contraseña incorrectos.'
          : error.message,
      )
    }
    setCargando(false)
  }

  return (
    <div className="mx-auto flex min-h-full w-full max-w-sm flex-col justify-center gap-6 px-6 py-12">
      <div>
        <h1>Zaha</h1>
        <p className="text-[15px]" style={{ color: 'var(--c-text-muted)' }}>
          Soporte a la decisión clínica
        </p>
      </div>

      <form onSubmit={entrar} className="panel flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="vital-label">Correo</span>
          <input
            type="email"
            className="cinput"
            style={{ fontSize: 16 }}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            required
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="vital-label">Contraseña</span>
          <input
            type="password"
            className="cinput"
            style={{ fontSize: 16 }}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        <button type="submit" className="cbtn cbtn-primary" disabled={cargando}>
          {cargando ? 'Entrando…' : 'Entrar'}
        </button>

        {error && (
          <p role="alert" className="text-[14px] font-semibold">
            {error}
          </p>
        )}
      </form>
    </div>
  )
}
