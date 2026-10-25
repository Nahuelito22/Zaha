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

// Sin `mrn`: la sala identifica por cama y por nombre. El número de historia
// clínica se dejó de mostrar y, por lo tanto, se dejó de pedir — traer un dato
// que nadie usa es ruido en la consulta y en el tipo. Está en el detalle del
// paciente, que es donde hace falta.
type Cama = {
  encounter_id: string
  bed: string | null
  paciente: string
  news2_score: number | null
  risk_level: NivelRiesgo | null
  /** `null`: internado y todavía sin ninguna toma. */
  recorded_at: string | null
}

type EpisodioCrudo = {
  id: string
  bed: string | null
  patients: { first_name: string; last_name: string } | null
}

type TomaCruda = {
  encounter_id: string
  news2_score: number | null
  risk_level: NivelRiesgo | null
  recorded_at: string
}

/** Antigüedad de la última toma; sin ninguna, es lo más atrasado que puede estar. */
function edadDe(c: Cama, ahora: number) {
  return c.recorded_at === null
    ? { texto: 'sin tomas', vieja: true }
    : antiguedad(c.recorded_at, ahora)
}

export function Sala() {
  const [camas, setCamas] = useState<Cama[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enVivo, setEnVivo] = useState(false)
  const ahora = useAhora()

  const cargar = useCallback(async () => {
    // LA SALA PARTE DE LAS INTERNACIONES, NO DE LAS TOMAS.
    // Antes se armaba sólo desde las tomas vigentes, y un paciente recién
    // internado —sin ninguna toma todavía— no aparecía: justo el que más
    // necesita que alguien le cargue vitales, y sin su fila no había desde
    // dónde hacerlo. Ahora cada internación activa es una fila, con su última
    // toma si la tiene y "sin score" si no.
    //
    // Las tomas se leen de la VISTA de vigentes: una toma enmendada no puede
    // aparecer como el valor actual del paciente.
    const [episodios, tomas] = await Promise.all([
      supabase
        .from('encounters')
        .select('id, bed, patients(first_name, last_name)')
        .eq('status', 'activo'),
      supabase
        .from('vital_records_vigentes')
        .select('encounter_id, news2_score, risk_level, recorded_at')
        .order('recorded_at', { ascending: false }),
    ])

    const fallo = episodios.error ?? tomas.error
    if (fallo) {
      setError(fallo.message)
      return
    }
    setError(null)

    // La toma vigente más reciente de cada episodio: vienen ordenadas, así
    // que la primera que aparece es la que vale.
    const ultima = new Map<string, TomaCruda>()
    for (const t of tomas.data as TomaCruda[]) {
      if (!ultima.has(t.encounter_id)) ultima.set(t.encounter_id, t)
    }

    const porEpisodio = new Map<string, Cama>()
    for (const e of episodios.data as unknown as EpisodioCrudo[]) {
      const t = ultima.get(e.id)
      porEpisodio.set(e.id, {
        encounter_id: e.id,
        bed: e.bed,
        paciente: e.patients
          ? `${e.patients.last_name}, ${e.patients.first_name}`
          : '—',
        news2_score: t?.news2_score ?? null,
        risk_level: t?.risk_level ?? null,
        recorded_at: t?.recorded_at ?? null,
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
          const edad = edadDe(c, ahora)
          return (
            <li
              key={c.encounter_id}
              className={`panel px-4 py-3 ${
                c.risk_level
                  ? `risk-edge-${CLASE_RIESGO[c.risk_level]}`
                  : 'score-incomplete'
              }`}
            >
              {/* TRES FILAS, Y EL ORDEN NO ES CASUAL.
                  Antes era una sola fila con `flex-wrap`, y en un teléfono el
                  nombre competía por el ancho con el puntaje, el chip y el
                  botón: quedaba truncado en «Funes, …», que es justo el dato
                  que el enfermero necesita leer entero para saber a quién está
                  por atender. */}
              <div className="flex flex-col gap-2">
                {/* Lo que se escanea de un vistazo, en una línea. */}
                <div className="flex items-center gap-x-3">
                  <span className="col-num ctext w-14 shrink-0 font-bold">
                    {c.bed ?? '—'}
                  </span>

                  <span className="ml-auto flex items-baseline gap-1">
                    <span className="vital-value">{c.news2_score ?? '—'}</span>
                    <span className="vital-unit">NEWS2</span>
                  </span>

                  <ChipRiesgo nivel={c.risk_level} />
                </div>

                {/* El nombre, en su propia línea y SIN truncar: si no entra,
                    baja a dos renglones. Ya no lleva el número de historia
                    clínica: en la sala la cama identifica sola, y ese número
                    largo le robaba el ancho al nombre. Sigue estando en el
                    detalle del paciente, a un toque de acá. */}
                <div className="min-w-0">
                  <Link
                    to={`/paciente/${c.encounter_id}`}
                    className="ctext-lead block font-semibold"
                  >
                    {c.paciente}
                  </Link>
                  <span className="ctext-2xs ctext-muted">
                    <span
                      className={`staleness${edad.vieja ? ' staleness-overdue' : ''}`}
                    >
                      {edad.texto}
                    </span>
                  </span>
                </div>

                {/* LA ACCIÓN PRINCIPAL VA A LA DERECHA.
                    En teléfono y tablet la app se usa de pie al lado de la
                    cama, sosteniendo el equipo con una mano: el pulgar llega
                    cómodo al borde derecho y forzado al izquierdo. El hueco que
                    quedaba libre lo ocupa el acceso al historial, que antes
                    exigía entrar al detalle y buscarlo. */}
                <div className="flex items-center gap-2">
                  <Link
                    to={`/paciente/${c.encounter_id}#historial`}
                    className="cbtn cbtn-secondary no-underline"
                  >
                    Historial
                  </Link>
                  <Link
                    to={`/cargar/${c.encounter_id}`}
                    className="cbtn cbtn-secondary no-underline ml-auto"
                  >
                    Cargar vitales
                  </Link>
                </div>
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
              const edad = edadDe(c, ahora)
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
                  {/* Sin número de historia clínica, igual que en las
                      tarjetas: en la sala la cama ya identifica, y el número
                      aparece en el detalle del paciente. */}
                  <td>
                    <Link
                      to={`/paciente/${c.encounter_id}`}
                      className="font-semibold"
                    >
                      {c.paciente}
                    </Link>
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
                        tarjetas, estos botones se tocan durante la ronda y no
                        pueden bajar de 44 px. Ver design_system/README.md.

                        EL ORDEN ES EL MISMO QUE EN LAS TARJETAS, Y ESO IMPORTA:
                        `Cargar vitales` va SIEMPRE último, el de más a la
                        derecha, en las dos vistas. Si cambiara de lugar según el
                        ancho de la pantalla, el gesto aprendido al pie de una
                        cama dejaría de servir en el carro del office. */}
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/paciente/${c.encounter_id}#historial`}
                        className="cbtn cbtn-secondary no-underline"
                      >
                        Historial
                      </Link>
                      <Link
                        to={`/cargar/${c.encounter_id}`}
                        className="cbtn cbtn-secondary no-underline"
                      >
                        Cargar vitales
                      </Link>
                    </div>
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
