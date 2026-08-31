import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import {
  PARAMETROS_NEWS2,
  fechaHora,
  type VitalDesglose,
} from '../lib/tipos'
import { ChipRiesgo, antiguedad } from '../componentes/ChipRiesgo'

type Episodio = {
  id: string
  bed: string | null
  ward: string
  spo2_scale: number
  patients: { first_name: string; last_name: string; mrn: string } | null
}

/**
 * Detalle de paciente: de dónde sale el número, y qué pasó antes (SCRUM-40).
 *
 * Un score sin desglose es un oráculo: no se puede discutir, no deja detectar
 * una carga mal tipeada y no enseña nada. Esta pantalla existe para que el
 * enfermero pueda mirar un 7 y decir "sale de la frecuencia respiratoria, no
 * del paciente".
 *
 * Los subpuntajes NO se calculan acá: vienen de `vital_records_desglose`, que
 * los deriva con las mismas funciones que usa el trigger. Es la misma regla de
 * una sola fuente de verdad que rige la carga de vitales.
 */
export function DetallePaciente() {
  const { encounterId } = useParams<{ encounterId: string }>()
  const [episodio, setEpisodio] = useState<Episodio | null>(null)
  const [tomas, setTomas] = useState<VitalDesglose[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!encounterId) return
    let vigente = true

    async function cargar() {
      const [ep, vr] = await Promise.all([
        supabase
          .from('encounters')
          .select('id, bed, ward, spo2_scale, patients(first_name, last_name, mrn)')
          .eq('id', encounterId)
          .maybeSingle(),
        // Se lee el historial COMPLETO, enmendadas incluidas: ver el dato
        // erróneo al lado del corregido es lo que el diseño append-only
        // existe para permitir.
        supabase
          .from('vital_records_desglose')
          .select('*')
          .eq('encounter_id', encounterId)
          .order('recorded_at', { ascending: false }),
      ])

      if (!vigente) return
      if (ep.error) return setError(ep.error.message)
      if (vr.error) return setError(vr.error.message)
      setEpisodio(ep.data as unknown as Episodio)
      setTomas(vr.data as unknown as VitalDesglose[])
    }

    void cargar()
    return () => {
      vigente = false
    }
  }, [encounterId])

  if (error) {
    return (
      <p role="alert" className="panel ctext">
        No se pudo cargar el paciente: {error}
      </p>
    )
  }
  if (!episodio || tomas === null) return <p className="ctext">Cargando paciente…</p>

  const paciente = episodio.patients
    ? `${episodio.patients.last_name}, ${episodio.patients.first_name}`
    : '—'
  // La vigente es la más reciente que nadie enmendó. Una toma corregida no
  // puede figurar como el valor actual del paciente.
  const actual = tomas.find((t) => t.superseded_by === null) ?? null

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2>{paciente}</h2>
        <p className="ctext-sm ctext-muted">
          {episodio.ward} · cama {episodio.bed ?? '—'} · {episodio.patients?.mrn}
        </p>
      </div>

      {actual === null ? (
        <div className="panel score-incomplete flex flex-col gap-2">
          <p className="ctext font-semibold">Sin tomas registradas.</p>
          <p className="ctext-sm ctext-muted">
            Este paciente todavía no tiene signos vitales cargados, así que no
            tiene NEWS2. No es lo mismo que un riesgo bajo.
          </p>
        </div>
      ) : (
        <>
          <Vigente toma={actual} escalaEpisodio={episodio.spo2_scale} />
          <Desglose toma={actual} />
        </>
      )}

      <Historial tomas={tomas} />

      <div className="flex flex-wrap gap-3">
        <Link to={`/cargar/${episodio.id}`} className="cbtn cbtn-primary no-underline">
          Cargar vitales
        </Link>
        <Link to="/" className="cbtn cbtn-secondary no-underline">
          Volver a la sala
        </Link>
      </div>
    </div>
  )
}

/** Encabezado con el score vigente y su antigüedad. */
function Vigente({
  toma,
  escalaEpisodio,
}: {
  toma: VitalDesglose
  escalaEpisodio: number
}) {
  const edad = antiguedad(toma.recorded_at)
  return (
    <div className="panel flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <span className="flex items-baseline gap-1">
          <span className="vital-value vital-value-lg">{toma.news2_score ?? '—'}</span>
          <span className="vital-unit">NEWS2</span>
        </span>
        <ChipRiesgo nivel={toma.risk_level} />
        <span className={`staleness${edad.vieja ? ' staleness-overdue' : ''}`}>
          {fechaHora(toma.recorded_at)} · {edad.texto}
        </span>
      </div>

      {/* La escala con la que se puntuó esta toma puede no ser la prescripción
          de hoy: las tomas viejas conservan la que regía entonces. Si difieren
          hay que decirlo, o el desglose parece mal calculado. */}
      {toma.spo2_scale_used !== null && toma.spo2_scale_used !== escalaEpisodio && (
        <p className="ctext-sm">
          Puntuada con la <strong>escala de SpO₂ {toma.spo2_scale_used}</strong>, que
          era la vigente al momento de la toma. Hoy el episodio tiene prescrita
          la {escalaEpisodio}.
        </p>
      )}
    </div>
  )
}

/** Los 7 parámetros con su aporte al total. El corazón del ticket. */
function Desglose({ toma }: { toma: VitalDesglose }) {
  const enRojo = PARAMETROS_NEWS2.filter((p) => (toma[p.sub] as number) === 3).length

  return (
    <div className="flex flex-col gap-2">
      <h3>De dónde sale el score</h3>

      <ul className="flex flex-col gap-1">
        {PARAMETROS_NEWS2.map((p) => {
          const puntos = toma[p.sub] as number
          return (
            <li
              key={p.etiqueta}
              className={`panel flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 ${
                puntos === 3 ? 'risk-edge-high' : ''
              }`}
            >
              <span className="vital-label min-w-0 flex-1">{p.etiqueta}</span>
              <span className="col-num vital-value text-base">
                {p.valor(toma)}
              </span>
              <span className="vital-subscore w-8 text-center">+{puntos}</span>
            </li>
          )
        })}
      </ul>

      <p className="ctext-xs ctext-muted">
        Los 7 aportes suman {toma.news2_score}. El cálculo lo hace la base de
        datos, no esta pantalla.
      </p>

      {/* El aviso del rojo AISLADO solo corresponde cuando ese rojo es lo que
          eleva el nivel. Con un total de 5 o más el nivel ya viene del puntaje,
          y decir "aunque el total sea bajo" frente a un 17 es sencillamente
          falso. Es la misma distinción que hace la pantalla de carga. */}
      {enRojo > 0 &&
        (toma.risk_level === 'Medio Bajo' ? (
          <p className="ctext-sm font-semibold">
            El puntaje total es bajo, pero hay un parámetro aislado en 3
            (marcado con el borde rojo). Por esa sola razón el nivel sube a
            Medio Bajo y requiere revisión.
          </p>
        ) : (
          <p className="ctext-sm font-semibold">
            {enRojo === 1
              ? 'Un parámetro puntúa 3, el máximo de la escala. Está marcado con el borde rojo.'
              : `${enRojo} parámetros puntúan 3, el máximo de la escala. Están marcados con el borde rojo.`}
          </p>
        ))}
    </div>
  )
}

/** Historial completo del episodio, con la cadena de enmiendas visible. */
function Historial({ tomas }: { tomas: VitalDesglose[] }) {
  if (tomas.length === 0) return null

  return (
    <div className="flex flex-col gap-2">
      <h3>Historial</h3>
      <p className="ctext-xs ctext-muted">
        {tomas.length} {tomas.length === 1 ? 'toma' : 'tomas'}. Las corregidas no
        se borran: quedan visibles junto a la enmienda que las reemplazó.
      </p>

      <ul className="flex flex-col gap-2">
        {tomas.map((t) => {
          const enmendada = t.superseded_by !== null
          return (
            <li
              key={t.id}
              className={`panel flex flex-col gap-1 px-4 py-3 ${
                enmendada ? 'score-incomplete' : ''
              }`}
            >
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <span className="col-num ctext-sm">{fechaHora(t.recorded_at)}</span>
                <span className="flex items-baseline gap-1">
                  <span className="vital-value">{t.news2_score ?? '—'}</span>
                  <span className="vital-unit">NEWS2</span>
                </span>
                <ChipRiesgo nivel={t.risk_level} />
                {enmendada && (
                  <span className="ctext-xs font-semibold">corregida</span>
                )}
              </div>

              {t.amends_id !== null && (
                <p className="ctext-xs">
                  <strong>Enmienda.</strong> {t.amendment_reason}
                </p>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
