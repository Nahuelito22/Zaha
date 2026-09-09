import { useCallback, useEffect, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { baseLocal, sincronizar, descartarRechazada } from '../lib/cola'
import { useSesion } from '../auth/sesion'
import { fechaHora } from '../lib/tipos'

/**
 * Estado de la cola offline (SCRUM-44).
 *
 * Se muestra solo cuando hay algo que decir. Una barra permanente que dice
 * "todo sincronizado" es ruido en una interfaz clínica: compite por la
 * atención con la información de riesgo, que es lo único que debería
 * interrumpir.
 */
export function EstadoCola() {
  const { session } = useSesion()
  const userId = session?.user.id
  const [sincronizando, setSincronizando] = useState(false)

  const tomas = useLiveQuery(
    async () =>
      userId
        ? await baseLocal.tomas.where('recorded_by').equals(userId).sortBy('recorded_at')
        : [],
    [userId],
    [],
  )

  const pendientes = tomas.filter((t) => t.estado === 'pendiente')
  const rechazadas = tomas.filter((t) => t.estado === 'rechazado')

  const correr = useCallback(async () => {
    if (!userId) return
    setSincronizando(true)
    try {
      await sincronizar(userId)
    } finally {
      setSincronizando(false)
    }
  }, [userId])

  /**
   * Disparadores de sincronización. `online` del navegador es una PISTA, no
   * una garantía: dice que hay interfaz de red, no que el servidor conteste.
   * Por eso el criterio real de éxito siempre es el resultado del INSERT, y
   * este evento solo decide cuándo vale la pena intentar.
   */
  useEffect(() => {
    if (!userId) return
    void correr()
    const alVolver = () => void correr()
    window.addEventListener('online', alVolver)
    return () => window.removeEventListener('online', alVolver)
  }, [userId, correr])

  if (pendientes.length === 0 && rechazadas.length === 0) return null

  return (
    <div className="panel mb-5 flex flex-col gap-3" role="status">
      {pendientes.length > 0 && (
        <>
          <p className="ctext-sm font-semibold">
            {pendientes.length === 1
              ? '1 toma guardada en este dispositivo, sin enviar'
              : `${pendientes.length} tomas guardadas en este dispositivo, sin enviar`}
          </p>
          <ul className="flex flex-col gap-1">
            {pendientes.map((t) => (
              <li key={t.id} className="ctext-xs ctext-muted">
                {t.paciente} · cama {t.cama ?? '—'} · {fechaHora(t.recorded_at)}
              </li>
            ))}
          </ul>
          <p className="ctext-xs ctext-muted">
            Todavía sin puntaje NEWS2: lo calcula el servidor al recibirlas.
          </p>
          <div>
            <button
              className="cbtn cbtn-secondary cbtn-sm"
              onClick={correr}
              disabled={sincronizando}
            >
              {sincronizando ? 'Enviando…' : 'Enviar ahora'}
            </button>
          </div>
        </>
      )}

      {rechazadas.length > 0 && (
        <>
          <p className="ctext-sm font-semibold">
            {rechazadas.length === 1
              ? '1 toma rechazada por el servidor'
              : `${rechazadas.length} tomas rechazadas por el servidor`}
          </p>
          <ul className="flex flex-col gap-2">
            {rechazadas.map((t) => (
              <li key={t.id} className="flex flex-col gap-1">
                <span className="ctext-xs">
                  {t.paciente} · cama {t.cama ?? '—'} · {fechaHora(t.recorded_at)}
                </span>
                <span className="ctext-2xs ctext-muted">{t.ultimo_error}</span>
                <span>
                  <button
                    className="cbtn cbtn-secondary cbtn-sm"
                    onClick={() => descartarRechazada(t.id)}
                  >
                    Descartar
                  </button>
                </span>
              </li>
            ))}
          </ul>
          <p className="ctext-xs ctext-muted">
            Reintentar no las va a arreglar. Descartarlas es la única salida, y
            solo se puede con las rechazadas: una pendiente todavía puede entrar.
          </p>
        </>
      )}
    </div>
  )
}
