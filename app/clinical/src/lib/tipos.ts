export type Rol = 'enfermero' | 'medico' | 'jefe'

export type NivelRiesgo = 'Bajo' | 'Medio Bajo' | 'Medio' | 'Alto'

export type ACVPU = 'A' | 'C' | 'V' | 'P' | 'U'

export type Perfil = {
  id: string
  full_name: string
  role: Rol
  license_id: string | null
  active: boolean
}

/** Sufijo de las clases del sistema de diseño para cada nivel. */
export const CLASE_RIESGO: Record<NivelRiesgo, string> = {
  Bajo: 'low',
  'Medio Bajo': 'lowmed',
  Medio: 'med',
  Alto: 'high',
}

/** Orden clínico: lo urgente primero. Nunca alfabético ni por número de cama. */
export const PESO_RIESGO: Record<NivelRiesgo, number> = {
  Alto: 0,
  Medio: 1,
  'Medio Bajo': 2,
  Bajo: 3,
}

/**
 * Peso de una cama SIN score vigente.
 *
 * Antes se la trataba como 'Bajo', lo cual afirma algo que no se sabe: una
 * cama sin medición no es una cama de riesgo bajo, es una cama sin medir. Va
 * al final de la lista igual que antes —no se inventa una urgencia que nadie
 * validó clínicamente— pero como categoría propia y explícita, y en la sala se
 * dibuja con `.score-incomplete`, no con el borde verde de riesgo bajo.
 *
 * Dónde ordenarla de verdad es una decisión clínica, no de código: queda para
 * la validación con enfermería (SCRUM-46).
 */
export const PESO_SIN_SCORE = 4

export const ROL_LEGIBLE: Record<Rol, string> = {
  enfermero: 'Enfermería',
  medico: 'Medicina',
  jefe: 'Jefatura',
}

/**
 * Las 5 opciones de ACVPU con su significado escrito.
 *
 * La C es "new confusion" y puntúa 3, igual que V, P y U. La escala AVDI que
 * se usa habitualmente no la tiene, y omitirla hace que un paciente con
 * confusión nueva puntúe 0 y quede clasificado como riesgo bajo. Por eso acá
 * la etiqueta es explícita y no una sigla suelta.
 */
export const OPCIONES_ACVPU: Array<{ valor: ACVPU; sigla: string; texto: string }> = [
  { valor: 'A', sigla: 'A', texto: 'Alerta' },
  { valor: 'C', sigla: 'C', texto: 'Confusión nueva' },
  { valor: 'V', sigla: 'V', texto: 'Responde a la voz' },
  { valor: 'P', sigla: 'P', texto: 'Responde al dolor' },
  { valor: 'U', sigla: 'U', texto: 'Sin respuesta' },
]

/**
 * Rangos de plausibilidad fisiológica.
 *
 * Son los MISMOS que los CHECK de la base (migración 20260521000000). Se
 * repiten en el cliente para avisar antes del viaje al servidor, no para
 * reemplazar la validación: la base sigue siendo la autoridad. Si alguna vez
 * divergen, manda la base — el cliente es una cortesía, no una garantía.
 *
 * OJO: fuera de rango es un ERROR DE CARGA, no un nivel clínico. Se marca con
 * forma y texto, nunca con el rojo de alerta, que está reservado al riesgo.
 */
export const RANGOS = {
  respiratory_rate: { min: 0, max: 80, unidad: 'rpm', etiqueta: 'Frecuencia respiratoria' },
  oxygen_saturation: { min: 50, max: 100, unidad: '%', etiqueta: 'Saturación de oxígeno' },
  temperature: { min: 25, max: 45, unidad: '°C', etiqueta: 'Temperatura' },
  systolic_bp: { min: 30, max: 300, unidad: 'mmHg', etiqueta: 'Presión sistólica' },
  heart_rate: { min: 0, max: 300, unidad: 'lpm', etiqueta: 'Frecuencia cardíaca' },
} as const

export type CampoNumerico = keyof typeof RANGOS
