import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { useSesion } from '../auth/sesion'
import {
  CAMPOS_NUMERICOS,
  fechaHora,
  fueraDeRango,
  type ACVPU,
  type CampoNumerico,
  type NivelRiesgo,
} from '../lib/tipos'
import {
  cambios,
  construirEnmienda,
  motivoValido,
  MOTIVO_MINIMO,
  type TomaOriginal,
  type ValoresToma,
} from '../lib/enmienda'
import { ChipRiesgo } from '../componentes/ChipRiesgo'
import { CamposVitales } from '../componentes/CamposVitales'

type Toma = TomaOriginal & {
  news2_score: number | null
  risk_level: NivelRiesgo | null
  encounters: { bed: string | null; ward: string } | null
  patients: { first_name: string; last_name: string; mrn: string } | null
}

type Puntaje = { news2_score: number; risk_level: NivelRiesgo }

/**
 * Corrección de una toma mal cargada.
 *
 * La tabla es append-only, así que corregir es insertar una ENMIENDA: una toma nueva que
 * apunta a la errónea y dice por qué. La original no se borra; queda en el historial
 * marcada como corregida. Del lado de la base, `apply_amendment` la sella y cierra su
 * alerta pendiente, firmada por quien corrige y con el motivo.
 *
 * SIN CONEXIÓN NO SE CORRIGE
 * A diferencia de la carga, la corrección no pasa por la cola offline. Una toma nueva es
 * independiente de lo que haya en el servidor; una corrección no: apunta a una versión
 * que puede haber sido corregida por otra persona mientras tanto, y la base la rechazaría
 * horas después, cuando nadie está mirando. Mejor un "no se pudo, probá de nuevo" ahora.
 */
export function EnmendarToma() {
  const { tomaId } = useParams<{ tomaId: string }>()
  const { session } = useSesion()

  const [toma, setToma] = useState<Toma | null>(null)
  const [valores, setValores] = useState<Record<CampoNumerico, string> | null>(null)
  const [oxigeno, setOxigeno] = useState(false)
  const [acvpu, setAcvpu] = useState<ACVPU | null>(null)
  const [motivo, setMotivo] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hecho, setHecho] = useState<Puntaje | null>(null)
  const dialogo = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    if (!tomaId) return
    supabase
      .from('vital_records')
      .select(
        'id, encounter_id, patient_id, recorded_at, superseded_by, respiratory_rate, ' +
          'oxygen_saturation, supplemental_oxygen, temperature, systolic_bp, heart_rate, ' +
          'consciousness_level, news2_score, risk_level, ' +
          'encounters(bed, ward), patients(first_name, last_name, mrn)',
      )
      .eq('id', tomaId)
      .maybeSingle()
      .then(({ data, error }) => {
        if (error) return setError(error.message)
        if (!data) return setError('No se encontró la toma.')
        const t = data as unknown as Toma
        setToma(t)
        // El formulario arranca con los valores de la toma errónea: lo habitual es
        // corregir uno solo, y obligar a recargar los siete invita a errores nuevos.
        setValores(
          Object.fromEntries(CAMPOS_NUMERICOS.map((c) => [c, String(t[c])])) as Record<
            CampoNumerico,
            string
          >,
        )
        setOxigeno(t.supplemental_oxygen)
        setAcvpu(t.consciousness_level)
      })
  }, [tomaId])

  if (error && !toma) {
    return (
      <p role="alert" className="panel ctext">
        {error}
      </p>
    )
  }
  if (!toma || !valores) return <p className="ctext">Cargando toma…</p>

  const paciente = toma.patients
    ? `${toma.patients.last_name}, ${toma.patients.first_name}`
    : '—'
  const volver = `/paciente/${toma.encounter_id}#historial`

  if (toma.superseded_by !== null) {
    return (
      <div className="panel flex flex-col gap-3">
        <p className="ctext font-semibold">Esta toma ya fue corregida.</p>
        <p className="ctext-sm ctext-muted">
          Si la corrección también tiene un error, corregí la versión vigente desde el
          historial.
        </p>
        <Link to={volver} className="cbtn cbtn-secondary no-underline self-start">
          Volver al historial
        </Link>
      </div>
    )
  }

  const hayFueraDeRango = CAMPOS_NUMERICOS.some((c) => fueraDeRango(c, valores[c]))
  const completo = CAMPOS_NUMERICOS.every((c) => valores[c] !== '') && acvpu !== null
  const corregida: ValoresToma | null =
    completo && !hayFueraDeRango && acvpu
      ? {
          respiratory_rate: Number(valores.respiratory_rate),
          oxygen_saturation: Number(valores.oxygen_saturation),
          supplemental_oxygen: oxigeno,
          temperature: Number(valores.temperature),
          systolic_bp: Number(valores.systolic_bp),
          heart_rate: Number(valores.heart_rate),
          consciousness_level: acvpu,
        }
      : null
  const diferencias = corregida ? cambios(toma, corregida) : []
  const puedeGuardar =
    corregida !== null && diferencias.length > 0 && motivoValido(motivo) && !guardando

  function pedirConfirmacion(e: FormEvent) {
    e.preventDefault()
    if (!puedeGuardar) return
    setError(null)
    dialogo.current?.showModal()
  }

  async function confirmarYGuardar() {
    if (!puedeGuardar || !corregida || !toma || !session) return
    dialogo.current?.close()
    setGuardando(true)
    setError(null)

    try {
      const fila = construirEnmienda(toma, corregida, motivo, session.user.id, crypto.randomUUID())
      const { data, error } = await supabase
        .from('vital_records')
        .insert(fila)
        .select('news2_score, risk_level')
        .single()
      if (error) throw new Error(error.message)
      setHecho(data as Puntaje)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'no se pudo guardar la corrección')
    } finally {
      setGuardando(false)
    }
  }

  // --- Después de guardar ----------------------------------------------------
  if (hecho) {
    return (
      <div className="flex flex-col gap-5">
        <div className="panel flex flex-col gap-3">
          <h2>Corrección registrada</h2>
          <p className="ctext">
            {paciente} · toma de {fechaHora(toma.recorded_at)}
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <span className="flex items-baseline gap-1">
              <span className="vital-value vital-value-lg">{hecho.news2_score}</span>
              <span className="vital-unit">NEWS2</span>
            </span>
            <ChipRiesgo nivel={hecho.risk_level} />
          </div>
          <p className="ctext-xs ctext-muted">
            La toma original sigue en el historial, marcada como corregida. Si tenía una
            alerta pendiente, se cerró con tu nombre y este motivo; si el valor corregido
            la justifica, se generó una nueva.
          </p>
        </div>
        <Link to={volver} className="cbtn cbtn-primary no-underline self-start">
          Volver al paciente
        </Link>
      </div>
    )
  }

  // --- Formulario -------------------------------------------------------------
  return (
    <form onSubmit={pedirConfirmacion} className="flex flex-col gap-5">
      <div>
        <h2>Corregir una toma</h2>
        <p className="ctext-sm ctext-muted">
          {paciente} · {toma.encounters?.ward} · cama {toma.encounters?.bed ?? '—'} ·{' '}
          {toma.patients?.mrn}
        </p>
      </div>

      <div className="panel flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-4">
          <span className="ctext-sm">Toma de {fechaHora(toma.recorded_at)}</span>
          <span className="flex items-baseline gap-1">
            <span className="vital-value">{toma.news2_score ?? '—'}</span>
            <span className="vital-unit">NEWS2</span>
          </span>
          <ChipRiesgo nivel={toma.risk_level} />
        </div>
        <p className="ctext-xs ctext-muted">
          La toma original no se borra: queda en el historial marcada como corregida, junto
          a esta corrección. La hora de la toma no cambia.
        </p>
      </div>

      <CamposVitales
        valores={valores}
        onValor={(campo, v) => setValores((prev) => (prev ? { ...prev, [campo]: v } : prev))}
        oxigeno={oxigeno}
        onOxigeno={setOxigeno}
        acvpu={acvpu}
        onAcvpu={setAcvpu}
      />

      <label className="flex flex-col gap-1.5">
        <span className="vital-label">Motivo de la corrección</span>
        <textarea
          className="cinput"
          rows={3}
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          placeholder="Por ejemplo: se tipeó 8 en lugar de 18 en la frecuencia respiratoria"
          required
        />
        {/* El motivo queda para siempre en el historial y en la alerta que se cierra.
            Es lo único que explica la corrección a quien la lea después. */}
        <span className="ctext-2xs ctext-muted">
          Queda visible en el historial. Mínimo {MOTIVO_MINIMO} caracteres.
        </span>
      </label>

      {error && (
        <p role="alert" className="panel ctext-sm font-semibold">
          No se pudo guardar la corrección: {error}. Las correcciones no se guardan sin
          conexión.
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <button type="submit" className="cbtn cbtn-primary" disabled={!puedeGuardar}>
          {guardando ? 'Guardando…' : 'Guardar corrección'}
        </button>
        <Link to={volver} className="cbtn cbtn-secondary no-underline">
          Cancelar
        </Link>
      </div>

      {corregida !== null && diferencias.length === 0 && (
        <p className="ctext-xs ctext-muted">
          Todavía no cambiaste ningún valor. Una corrección tiene que corregir algo.
        </p>
      )}

      <dialog ref={dialogo} className="cdialog">
        <h3 className="m-0">Confirmar la corrección</h3>
        <p className="ctext-sm ctext-muted">
          La toma original queda en el historial como corregida. Esta corrección tampoco se
          podrá borrar.
        </p>

        <ul className="cdialog-resumen">
          {diferencias.map((d) => (
            <li key={d.etiqueta}>
              <span className="ctext-sm">{d.etiqueta}</span>
              <span className="col-num font-semibold">
                {d.antes} → {d.despues}
              </span>
            </li>
          ))}
          <li>
            <span className="ctext-sm">Motivo</span>
            <span className="font-semibold">{motivo.trim()}</span>
          </li>
        </ul>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="cbtn cbtn-primary"
            onClick={() => void confirmarYGuardar()}
          >
            Confirmar y guardar
          </button>
          <button
            type="button"
            className="cbtn cbtn-secondary"
            onClick={() => dialogo.current?.close()}
          >
            Volver a revisar
          </button>
        </div>
      </dialog>
    </form>
  )
}
