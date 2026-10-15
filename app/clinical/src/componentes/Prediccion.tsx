import { useEffect, useState } from 'react'
import { servicioPrediccion } from '../lib/prediccion.supabase'
import {
  ETIQUETA_PARAMETRO,
  separarContribuciones,
  type Contribucion,
  type ResultadoPrediccion,
} from '../lib/prediccion'
import { fechaHora } from '../lib/tipos'

/**
 * Estimación del motor de IA, separada del score determinístico (SCRUM-67).
 *
 * LA REGLA QUE ESTE COMPONENTE EXISTE PARA HACER CUMPLIR
 * El usuario tiene que poder distinguir, de un vistazo, **"esto lo calculó la escala" de
 * "esto lo estimó un modelo"**. Por eso todo lo de acá va en violeta punteado
 * (`.predict`), fuera de la escala cromática de NEWS2 — donde el rojo, el ámbar y el
 * verde están reservados en exclusiva a los cuatro niveles de riesgo. Un panel sólido con
 * un número grande haría que la estimación pareciera un dato determinístico más.
 *
 * El borde **discontinuo** es la señal no cromática: quien no distingue el violeta del
 * gris igual ve que ese bloque está dibujado distinto del resto.
 *
 * SI NO HAY ESTIMACIÓN, NO PASA NADA
 * El ADR-004 dice que el NEWS2 nunca depende de la API de IA. Acá eso se traduce en que
 * los estados `dormido`, `caido` y `sin_tomas` **no son errores**: se muestra una línea
 * discreta y el resto de la pantalla queda intacto. No hay `role="alert"`, no hay rojo, y
 * el mensaje aclara que el puntaje no depende de esto.
 *
 * POR QUÉ ESTE COMPONENTE NO VA EN EL TABLERO DE SALA
 * El tablero muestra la sala entera y ordena por NEWS2, que es la escala validada. Meter
 * una estimación por cama sería N llamadas para una pantalla cuyo trabajo es priorizar
 * con la escala, y competiría visualmente con el dato que manda. La estimación vive donde
 * se mira a UN paciente y se la puede leer con su explicación.
 */
export function Prediccion({ patientId }: { patientId: string }) {
  const [resultado, setResultado] = useState<ResultadoPrediccion | null>(null)

  useEffect(() => {
    let vigente = true

    // `pedir` nunca lanza: por eso no hay try/catch. Ver la obligación dura
    // documentada en `lib/prediccion.ts`.
    void servicioPrediccion.pedir(patientId).then((r) => {
      if (vigente) setResultado(r)
    })

    return () => {
      vigente = false
    }
  }, [patientId])

  // Sin estado de carga aparte: `null` ya significa "todavía no contestó". El
  // componente se monta con `key={patientId}` en el llamador, así que cambiar de
  // paciente lo reinicia y no hay que resetear nada a mano desde el efecto.
  if (resultado === null) {
    return <p className="ctext-sm ctext-muted">Consultando el motor predictivo…</p>
  }

  if (resultado.estado !== 'ok') {
    return (
      <p className="ctext-sm ctext-muted">
        <span className="predict">sin estimación</span>{' '}
        {resultado.mensaje}
      </p>
    )
  }

  const { prediccion, medicion } = resultado
  const explicacion = prediccion.explicacion
  const { accionables, deBase } = separarContribuciones(
    explicacion?.contribuciones ?? [],
  )
  // La escala de las barras es relativa a la contribución más grande de ESTA
  // predicción: lo que importa es cuál pesó más en este paciente, no comparar
  // magnitudes entre pacientes.
  const maxima = Math.max(
    ...(explicacion?.contribuciones ?? []).map((c) => Math.abs(c.contribucion)),
    0.0001,
  )

  return (
    <section className="predict-panel flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="m-0">Estimación del modelo</h3>
        <span className="predict">
          {prediccion.alerta ? 'alerta' : 'sin alerta'} ·{' '}
          {(prediccion.probabilidad * 100).toFixed(1)} %
        </span>
      </div>

      <p className="ctext-sm">
        Esto <strong>no es NEWS2</strong>. Es una estimación de un modelo entrenado sobre
        otra población, y se muestra aparte justamente para que no se confunda con el
        puntaje de la escala.
      </p>

      {explicacion === null ? (
        <p className="ctext-sm ctext-muted">
          La explicación de esta estimación no pudo verificarse contra el modelo, así que
          no se muestra. El número de arriba sigue siendo válido.
        </p>
      ) : (
        <>
          <ul className="flex flex-col gap-2">
            {accionables.map((c) => (
              <Fila key={c.parametro} c={c} maxima={maxima} />
            ))}
          </ul>

          {deBase.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="ctext-xs ctext-muted">
                Pesa en la estimación, pero no es algo sobre lo que se pueda actuar en
                esta toma:
              </p>
              <ul className="flex flex-col gap-2">
                {deBase.map((c) => (
                  <Fila key={c.parametro} c={c} maxima={maxima} />
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <p className="ctext-xs ctext-muted">
        Umbral usado: {prediccion.punto_de_operacion.umbral.toFixed(3)} (sensibilidad
        objetivo {(prediccion.punto_de_operacion.sensibilidad_objetivo * 100).toFixed(0)} %).
        {medicion && <> Estimado sobre la toma de {fechaHora(medicion.recorded_at)}.</>}
      </p>

      {/* La advertencia viaja con cada predicción desde la API. Se muestra, no se
          esconde: es la diferencia entre presentar un resultado y presentarlo con su
          límite. */}
      <p className="ctext-xs ctext-muted italic">{prediccion.advertencia}</p>
    </section>
  )
}

/** Una contribución, con su barra proporcional. */
function Fila({ c, maxima }: { c: Contribucion; maxima: number }) {
  const ancho = Math.round((Math.abs(c.contribucion) / maxima) * 100)
  return (
    <li className="predict-contrib">
      <span className="min-w-0 flex-1">
        {ETIQUETA_PARAMETRO[c.parametro] ?? c.parametro}
      </span>
      <span className="col-num">{c.valor}</span>
      <span
        className={`predict-barra${c.direccion === 'reduce' ? ' predict-barra-reduce' : ''}`}
        style={{ width: `${Math.max(ancho, 2)}%`, maxWidth: '96px' }}
        // La barra es decorativa: el dato lo dice el texto de al lado, que es lo
        // que lee un lector de pantalla.
        aria-hidden="true"
      />
      <span className="ctext-xs ctext-muted w-16 text-right">
        {c.direccion === 'reduce' ? 'aleja' : 'acerca'}
      </span>
    </li>
  )
}
