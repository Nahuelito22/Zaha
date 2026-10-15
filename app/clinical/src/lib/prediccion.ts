/**
 * Cliente del motor predictivo, con degradación elegante (SCRUM-65).
 *
 * LA REGLA QUE ESTE ARCHIVO TIENE QUE HACER CUMPLIR
 * El ADR-004 dice que el NEWS2 determinístico **nunca** depende de la API de IA. La
 * escala la calcula un trigger de la base y llega con la medición; la estimación del
 * modelo es un agregado opcional. Entonces este módulo tiene una sola obligación dura:
 *
 *     NINGUNA FUNCIÓN DE ACÁ PUEDE LANZAR UNA EXCEPCIÓN.
 *
 * Si lanzara, un `await` sin `try` en una pantalla de triage dejaría la sala entera en
 * blanco porque un Space gratuito se durmió. El puntaje que sí importa estaría calculado,
 * guardado y disponible, y aun así no se vería. Por eso todo devuelve un resultado
 * discriminado y nunca un throw, igual que `ResultadoEnvio` en `cola.ts`.
 *
 * POR QUÉ ESTE ARCHIVO NO IMPORTA `./supabase`
 * Para poder probarlo. `supabase.ts` lee `import.meta.env` al cargarse y revienta fuera
 * de Vite, así que la lógica de degradación —que es lo que hay que probar— quedaría sin
 * pruebas. Acá se recibe el invocador por parámetro; el cableado real está en
 * `prediccion.supabase.ts`, que es trivial y no tiene decisiones.
 *
 * EL CORTACIRCUITO, Y POR QUÉ NO ES UNA OPTIMIZACIÓN
 * El tablero de triage muestra la sala completa. Si el Space está dormido y cada tarjeta
 * pide su estimación por separado, son N llamadas que tardan 8 segundos cada una, todas
 * destinadas a fallar. Con veinte camas eso es un tablero inutilizable durante minutos
 * por un servicio que es opcional. Después del primer fallo se deja de preguntar por un
 * rato y se responde con el último estado conocido, sin red.
 */

/** El cuerpo que devuelve la Edge Function `prediccion`. Siempre llega con 200. */
export type RespuestaDeLaFuncion = {
  estado: 'ok' | 'dormido' | 'caido' | 'sin_tomas'
  prediccion: unknown | null
  mensaje: string
  medicion?: { id: string; recorded_at: string }
}

export type ResultadoPrediccion =
  | {
      estado: 'ok'
      prediccion: Prediccion
      medicion: { id: string; recorded_at: string } | null
    }
  /**
   * No hay estimación, y eso **no es un error**: la interfaz muestra NEWS2 y sigue.
   * `sin_sesion` es el único que amerita mirar algo, y tampoco rompe nada.
   */
  | {
      estado: 'dormido' | 'caido' | 'sin_tomas' | 'sin_sesion'
      prediccion: null
      mensaje: string
    }

/** Lo que devuelve el motor. Se tipa sólo lo que la interfaz usa. */
export type Prediccion = {
  probabilidad: number
  alerta: boolean
  es_estimacion: true
  punto_de_operacion: {
    sensibilidad_objetivo: number
    umbral: number
    tasa_de_alertas_esperada: number | null
    elegido_por: 'cliente' | 'valor_por_defecto'
  }
  explicacion: {
    exacta: true
    intercepto: number
    logit: number
    probabilidad_reconstruida: number
    reconstruye_la_probabilidad: boolean
    contribuciones: {
      parametro: string
      valor: number
      contribucion: number
      direccion: 'aumenta' | 'reduce' | 'neutro'
    }[]
  } | null
  advertencia: string
}

export type Invocador = (
  nombre: string,
  cuerpo: Record<string, unknown>,
) => Promise<{ data: unknown; error: unknown }>

/**
 * Cuánto se deja de preguntar después de un fallo. Un Space gratuito tarda del orden de
 * medio minuto en despertar, así que insistir antes es ruido garantizado.
 */
export const PAUSA_TRAS_FALLO_MS = 30_000

const MENSAJES: Record<Exclude<ResultadoPrediccion['estado'], 'ok'>, string> = {
  dormido: 'El motor predictivo está despertando. El puntaje NEWS2 no depende de él.',
  caido: 'El motor predictivo no está disponible. El puntaje NEWS2 no depende de él.',
  sin_tomas: 'El paciente no tiene mediciones vigentes para estimar.',
  sin_sesion: 'Sesión no iniciada. El puntaje NEWS2 no depende de esto.',
}

function sinPrediccion(
  estado: Exclude<ResultadoPrediccion['estado'], 'ok'>,
  mensaje?: string,
): ResultadoPrediccion {
  return { estado, prediccion: null, mensaje: mensaje || MENSAJES[estado] }
}

/**
 * Una estimación sin su verificación de consistencia no se muestra.
 *
 * La API marca `reconstruye_la_probabilidad: false` cuando las contribuciones no
 * reproducen la probabilidad servida — es decir, cuando la explicación no describe al
 * modelo que respondió. En ese caso se descarta la explicación y se deja la probabilidad:
 * mostrar una explicación equivocada de una alerta clínica es peor que no explicar.
 */
export function depurarExplicacion(prediccion: Prediccion): Prediccion {
  if (prediccion.explicacion && !prediccion.explicacion.reconstruye_la_probabilidad) {
    return { ...prediccion, explicacion: null }
  }
  return prediccion
}

/**
 * Parámetros sobre los que enfermería NO puede actuar al pie de la cama.
 *
 * SCRUM-66 dejó medido que la edad es el **segundo contribuyente** del modelo. Mostrarla
 * en la misma lista que la frecuencia respiratoria invita a leer "el paciente está en
 * riesgo por su edad", que no es una conclusión accionable ni es lo que el modelo quiso
 * decir: la edad es un factor de base, no algo que haya cambiado hoy.
 *
 * Se siguen mostrando —ocultarlas haría que las contribuciones no sumaran el logit y la
 * explicación dejaría de ser verificable—, pero separadas y después.
 */
export const PARAMETROS_NO_ACCIONABLES = new Set(['edad'])

export type Contribucion = NonNullable<Prediccion['explicacion']>['contribuciones'][number]

/**
 * Separa las contribuciones en las que enfermería puede atender y las de base.
 *
 * Conserva el orden de entrada, que la API ya devuelve por magnitud decreciente.
 */
export function separarContribuciones(contribuciones: Contribucion[]): {
  accionables: Contribucion[]
  deBase: Contribucion[]
} {
  const accionables: Contribucion[] = []
  const deBase: Contribucion[] = []
  for (const c of contribuciones) {
    ;(PARAMETROS_NO_ACCIONABLES.has(c.parametro) ? deBase : accionables).push(c)
  }
  return { accionables, deBase }
}

/** Nombre clínico del parámetro. El de la API es el del modelo, no el de la pantalla. */
export const ETIQUETA_PARAMETRO: Record<string, string> = {
  frecuencia_respiratoria: 'Frecuencia respiratoria',
  spo2: 'Saturación de oxígeno',
  temperatura: 'Temperatura',
  presion_sistolica: 'Presión sistólica',
  frecuencia_cardiaca: 'Frecuencia cardíaca',
  confusion: 'Confusión nueva',
  edad: 'Edad',
}

export type ServicioPrediccion = {
  pedir: (
    patientId: string,
    opciones?: { sensibilidadObjetivo?: number },
  ) => Promise<ResultadoPrediccion>
  /** Para la interfaz: si está en pausa, ni vale la pena mostrar un spinner. */
  enPausa: () => boolean
  reiniciar: () => void
}

export function crearServicioPrediccion(
  invocar: Invocador,
  ahora: () => number = Date.now,
  pausaMs: number = PAUSA_TRAS_FALLO_MS,
): ServicioPrediccion {
  let pausadoHasta = 0
  let ultimoEstadoMalo: Exclude<ResultadoPrediccion['estado'], 'ok'> = 'caido'

  const enPausa = () => ahora() < pausadoHasta

  async function pedir(
    patientId: string,
    opciones: { sensibilidadObjetivo?: number } = {},
  ): Promise<ResultadoPrediccion> {
    if (enPausa()) return sinPrediccion(ultimoEstadoMalo)

    let respuesta: { data: unknown; error: unknown }
    try {
      respuesta = await invocar('prediccion', {
        patient_id: patientId,
        ...(opciones.sensibilidadObjetivo !== undefined
          ? { sensibilidad_objetivo: opciones.sensibilidadObjetivo }
          : {}),
      })
    } catch {
      // Red caída, DNS, CORS, lo que sea. Nunca sale de acá.
      pausadoHasta = ahora() + pausaMs
      ultimoEstadoMalo = 'caido'
      return sinPrediccion('caido')
    }

    if (respuesta.error) {
      // 401 de la Edge Function: no hay sesión. No se pausa, porque se arregla con un
      // login y la proxima llamada ya tendria que andar.
      const mensaje = String((respuesta.error as { message?: string })?.message ?? '')
      if (/401|jwt|unauthor/i.test(mensaje)) return sinPrediccion('sin_sesion')

      pausadoHasta = ahora() + pausaMs
      ultimoEstadoMalo = 'caido'
      return sinPrediccion('caido')
    }

    const cuerpo = respuesta.data as RespuestaDeLaFuncion | null
    if (!cuerpo || typeof cuerpo.estado !== 'string') {
      pausadoHasta = ahora() + pausaMs
      ultimoEstadoMalo = 'caido'
      return sinPrediccion('caido')
    }

    if (cuerpo.estado !== 'ok') {
      // `sin_tomas` NO pausa: es del paciente, no del motor. Pausar por eso dejaria sin
      // estimacion a toda la sala porque una cama no tiene mediciones todavia.
      if (cuerpo.estado === 'dormido' || cuerpo.estado === 'caido') {
        pausadoHasta = ahora() + pausaMs
        ultimoEstadoMalo = cuerpo.estado
      }
      return sinPrediccion(cuerpo.estado, cuerpo.mensaje)
    }

    if (!cuerpo.prediccion) return sinPrediccion('caido')

    // Una respuesta OK borra la pausa: el motor volvio.
    pausadoHasta = 0

    return {
      estado: 'ok',
      prediccion: depurarExplicacion(cuerpo.prediccion as Prediccion),
      medicion: cuerpo.medicion ?? null,
    }
  }

  return { pedir, enPausa, reiniciar: () => { pausadoHasta = 0 } }
}
