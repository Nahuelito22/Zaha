import { useState, type FormEvent } from 'react'
import { supabase } from '../lib/supabase'

/**
 * Login.
 *
 * Es la ÚNICA pantalla de este bundle que pertenece a la capa de MARCA y no a
 * la clínica (design_system/README.md): el login, la landing y el onboarding
 * llevan la paleta tierra; `/app` no.
 *
 * Por qué acá sí y en `/app` no: la regla que separa las capas es que la
 * terracota ocupa el mismo rango cromático que el ámbar de alerta NEWS2, así
 * que teñir la interfaz clínica hace que lo neutro parezca alerta y que la
 * alerta real deje de destacar. En una pantalla sin un solo dato de paciente
 * ese riesgo no existe, y sí importa que la primera impresión sea la marca.
 *
 * Las clases son las de `brand.css` (`card`, `input`, `btn`), NO las de la
 * capa clínica (`panel`, `cinput`, `cbtn`): las dos capas no comparten nombres.
 * Los modificadores `-touch` traen de vuelta el mínimo de 44px, porque esto se
 * usa en la misma tablet y con los mismos guantes que el resto.
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
    <div className="zaha-brand flex min-h-dvh w-full items-center justify-center px-6 py-12">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div>
          <h1>Zaha</h1>
          <p className="text-muted">Soporte a la decisión clínica</p>
        </div>

        <form onSubmit={entrar} className="card">
          <div className="field">
            <label htmlFor="login-email">Correo</label>
            <input
              id="login-email"
              type="email"
              className="input input-touch"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
            />
          </div>

          <div className="field">
            <label htmlFor="login-password">Contraseña</label>
            <input
              id="login-password"
              type="password"
              className="input input-touch"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-block btn-touch"
            disabled={cargando}
          >
            {cargando ? 'Entrando…' : 'Entrar'}
          </button>

          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
        </form>
      </div>
    </div>
  )
}
