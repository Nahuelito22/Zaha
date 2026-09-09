import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom'
import { SesionProvider, useSesion } from './auth/sesion'
import { Login } from './paginas/Login'
import { Sala } from './paginas/Sala'
import { CargarVitales } from './paginas/CargarVitales'
import { DetallePaciente } from './paginas/DetallePaciente'
import { EstadoCola } from './componentes/EstadoCola'
import { ROL_LEGIBLE } from './lib/tipos'

function Encabezado() {
  const { perfil, salir } = useSesion()
  return (
    <header
      className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3"
      style={{ borderColor: 'var(--c-border)', background: 'var(--c-bg)' }}
    >
      <Link to="/" className="text-[19px] font-bold no-underline">
        Zaha
      </Link>
      {perfil && (
        <div className="flex items-center gap-4">
          <span className="ctext-xs text-right leading-tight">
            <span className="block font-semibold">{perfil.full_name}</span>
            <span className="ctext-muted">
              {ROL_LEGIBLE[perfil.role]}
              {perfil.license_id ? ` · ${perfil.license_id}` : ''}
            </span>
          </span>
          <button className="cbtn cbtn-secondary cbtn-sm" onClick={salir}>
            Salir
          </button>
        </div>
      )}
    </header>
  )
}

/**
 * Puerta de entrada. No alcanza con estar autenticado: hace falta un perfil
 * activo, que es lo que evalúan las políticas RLS. Un usuario de auth sin
 * perfil vería la aplicación vacía y sin explicación, así que se lo dice.
 */
function Privado({ children }: { children: React.ReactNode }) {
  const { session, perfil, cargando } = useSesion()

  if (cargando) return null
  // El login queda FUERA de `zaha-clinical`: monta `zaha-brand`, que es la
  // capa que le corresponde. Ver el comentario en Login.
  if (!session) return <Login />

  if (!perfil) {
    return (
      <div className="zaha-clinical mx-auto max-w-md px-5 py-10">
        <div className="panel flex flex-col gap-2">
          <p className="ctext font-semibold">Tu usuario no tiene perfil activo.</p>
          <p className="ctext-sm ctext-muted">
            No vas a poder ver ni cargar datos hasta que jefatura habilite tu
            cuenta.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="zaha-clinical flex min-h-full flex-col">
      <Encabezado />
      {/* El tope de 3xl (768px) es el ancho de lectura cómodo de un formulario
          y se mantiene como norma. `ancho:` lo levanta solo en tablet acostada,
          donde la sala se muestra como tabla y necesita las seis columnas: si
          el contenedor siguiera capado, la tabla scrollearía dentro de una
          franja angosta en el medio de una pantalla vacía. Ver el comentario
          del breakpoint en index.css. */}
      <main className="ancho:max-w-6xl mx-auto w-full max-w-3xl flex-1 px-5 py-6">
        {/* Va acá y no dentro de cada página: lo pendiente de enviar es estado
            de la sesión, no de la pantalla en la que se esté parado. */}
        <EstadoCola />
        {children}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <div className="min-h-full">
      <SesionProvider>
        <BrowserRouter basename="/app">
          <Routes>
            <Route
              path="/"
              element={
                <Privado>
                  <Sala />
                </Privado>
              }
            />
            <Route
              path="/cargar/:encounterId"
              element={
                <Privado>
                  <CargarVitales />
                </Privado>
              }
            />
            <Route
              path="/paciente/:encounterId"
              element={
                <Privado>
                  <DetallePaciente />
                </Privado>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </SesionProvider>
    </div>
  )
}
