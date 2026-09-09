import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import {
  PESO_RIESGO,
  PESO_SIN_SCORE,
  CLASE_RIESGO,
  type NivelRiesgo,
} from '../lib/tipos'
import { ChipRiesgo, antiguedad } from '../componentes/ChipRiesgo'
import { useAhora } from '../lib/reloj'

type Cama = {
  encounter_id: string
  bed: string | null
  paciente: string
  mrn: string
  news2_score: number | null
  risk_level: NivelRiesgo | null
  recorded_at: string
}

type FilaCruda = {
  encounter_id: string
  news2_score: number | null
  risk_level: NivelRiesgo | null
  recorded_at: string
  patients: { first_name: string; last_name: string; mrn: string } | null
  encounters: { bed: string | null } | null
}

export function Sala() {
  const [camas, setCamas] = useState<Cama[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enVivo, setEnVivo] = useState(false)
  const ahora = useAhora()

  const cargar = useCallback(async () => {
    // Se lee de la VISTA de vigentes: una toma enmendada no puede aparecer
    // como el valor actual del paciente.
    const { data, error } = await supabase
      .from('vital_records_vigentes')
      .select(
        'encounter_id, news2_score, risk_level, recorded_at, patients(first_name, last_name, mrn), encounters(bed)',
      )
      .order('recorded_at', { ascending: false })

    if (error) {
      setError(error.message)
      return
    }
    setError(null)

    // Una fila por cama: la toma vigente más reciente de cada episodio.
    const porEpisodio = new Map<string, Cama>()
    for (const cruda of data as unknown as FilaCruda[]) {
      if (porEpisodio.has(cruda.encounter_id)) continue
      porEpisodio.set(cruda.encounter_id, {
        encounter_id: cruda.encounter_id,
        bed: cruda.encounters?.bed ?? null,
        paciente: cruda.patients
          ? `${cruda.patients.last_name}, ${cruda.patients.first_name}`
          : '—',
        mrn: cruda.patients?.mrn ?? '',
        news2_score: cruda.news2_score,
        risk_level: cruda.risk_level,
        recorded_at: cruda.recorded_at,
      })
    }

    // Sin score no es lo mismo que riesgo bajo: es su propia categoría.
    const peso = (c: Cama) =>
      c.risk_level === null ? PESO_SIN_SCORE : PESO_RIESGO[c.risk_level]

    setCamas(
      [...porEpisodio.values()].sort(
        (a, b) =>
          peso(a) - peso(b) ||
          // Dentro del mismo nivel manda el puntaje: un 6 y un 5 son los dos
          // "Medio", pero no piden lo mismo. Recién si empatan, la cama, que
          // es lo único estable — sin esto la lista se reordenaría sola en
          // cada refresco y jefatura perdería la referencia visual.
          (b.news2_score ?? -1) - (a.news2_score ?? -1) ||
          (a.bed ?? '').localeCompare(b.bed ?? ''),
      ),
    )
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  // — Tiempo real (HU-06) —
  // Se escucha la TABLA `vital_records` y se recarga la vista de vigentes. El
  // payload del evento no se usa para derivar estado: solo avisa "andá a
  // releer". Una enmienda son dos operaciones (el INSERT de la toma nueva y el
  // UPDATE que marca la vieja como superseded) y aplicarlas sueltas dejaría la
  // pantalla en un estado intermedio que en la base nunca existió.
  const pendiente = useRef<number | null>(null)
  useEffect(() => {
    const recargarPronto = () => {
      // Una ronda de carga dispara varios eventos seguidos. Sin esta espera
      // corta, cada uno pediría la sala entera de nuevo.
      if (pendiente.current !== null) clearTimeout(pendiente.current)
      pendiente.current = window.setTimeout(() => void cargar(), 400)
    }

    const canal = supabase
      .channel('sala-vitales')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'vital_records' },
        recargarPronto,
      )
      .subscribe((estado) => setEnVivo(estado === 'SUBSCRIBED'))

    // Red de seguridad: si la tablet estuvo suspendida, el socket pudo haberse
    // caído sin que llegara ningún evento. Al volver a la pantalla se relee.
    const alVolver = () => {
      if (document.visibilityState === 'visible') void cargar()
    }
    document.addEventListener('visibilitychange', alVolver)

    return () => {
      if (pendiente.current !== null) clearTimeout(pendiente.current)
      document.removeEventListener('visibilitychange', alVolver)
      void supabase.removeChannel(canal)
    }
  }, [cargar])

  if (error) {
    return (
      <p role="alert" className="panel ctext">
        No se pudo cargar la sala: {error}
      </p>
    )
  }

  if (camas === null) return <p className="ctext">Cargando sala…</p>

  if (camas.length === 0) {
    return (
      <div className="panel flex flex-col gap-2">
        <p className="ctext font-semibold">No hay camas visibles.</p>
        <p className="ctext-sm ctext-muted">
          Si esperabas ver pacientes, las políticas de acceso están denegando la
          lectura. Verificá que tu perfil exista y esté activo.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="ctext-xs ctext-muted">
        {camas.length} camas ocupadas · ordenadas por riesgo ·{' '}
        {/* Se dice si el tablero se está actualizando solo o no. Un panel de
            triage que quedó mudo y parece al día es exactamente el modo de
            falla que hay que evitar. */}
        {enVivo ? 'actualización en vivo' : 'sin actualización en vivo'}
      </p>

      {/* Tablet vertical al pie de la cama: una tarjeta por cama. */}
      <ul className="ancho:hidden flex flex-col gap-2">
        {camas.map((c) => {
          const edad = antiguedad(c.recorded_at, ahora)
          return (
            <li
              key={c.encounter_id}
              className={`panel px-4 py-3 ${
                c.risk_level
                  ? `risk-edge-${CLASE_RIESGO[c.risk_level]}`
                  : 'score-incomplete'
              }`}
            >
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <span className="col-num ctext w-14 shrink-0 font-bold">
                  {c.bed ?? '—'}
                </span>

                <span className="min-w-0 flex-1">
                  <Link
                    to={`/paciente/${c.encounter_id}`}
                    className="ctext-lead block truncate font-semibold"
                  >
                    {c.paciente}
                  </Link>
                  <span className="ctext-2xs ctext-muted">
                    {c.mrn} ·{' '}
                    <span
                      className={`staleness${edad.vieja ? ' staleness-overdue' : ''}`}
                    >
                      {edad.texto}
                    </span>
                  </span>
                </span>

                <span className="flex items-baseline gap-1">
                  <span className="vital-value">{c.news2_score ?? '—'}</span>
                  <span className="vital-unit">NEWS2</span>
                </span>

                <ChipRiesgo nivel={c.risk_level} />

                <Link
                  to={`/cargar/${c.encounter_id}`}
                  className="cbtn cbtn-secondary no-underline"
                >
                  Cargar vitales
                </Link>
              </div>
            </li>
          )
        })}
      </ul>

      {/* Tablet acostada o carro del office: la sala entera de un vistazo, que
          es lo que la HU-06 pide para poder distribuir la carga. Es el MISMO
          dato y el MISMO orden; solo cambia la forma. La rama que no
          corresponde queda en display:none, así que tampoco existe para un
          lector de pantalla: nunca se lee la sala dos veces. */}
      <div className="ancho:block hidden overflow-x-auto">
        <table className="ctable">
          <caption className="sr-only">
            Camas ocupadas, ordenadas de mayor a menor riesgo
          </caption>
          <thead>
            <tr>
              <th scope="col">Cama</th>
              <th scope="col">Paciente</th>
              <th scope="col">NEWS2</th>
              <th scope="col">Nivel</th>
              <th scope="col">Última toma</th>
              <th scope="col">
                <span className="sr-only">Acciones</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {camas.map((c) => {
              const edad = antiguedad(c.recorded_at, ahora)
              return (
                <tr key={c.encounter_id}>
                  {/* El borde de riesgo va en la celda y no en la fila: con
                      `border-collapse: collapse` el navegador no pinta el
                      box-shadow de un <tr>. Igual el nivel nunca depende de
                      ese borde — lo dicen el chip con su forma y su texto. */}
                  <td
                    className={`col-num font-bold ${
                      c.risk_level ? `risk-edge-${CLASE_RIESGO[c.risk_level]}` : ''
                    }`}
                  >
                    {c.bed ?? '—'}
                  </td>
                  <td>
                    <Link
                      to={`/paciente/${c.encounter_id}`}
                      className="font-semibold"
                    >
                      {c.paciente}
                    </Link>
                    <span className="ctext-2xs ctext-muted block">{c.mrn}</span>
                  </td>
                  <td
                    className={`col-num${c.risk_level ? '' : ' score-incomplete'}`}
                  >
                    <span className="vital-value">{c.news2_score ?? '—'}</span>
                  </td>
                  <td>
                    <ChipRiesgo nivel={c.risk_level} />
                  </td>
                  <td>
                    <span
                      className={`staleness${edad.vieja ? ' staleness-overdue' : ''}`}
                    >
                      {edad.texto}
                    </span>
                  </td>
                  <td>
                    {/* Sin `cbtn-sm`: aunque la tabla sea más densa que las
                        tarjetas, este botón se toca durante la ronda y no puede
                        bajar de 44 px. Ver design_system/README.md. */}
                    <Link
                      to={`/cargar/${c.encounter_id}`}
                      className="cbtn cbtn-secondary no-underline"
                    >
                      Cargar vitales
                    </Link>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
