/**
 * Cableado del servicio de predicción con el cliente real (SCRUM-65).
 *
 * Esto es lo único de la predicción que importa `./supabase`, y por eso no se puede
 * probar fuera de Vite. A propósito no tiene ninguna decisión: toda la lógica de
 * degradación —qué pasa si el motor duerme, el cortacircuito, qué se muestra y qué no—
 * vive en `prediccion.ts`, que sí tiene pruebas.
 *
 * Si algo de este archivo crece más allá de pasar argumentos, va para el otro lado.
 */

import { supabase } from './supabase'
import { crearServicioPrediccion, type Invocador } from './prediccion'

const invocar: Invocador = async (nombre, cuerpo) => {
  // `functions.invoke` adjunta sola la cabecera Authorization con el JWT de la sesión
  // activa, que es lo que la Edge Function necesita para consultar la base con RLS.
  const { data, error } = await supabase.functions.invoke(nombre, { body: cuerpo })
  return { data, error }
}

export const servicioPrediccion = crearServicioPrediccion(invocar)
