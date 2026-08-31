import { useState, type FormEvent } from 'react'
import { supabase } from '../lib/supabase'

/**
 * Login.
 *
 * Es la ÚNICA pantalla de este bundle que pertenece a la capa de MARCA y no a
 * la clínica (design_system/README.md): el login, la landing y el onboarding
 * llevan la paleta tierra; `/app` no. Hoy sigue montando `zaha-clinical` para
 * no quedar sin estilos, y ese es exactamente el trabajo de SCRUM-36:
 * reemplazar esa clase por la capa de marca.
 *
 * OJO al hacerlo: `brand.css` NO está namespaceado — define sobre `:root` y
 * `body`, así que importarlo en este bundle pisaría la capa clínica de toda la
 * aplicación, no solo de esta pantalla. Antes de aplicarlo hay que encerrarlo
 * bajo una clase raíz, igual que `clinical.css`.
 */
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
    <div className="zaha-clinical mx-auto flex min-h-full w-full max-w-sm flex-col justify-center gap-6 px-6 py-12">
      <div>
        <h1>Zaha</h1>
        <p className="ctext ctext-muted">Soporte a la decisión clínica</p>
      </div>

      <form onSubmit={entrar} className="panel flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="vital-label">Correo</span>
          <input
            type="email"
            className="cinput"
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
          <p role="alert" className="ctext-sm font-semibold">
            {error}
          </p>
        )}
      </form>
    </div>
  )
}
