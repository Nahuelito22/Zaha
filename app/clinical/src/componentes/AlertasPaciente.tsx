import { useCallback, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { useSesion } from '../auth/sesion'
import { construirAcuse, etiquetaAccion, type AccionAlerta } from '../lib/alertas'
import { fechaHora } from '../lib/tipos'
import { ChipRiesgo } from './ChipRiesgo'

type AlertaEnCola = {
  id: string
  source: 'news2' | 'ml'
  risk_level: 'Medio Bajo' | 'Medio' | 'Alto'
  news2_score: number | null
  message: string
  triggered_at: string
  fue_pospuesta: boolean
  postponed_until: string | null
}

/**
 * Alertas que requieren atención, con el flujo de un clic (SCRUM-68).
 *
 * DE DONDE SALE LA LISTA
 * De la vista `alertas_en_cola`, no de `alerts`. La vista define en UN solo lugar qué
 * cuenta como pendiente —pendientes más pospuestas con el plazo vencido—; si cada
 * pantalla escribiera ese criterio por su cuenta, dos pantallas terminarían difiriendo y
 * la que muestra de menos escondería una alerta real.
 *
 * UN CLIC ES UN CLIC
 * No hay modal, ni confirmación, ni campo de texto obligatorio. Validar y posponer se
 * resuelven apretando una vez, que es lo que el ticket pide y lo que mitiga la fatiga:
 * si atender una alerta cuesta tres pasos, la respuesta del turno ocupado es ignorarla.
 *
 * El botón de posponer **dice el plazo**. Un "posponer" a secas es una caja negra: el
 * usuario no sabe si la alerta vuelve en cinco minutos o nunca.
 *
 * LO QUE NO SE PUEDE DESHACER SE AVISA ANTES
 * Ninguna de las dos acciones borra nada: el log de auditoría es append-only y conserva
 * cada acto con su firma. Por eso no hace falta pedir confirmación — no hay pérdida
 * posible, sólo un registro más.
 */
export function AlertasPaciente({ patientId }: { patientId: string }) {
  const { perfil } = useSesion()
  const [alertas, setAlertas] = useState<AlertaEnCola[] | null>(null)
  const [trabajando, setTrabajando] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const cargar = useCallback(async () => {
    const { data, error } = await supabase
      .from('alertas_en_cola')
      .select('id, source, risk_level, news2_score, message, triggered_at, fue_pospuesta, postponed_until')
      .eq('patient_id', patientId)
      .order('triggered_at', { ascending: false })

    if (error) {
      setError(error.message)
      setAlertas([])
      return
    }
    setError(null)
    setAlertas((data ?? []) as AlertaEnCola[])
  }, [patientId])

  useEffect(() => {
    void cargar()
  }, [cargar])

  async function acusar(alerta: AlertaEnCola, accion: AccionAlerta) {
    if (!perfil) return
    setTrabajando(alerta.id)
    setError(null)

    try {
      const acuse = construirAcuse(accion, perfil.id)
      const { error } = await supabase.from('alerts').update(acuse).eq('id', alerta.id)
      if (error) throw new Error(error.message)
      await cargar()
    } catch (e) {
      // El acuse no se da por hecho: si la base lo rechazó, la alerta sigue en la
      // cola y se dice por qué. Una interfaz que "ya lo marqué" sin que el
      // servidor lo confirme es peor que una que falla visiblemente.
      setError(e instanceof Error ? e.message : 'no se pudo registrar el acuse')
    } finally {
      setTrabajando(null)
    }
  }

  if (alertas === null) return <p className="ctext-sm ctext-muted">Cargando alertas…</p>
  if (alertas.length === 0 && error === null) return null

  return (
    <section className="flex flex-col gap-2">
      <h3>Alertas por atender</h3>

      {error !== null && (
        <p role="alert" className="panel ctext-sm">
          No se pudo registrar el acuse: {error}. La alerta sigue pendiente.
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {alertas.map((a) => (
          <li
            key={a.id}
            className={`panel flex flex-col gap-2 px-4 py-3 risk-edge-${
              a.risk_level === 'Alto' ? 'high' : a.risk_level === 'Medio' ? 'med' : 'lowmed'
            }`}
          >
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <ChipRiesgo nivel={a.risk_level} />
              {a.source === 'ml' && <span className="predict">estimación</span>}
              <span className="ctext-sm">{a.message}</span>
              <span className="staleness">{fechaHora(a.triggered_at)}</span>
            </div>

            {/* Una alerta que VUELVE no es lo mismo que una que nunca se miró: sin
                esto, posponer se parecería a que no pasó nada. */}
            {a.fue_pospuesta && (
              <p className="ctext-xs ctext-muted">
                Pospuesta hasta {a.postponed_until ? fechaHora(a.postponed_until) : '—'}.
                El plazo venció y volvió a la cola.
              </p>
            )}

            <div className="flex flex-wrap gap-2">
              {(['validar', 'posponer'] as const).map((accion) => (
                <button
                  key={accion}
                  type="button"
                  className={`cbtn cbtn-sm ${
                    accion === 'validar' ? 'cbtn-primary' : 'cbtn-secondary'
                  }`}
                  disabled={trabajando === a.id || !perfil}
                  onClick={() => void acusar(a, accion)}
                >
                  {trabajando === a.id ? 'Registrando…' : etiquetaAccion(accion)}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>

      <p className="ctext-xs ctext-muted">
        Cada acuse queda firmado y registrado en la bitácora de auditoría, que no admite
        modificación ni borrado.
      </p>
    </section>
  )
}
