import Dexie, { type Table } from 'dexie'
import { supabase } from './supabase'
import type { ACVPU, NivelRiesgo } from './tipos'

/**
 * Cola de escritura offline (SCRUM-44 / HU-01).
 *
 * El problema no es "guardar cuando no hay señal": eso lo resuelve cualquier
 * buffer. El problema es que `vital_records` es APPEND-ONLY y el score lo
 * calcula un trigger del servidor. Eso impone tres cosas que definen todo el
 * diseño de este archivo:
 *
 * 1. Un reintento no puede duplicar. Si la red se corta DESPUÉS de que el
 *    INSERT se confirmó pero ANTES de que llegue la respuesta, el cliente no
 *    distingue "no llegó" de "llegó y no me enteré". Reintentar a ciegas
 *    inserta una segunda observación con su propio score y su propia alerta,
 *    y no se puede borrar: la tabla no tiene DELETE. Por eso el `id` se genera
 *    en el cliente y viaja en el INSERT. En el reintento, Postgres rechaza el
 *    duplicado con 23505 y eso es la CONFIRMACIÓN de que la primera vez sí
 *    entró. El error es el acuse de recibo.
 *
 * 2. Offline no hay puntaje. Calcular NEWS2 acá daría dos motores que pueden
 *    divergir, y el que vale legalmente es el de la base (mismo razonamiento
 *    que en CargarVitales). Una toma encolada se muestra SIN score, dicho de
 *    frente, hasta que el servidor la puntúe.
 *
 * 3. La política RLS exige `recorded_by = auth.uid()`. La cola es por usuario:
 *    lo que encoló una enfermera no lo puede sincronizar otra, porque la firma
 *    del registro no se delega.
 */

/** Toma capturada localmente, todavía no confirmada por el servidor. */
export type TomaEnCola = {
  /**
   * UUID generado en el cliente. Es la clave de idempotencia: se manda en el
   * INSERT para que un reintento choque contra la PK en vez de duplicar.
   */
  id: string

  // --- Payload que va a vital_records ---------------------------------------
  encounter_id: string
  patient_id: string
  recorded_by: string
  /**
   * Momento de la OBSERVACIÓN, sellado al capturar. No se puede delegar en el
   * DEFAULT NOW() de la tabla: una toma cargada a las 08:00 y sincronizada a
   * las 14:00 quedaría registrada a las 14:00, y las ventanas temporales del
   * modelo (y el relato clínico) pasarían a ser falsos.
   */
  recorded_at: string
  respiratory_rate: number
  oxygen_saturation: number
  supplemental_oxygen: boolean
  temperature: number
  systolic_bp: number
  heart_rate: number
  consciousness_level: ACVPU

  // --- Metadatos locales ----------------------------------------------------
  estado: 'pendiente' | 'rechazado'
  intentos: number
  ultimo_error: string | null
  encolada_en: string

  /**
   * Copia del nombre y la cama al momento de encolar. Sin red no se puede
   * resolver el join contra `patients`, y una cola que dice "3 tomas
   * pendientes" sin decir de quién no sirve para nada al pie de la cama.
   */
  paciente: string
  cama: string | null
}

class BaseLocal extends Dexie {
  tomas!: Table<TomaEnCola, string>

  constructor() {
    super('zaha_offline')
    // `estado` y `recorded_by` se indexan porque son el filtro de toda
    // consulta: "lo pendiente de ESTE usuario", en orden cronológico.
    this.version(1).stores({
      tomas: 'id, estado, recorded_by, encounter_id, recorded_at',
    })
  }
}

export const baseLocal = new BaseLocal()

/**
 * Errores de Postgres que NO se arreglan reintentando: el dato es inválido
 * contra el esquema y lo va a seguir siendo dentro de una hora. Reintentarlos
 * en loop esconde el problema justo cuando hay que mostrarlo.
 */
const CODIGOS_PERMANENTES = new Set([
  '23514', // check_violation — rango fisiológico, o recorded_at en el futuro
  '23503', // foreign_key_violation — el episodio ya no existe
  '23502', // not_null_violation
  '22003', // numeric_value_out_of_range
  '22007', // invalid_datetime_format
  '22P02', // invalid_text_representation
])

/** Confirmación que devuelve el servidor cuando la toma efectivamente entró. */
export type Puntaje = {
  news2_score: number
  risk_level: NivelRiesgo
  single_red_flag: boolean
}

export type ResultadoEnvio =
  | { tipo: 'confirmada'; puntaje: Puntaje }
  /** Ya estaba en el servidor (23505). La primera vez sí había entrado. */
  | { tipo: 'ya_estaba' }
  /** No se pudo llegar al servidor. Queda pendiente, sin tocar. */
  | { tipo: 'sin_red' }
  /** El servidor la rechazó por un motivo que no se arregla reintentando. */
  | { tipo: 'rechazada'; motivo: string }
  /** Falta permiso (RLS) o la sesión no sirve. Queda pendiente. */
  | { tipo: 'sin_permiso'; motivo: string }

/** Guarda la toma en IndexedDB. Devuelve recién cuando está en disco. */
export async function encolar(toma: TomaEnCola): Promise<void> {
  await baseLocal.tomas.put(toma)
}

/**
 * Intenta subir UNA toma.
 *
 * El orden importa: primero se persiste local (`encolar`), después se intenta
 * la red. Al revés, un corte de luz entre el submit y la respuesta perdería la
 * observación sin dejar rastro.
 */
export async function enviarUna(toma: TomaEnCola): Promise<ResultadoEnvio> {
  const { data, error } = await supabase
    .from('vital_records')
    .insert({
      id: toma.id,
      encounter_id: toma.encounter_id,
      patient_id: toma.patient_id,
      recorded_by: toma.recorded_by,
      recorded_at: toma.recorded_at,
      respiratory_rate: toma.respiratory_rate,
      oxygen_saturation: toma.oxygen_saturation,
      supplemental_oxygen: toma.supplemental_oxygen,
      temperature: toma.temperature,
      systolic_bp: toma.systolic_bp,
      heart_rate: toma.heart_rate,
      consciousness_level: toma.consciousness_level,
    })
    .select('news2_score, risk_level, single_red_flag')
    .single()

  if (!error) {
    await baseLocal.tomas.delete(toma.id)
    return { tipo: 'confirmada', puntaje: data as Puntaje }
  }

  // 23505 sobre la PK: esta misma toma ya está en el servidor. Es el caso que
  // justifica todo el diseño — el reintento después de un timeout ambiguo.
  if (error.code === '23505') {
    await baseLocal.tomas.delete(toma.id)
    return { tipo: 'ya_estaba' }
  }

  if (error.code === '42501') {
    // RLS. Puede volverse válido si jefatura activa el perfil o si se vuelve
    // a iniciar sesión, así que la toma NO se descarta.
    await marcarIntento(toma, error.message)
    return { tipo: 'sin_permiso', motivo: error.message }
  }

  if (error.code && CODIGOS_PERMANENTES.has(error.code)) {
    await baseLocal.tomas.update(toma.id, {
      estado: 'rechazado',
      intentos: toma.intentos + 1,
      ultimo_error: error.message,
    })
    return { tipo: 'rechazada', motivo: error.message }
  }

  // Sin `code` es, casi siempre, que el fetch no llegó a destino. Se deja
  // pendiente: no sabemos nada del servidor, así que no asumimos nada.
  await marcarIntento(toma, error.message)
  return { tipo: 'sin_red' }
}

async function marcarIntento(toma: TomaEnCola, mensaje: string): Promise<void> {
  await baseLocal.tomas.update(toma.id, {
    intentos: toma.intentos + 1,
    ultimo_error: mensaje,
  })
}

export type ResumenSincronizacion = {
  confirmadas: number
  yaEstaban: number
  rechazadas: number
  pendientes: number
}

/**
 * Cerrojo de módulo. Dos corridas simultáneas (por ejemplo el evento `online`
 * y el botón manual a la vez) mandarían la misma fila dos veces. La segunda
 * chocaría contra 23505 y no duplicaría nada, pero igual es ruido evitable.
 */
let corriendo = false

/**
 * Vacía la cola del usuario dado, en orden cronológico.
 *
 * Se corta en el primer problema de red o de permisos: si el servidor no está,
 * insistir con las 20 siguientes solo suma latencia y ruido. Los rechazos
 * permanentes NO cortan: son de esa fila sola y el resto puede entrar.
 */
export async function sincronizar(userId: string): Promise<ResumenSincronizacion> {
  const vacio = { confirmadas: 0, yaEstaban: 0, rechazadas: 0, pendientes: 0 }
  if (corriendo) return { ...vacio, pendientes: await contarPendientes(userId) }
  corriendo = true

  try {
    const pendientes = await baseLocal.tomas
      .where('recorded_by')
      .equals(userId)
      .filter((t) => t.estado === 'pendiente')
      .sortBy('recorded_at')

    const resumen = { ...vacio }

    for (const toma of pendientes) {
      const r = await enviarUna(toma)
      if (r.tipo === 'confirmada') resumen.confirmadas++
      else if (r.tipo === 'ya_estaba') resumen.yaEstaban++
      else if (r.tipo === 'rechazada') resumen.rechazadas++
      else break // sin_red o sin_permiso: cortar la corrida entera
    }

    resumen.pendientes = await contarPendientes(userId)
    return resumen
  } finally {
    corriendo = false
  }
}

export function contarPendientes(userId: string): Promise<number> {
  return baseLocal.tomas
    .where('recorded_by')
    .equals(userId)
    .filter((t) => t.estado === 'pendiente')
    .count()
}

/**
 * Descarta una toma rechazada. Es la única salida para una fila que el
 * servidor nunca va a aceptar (por ejemplo, un episodio dado de alta mientras
 * el dispositivo estaba sin señal). Solo se permite sobre `rechazado`: una
 * pendiente todavía puede entrar y borrarla sería perder una observación.
 */
export async function descartarRechazada(id: string): Promise<void> {
  const toma = await baseLocal.tomas.get(id)
  if (toma?.estado === 'rechazado') await baseLocal.tomas.delete(id)
}
