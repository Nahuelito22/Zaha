import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { useSesion } from '../auth/sesion'
import {
  OPCIONES_ACVPU,
  RANGOS,
  type ACVPU,
  type CampoNumerico,
  type NivelRiesgo,
} from '../lib/tipos'
import { ChipRiesgo } from '../componentes/ChipRiesgo'

type Episodio = {
  id: string
  bed: string | null
  ward: string
  spo2_scale: number
  patient_id: string
  patients: { first_name: string; last_name: string; mrn: string } | null
}

type Guardado = {
  news2_score: number
  risk_level: NivelRiesgo
  single_red_flag: boolean
}

const VACIO: Record<CampoNumerico, string> = {
  respiratory_rate: '',
  oxygen_saturation: '',
  temperature: '',
  systolic_bp: '',
  heart_rate: '',
}

/**
 * Carga de los 7 parámetros NEWS2 (SCRUM-39 / HU-01).
 *
 * El score NO se calcula acá. Lo calcula el trigger de la base y se lee de
 * vuelta con `.select()`. Reimplementar NEWS2 en el cliente daría dos motores
 * que pueden divergir, y el que vale legalmente es el de la base. Una sola
 * fuente de verdad.
 */
export function CargarVitales() {
  const { encounterId } = useParams<{ encounterId: string }>()
  const { session } = useSesion()
  const navigate = useNavigate()

  const [episodio, setEpisodio] = useState<Episodio | null>(null)
  const [valores, setValores] = useState<Record<CampoNumerico, string>>(VACIO)
  const [oxigeno, setOxigeno] = useState(false)
  const [acvpu, setAcvpu] = useState<ACVPU | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [guardado, setGuardado] = useState<Guardado | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!encounterId) return
    supabase
      .from('encounters')
      .select('id, bed, ward, spo2_scale, patient_id, patients(first_name, last_name, mrn)')
      .eq('id', encounterId)
      .maybeSingle()
      .then(({ data, error }) => {
        if (error) setError(error.message)
        else setEpisodio(data as unknown as Episodio)
      })
  }, [encounterId])

  function fueraDeRango(campo: CampoNumerico): boolean {
    const bruto = valores[campo]
    if (bruto === '') return false
    const n = Number(bruto)
    return Number.isNaN(n) || n < RANGOS[campo].min || n > RANGOS[campo].max
  }

  const camposNumericos = Object.keys(RANGOS) as CampoNumerico[]
  const hayFueraDeRango = camposNumericos.some(fueraDeRango)
  const completo =
    camposNumericos.every((c) => valores[c] !== '') && acvpu !== null
  const puedeGuardar = completo && !hayFueraDeRango && !guardando

  async function guardar(e: FormEvent) {
    e.preventDefault()
    if (!puedeGuardar || !episodio || !session) return
    setGuardando(true)
    setError(null)

    const { data, error } = await supabase
      .from('vital_records')
      .insert({
        encounter_id: episodio.id,
        patient_id: episodio.patient_id,
        // La firma del registro no se delega: la política de inserción exige
        // que recorded_by sea el usuario autenticado.
        recorded_by: session.user.id,
        respiratory_rate: Number(valores.respiratory_rate),
        oxygen_saturation: Number(valores.oxygen_saturation),
        supplemental_oxygen: oxigeno,
        temperature: Number(valores.temperature),
        systolic_bp: Number(valores.systolic_bp),
        heart_rate: Number(valores.heart_rate),
        consciousness_level: acvpu,
      })
      .select('news2_score, risk_level, single_red_flag')
      .single()

    if (error) setError(error.message)
    else setGuardado(data as Guardado)
    setGuardando(false)
  }

  if (error && !episodio) {
    return (
      <p role="alert" className="panel ctext">
        {error}
      </p>
    )
  }
  if (!episodio) return <p className="ctext">Cargando episodio…</p>

  const paciente = episodio.patients
    ? `${episodio.patients.last_name}, ${episodio.patients.first_name}`
    : '—'

  // --- Confirmación posterior al guardado -----------------------------------
  if (guardado) {
    return (
      <div className="flex flex-col gap-5">
        <div className="panel flex flex-col gap-3">
          <h2>Toma registrada</h2>
          <p className="ctext">
            {paciente} · cama {episodio.bed ?? '—'}
          </p>

          <div className="flex flex-wrap items-center gap-4">
            <span className="flex items-baseline gap-1">
              <span className="vital-value vital-value-lg">
                {guardado.news2_score}
              </span>
              <span className="vital-unit">NEWS2</span>
            </span>
            <ChipRiesgo nivel={guardado.risk_level} />
          </div>

          {/* Este aviso solo corresponde cuando el rojo aislado es lo que
              eleva el nivel: con un total de 5 o más, el nivel ya viene del
              puntaje y decir "aunque el total sea bajo" seria falso. */}
          {guardado.single_red_flag && guardado.risk_level === 'Medio Bajo' && (
            <p className="ctext-sm font-semibold">
              El puntaje total es bajo, pero hay un parámetro aislado en 3. Por
              esa sola razón el nivel sube a Medio Bajo y requiere revisión.
            </p>
          )}

          <p className="ctext-xs ctext-muted">
            El puntaje lo calculó la base de datos, no esta pantalla. El registro
            ya no se puede editar: si hay un error, se corrige cargando una
            enmienda con su motivo.
          </p>
        </div>

        <div className="flex gap-3">
          <Link to="/" className="cbtn cbtn-primary">
            Volver a la sala
          </Link>
          <button
            className="cbtn cbtn-secondary"
            onClick={() => {
              setGuardado(null)
              setValores(VACIO)
              setOxigeno(false)
              setAcvpu(null)
            }}
          >
            Cargar otra toma
          </button>
        </div>
      </div>
    )
  }

  // --- Formulario -----------------------------------------------------------
  return (
    <form onSubmit={guardar} className="flex flex-col gap-5">
      <div>
        <h2>{paciente}</h2>
        <p className="ctext-sm ctext-muted">
          {episodio.ward} · cama {episodio.bed ?? '—'} ·{' '}
          {episodio.patients?.mrn}
        </p>
      </div>

      {/* La escala de SpO2 es una PRESCRIPCIÓN médica y cambia cómo puntúa la
          saturación. Se muestra siempre, y enfermería no puede tocarla. */}
      {episodio.spo2_scale === 2 && (
        <div className="panel ctext-sm">
          <strong>Escala de SpO₂ 2 (hipercapnia).</strong> Objetivo de saturación
          prescrito 88–92%. La saturación puntúa con esta escala, no con la
          estándar. Solo medicina puede cambiarla.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {camposNumericos.map((campo) => {
          const r = RANGOS[campo]
          const malo = fueraDeRango(campo)
          return (
            <label key={campo} className="flex flex-col gap-1.5">
              <span className="vital-label">
                {r.etiqueta} ({r.unidad})
              </span>
              <input
                className="cinput"
                type="number"
                inputMode="decimal"
                step={campo === 'temperature' ? '0.1' : '1'}
                value={valores[campo]}
                aria-invalid={malo}
                aria-describedby={malo ? `${campo}-error` : undefined}
                onChange={(e) =>
                  setValores((v) => ({ ...v, [campo]: e.target.value }))
                }
                required
              />
              {malo && (
                <span id={`${campo}-error`} className="ctext-2xs font-semibold">
                  Fuera del rango posible ({r.min}–{r.max} {r.unidad}). Revisá el
                  valor cargado.
                </span>
              )}
            </label>
          )
        })}

        <fieldset className="flex flex-col gap-1.5">
          <legend className="vital-label">Oxígeno suplementario</legend>
          <div className="flex gap-2">
            <button
              type="button"
              className={`cbtn ${oxigeno ? 'cbtn-secondary' : 'cbtn-primary'} flex-1`}
              aria-pressed={!oxigeno}
              onClick={() => setOxigeno(false)}
            >
              Aire ambiente
            </button>
            <button
              type="button"
              className={`cbtn ${oxigeno ? 'cbtn-primary' : 'cbtn-secondary'} flex-1`}
              aria-pressed={oxigeno}
              onClick={() => setOxigeno(true)}
            >
              Con oxígeno
            </button>
          </div>
        </fieldset>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="vital-label">Nivel de consciencia (ACVPU)</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {OPCIONES_ACVPU.map((o) => (
            <button
              key={o.valor}
              type="button"
              aria-pressed={acvpu === o.valor}
              className={`cbtn cbtn-start ${
                acvpu === o.valor ? 'cbtn-primary' : 'cbtn-secondary'
              }`}
              onClick={() => setAcvpu(o.valor)}
            >
              {/* Ancho fijo para que las 5 siglas alineen y el significado
                  de cada una arranque en la misma columna. */}
              <span className="vital-value w-5 text-[17px]">{o.sigla}</span>
              <span className="font-medium">{o.texto}</span>
            </button>
          ))}
        </div>
      </fieldset>

      {error && (
        <p role="alert" className="panel ctext-sm font-semibold">
          No se pudo guardar: {error}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <button type="submit" className="cbtn cbtn-primary" disabled={!puedeGuardar}>
          {guardando ? 'Guardando…' : 'Guardar toma'}
        </button>
        <button
          type="button"
          className="cbtn cbtn-secondary"
          onClick={() => navigate('/')}
        >
          Cancelar
        </button>
      </div>

      {!completo && (
        <p className="ctext-xs ctext-muted">
          Faltan parámetros. NEWS2 sobre datos incompletos no es un NEWS2 válido,
          así que se cargan los 7 o no se guarda.
        </p>
      )}
    </form>
  )
}
