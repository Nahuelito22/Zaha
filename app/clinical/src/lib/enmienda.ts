import { OPCIONES_ACVPU, RANGOS, type ACVPU, type CampoNumerico } from './tipos.ts'

/**
 * Enmienda de una toma (corrección de un dato mal cargado).
 *
 * `vital_records` es append-only: corregir es INSERTAR una fila nueva que apunta a la
 * errónea (`amends_id`) y dice por qué (`amendment_reason`). Del lado de la base, el
 * trigger `apply_amendment` sella la vieja y cierra su alerta pendiente; eso no se hace
 * acá. Este módulo sólo arma el INSERT y decide si tiene sentido mandarlo.
 *
 * Es lógica pura, sin red ni React, para poder probarla con `node --test`.
 */

/** El mismo mínimo que el CHECK `enmienda_requiere_motivo` de la base. */
export const MOTIVO_MINIMO = 10

/** Los 7 parámetros tal como se cargan. */
export type ValoresToma = {
  respiratory_rate: number
  oxygen_saturation: number
  supplemental_oxygen: boolean
  temperature: number
  systolic_bp: number
  heart_rate: number
  consciousness_level: ACVPU
}

/** Lo que hace falta de la toma que se corrige. */
export type TomaOriginal = ValoresToma & {
  id: string
  encounter_id: string
  patient_id: string
  recorded_at: string
  superseded_by: string | null
}

export type Cambio = { etiqueta: string; antes: string; despues: string }

function legible(campo: keyof ValoresToma, v: ValoresToma): string {
  if (campo === 'supplemental_oxygen') return v.supplemental_oxygen ? 'Con oxígeno' : 'Aire ambiente'
  if (campo === 'consciousness_level') {
    return OPCIONES_ACVPU.find((o) => o.valor === v.consciousness_level)?.texto ?? v.consciousness_level
  }
  return `${v[campo]} ${RANGOS[campo as CampoNumerico].unidad}`
}

const ORDEN: Array<{ campo: keyof ValoresToma; etiqueta: string }> = [
  ...(Object.keys(RANGOS) as CampoNumerico[]).map((c) => ({ campo: c, etiqueta: RANGOS[c].etiqueta })),
  { campo: 'supplemental_oxygen', etiqueta: 'Oxígeno suplementario' },
  { campo: 'consciousness_level', etiqueta: 'Consciencia (ACVPU)' },
]

/**
 * Qué cambia entre la toma errónea y la corregida, en el orden del formulario.
 *
 * Es lo que muestra la confirmación: "antes → después" convierte el paso en una
 * relectura de la corrección, igual que el resumen de la carga.
 */
export function cambios(original: ValoresToma, corregida: ValoresToma): Cambio[] {
  return ORDEN.filter(({ campo }) => original[campo] !== corregida[campo]).map(
    ({ campo, etiqueta }) => ({
      etiqueta,
      antes: legible(campo, original),
      despues: legible(campo, corregida),
    }),
  )
}

/**
 * El motivo cuenta sin los espacios de los bordes, como en la base. Acá `trim` quita
 * también saltos de línea, así que es un poco más estricto que el CHECK: nunca deja
 * pasar algo que la base vaya a rechazar.
 */
export function motivoValido(motivo: string): boolean {
  return motivo.trim().length >= MOTIVO_MINIMO
}

/**
 * Arma la fila de la enmienda.
 *
 * - **`recorded_at` es el de la toma original**, no el de ahora: la enmienda corrige
 *   esa observación, no registra una nueva. Con la hora de ahora, la corrección
 *   pasaría a ser "la última toma" del paciente aunque se haya hecho tres días después.
 * - El `id` se genera en el cliente por la misma razón que en la cola: un reintento
 *   después de un timeout choca contra la PK en vez de insertar una segunda enmienda.
 * - Se niega a enmendar sin cambios: una "corrección" idéntica sólo cerraría la
 *   alerta de la toma vieja con un motivo, que es descartar una alerta por la puerta
 *   de atrás.
 */
export function construirEnmienda(
  original: TomaOriginal,
  corregida: ValoresToma,
  motivo: string,
  autor: string,
  id: string,
) {
  if (!autor) throw new Error('una enmienda sin autor no se puede firmar')
  if (original.superseded_by !== null) {
    throw new Error('esa toma ya fue corregida: hay que corregir la versión vigente')
  }
  if (cambios(original, corregida).length === 0) {
    throw new Error('la corrección no cambia ningún valor')
  }
  if (!motivoValido(motivo)) {
    throw new Error(`el motivo tiene que tener al menos ${MOTIVO_MINIMO} caracteres`)
  }

  return {
    id,
    amends_id: original.id,
    amendment_reason: motivo.trim(),
    encounter_id: original.encounter_id,
    patient_id: original.patient_id,
    recorded_by: autor,
    recorded_at: original.recorded_at,
    ...corregida,
  }
}
