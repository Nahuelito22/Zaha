/**
 * Pruebas de la degradación elegante (SCRUM-65).
 *
 *     node --test app/clinical/src/lib/prediccion.test.ts
 *
 * Lo que se verifica es la obligación dura del módulo: **nada de acá lanza**. El ADR-004
 * dice que el NEWS2 determinístico nunca depende de la API de IA, y la forma concreta de
 * romper esa regla no es un `if` mal puesto — es una excepción que escapa y deja la sala
 * en blanco porque un Space gratuito se durmió.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  crearServicioPrediccion,
  depurarExplicacion,
  PAUSA_TRAS_FALLO_MS,
  type Prediccion,
  type RespuestaDeLaFuncion,
} from './prediccion.ts'

const PREDICCION: Prediccion = {
  probabilidad: 0.971055,
  alerta: true,
  es_estimacion: true,
  punto_de_operacion: {
    sensibilidad_objetivo: 0.7,
    umbral: 0.224004,
    tasa_de_alertas_esperada: 0.3038,
    elegido_por: 'valor_por_defecto',
  },
  explicacion: {
    exacta: true,
    intercepto: -0.5887,
    logit: 3.5,
    probabilidad_reconstruida: 0.971055,
    reconstruye_la_probabilidad: true,
    contribuciones: [
      { parametro: 'confusion', valor: 1, contribucion: 1.066, direccion: 'aumenta' },
    ],
  },
  advertencia: 'La reduccion de alertas contra NEWS2 NO esta demostrada',
}

function respuesta(cuerpo: Partial<RespuestaDeLaFuncion>) {
  return async () => ({
    data: { estado: 'ok', prediccion: PREDICCION, mensaje: '', ...cuerpo },
    error: null,
  })
}

/** Reloj controlado: las pruebas del cortacircuito no pueden depender del tiempo real. */
function reloj(inicio = 1_000_000) {
  let t = inicio
  return { ahora: () => t, avanzar: (ms: number) => (t += ms) }
}

// -- el camino feliz -------------------------------------------------------------------

test('una respuesta ok devuelve la predicción y la medición usada', async () => {
  const servicio = crearServicioPrediccion(
    respuesta({ medicion: { id: 'abc', recorded_at: '2026-10-13T14:30:00Z' } }),
  )
  const r = await servicio.pedir('paciente-1')

  if (r.estado !== 'ok') throw new Error(`esperaba ok, vino ${r.estado}`)
  assert.equal(r.prediccion.probabilidad, 0.971055)
  assert.equal(r.medicion?.id, 'abc')
})

test('la sensibilidad elegida viaja a la función', async () => {
  let recibido: Record<string, unknown> | null = null
  const servicio = crearServicioPrediccion(async (_n, cuerpo) => {
    recibido = cuerpo
    return { data: { estado: 'ok', prediccion: PREDICCION, mensaje: '' }, error: null }
  })

  await servicio.pedir('paciente-1', { sensibilidadObjetivo: 0.8 })
  assert.equal(recibido!.sensibilidad_objetivo, 0.8)
  assert.equal(recibido!.patient_id, 'paciente-1')
})

test('sin sensibilidad explícita no se manda el campo', async () => {
  let recibido: Record<string, unknown> | null = null
  const servicio = crearServicioPrediccion(async (_n, cuerpo) => {
    recibido = cuerpo
    return { data: { estado: 'ok', prediccion: PREDICCION, mensaje: '' }, error: null }
  })

  await servicio.pedir('paciente-1')
  assert.ok(!('sensibilidad_objetivo' in recibido!))
})

// -- la obligación dura: nunca lanzar ---------------------------------------------------

test('si el invocador lanza, no se propaga', async () => {
  const servicio = crearServicioPrediccion(async () => {
    throw new Error('fetch failed')
  })

  const r = await servicio.pedir('paciente-1')
  assert.equal(r.estado, 'caido')
  assert.equal(r.prediccion, null)
})

test('un cuerpo basura no rompe nada', async () => {
  for (const data of [null, undefined, 'texto', 42, {}, { estado: 7 }]) {
    const servicio = crearServicioPrediccion(async () => ({ data, error: null }))
    const r = await servicio.pedir('paciente-1')
    // Alcanza con esto: `assert.equal` esta tipada como `asserts`, asi que si pasa, el
    // compilador ya descarto la rama 'ok' --que es la unica con prediccion.
    assert.equal(r.prediccion, null, `${JSON.stringify(data)} no deberia dar prediccion`)
  }
})

test('un estado ok sin predicción no se toma por bueno', async () => {
  const servicio = crearServicioPrediccion(async () => ({
    data: { estado: 'ok', prediccion: null, mensaje: '' },
    error: null,
  }))
  const r = await servicio.pedir('paciente-1')
  assert.equal(r.estado, 'caido')
})

// -- los mensajes no comprometen a NEWS2 -------------------------------------------------

test('dormido y caído aclaran que NEWS2 no depende del motor', async () => {
  for (const estado of ['dormido', 'caido'] as const) {
    const servicio = crearServicioPrediccion(
      respuesta({ estado, prediccion: null, mensaje: '' }),
    )
    const r = await servicio.pedir('paciente-1')
    if (r.estado === 'ok') throw new Error('no deberia haber estimacion')
    assert.equal(r.estado, estado)
    assert.match(r.mensaje, /NEWS2 no depende/)
  }
})

test('sin tomas es del paciente, no del motor', async () => {
  const servicio = crearServicioPrediccion(
    respuesta({ estado: 'sin_tomas', prediccion: null, mensaje: '' }),
  )
  const r = await servicio.pedir('paciente-1')
  assert.equal(r.estado, 'sin_tomas')
})

test('un 401 se reporta como sin sesión y no como motor caído', async () => {
  const servicio = crearServicioPrediccion(async () => ({
    data: null,
    error: { message: 'Edge Function returned a non-2xx status code: 401' },
  }))
  const r = await servicio.pedir('paciente-1')
  assert.equal(r.estado, 'sin_sesion')
})

// -- el cortacircuito ---------------------------------------------------------------------

test('tras un fallo deja de preguntar, para no colgar la sala entera', async () => {
  const t = reloj()
  let llamadas = 0
  const servicio = crearServicioPrediccion(
    async () => {
      llamadas += 1
      return { data: { estado: 'dormido', prediccion: null, mensaje: '' }, error: null }
    },
    t.ahora,
  )

  await servicio.pedir('cama-1')
  // Veinte camas mas en el tablero: ninguna tendria que volver a salir a la red.
  for (let i = 2; i <= 21; i++) await servicio.pedir(`cama-${i}`)

  assert.equal(llamadas, 1)
  assert.ok(servicio.enPausa())
})

test('en pausa conserva el último estado conocido', async () => {
  const t = reloj()
  const servicio = crearServicioPrediccion(
    respuesta({ estado: 'dormido', prediccion: null, mensaje: '' }),
    t.ahora,
  )
  await servicio.pedir('cama-1')
  const segundo = await servicio.pedir('cama-2')
  assert.equal(segundo.estado, 'dormido')
})

test('la pausa vence y se vuelve a intentar', async () => {
  const t = reloj()
  let llamadas = 0
  const servicio = crearServicioPrediccion(
    async () => {
      llamadas += 1
      return { data: { estado: 'dormido', prediccion: null, mensaje: '' }, error: null }
    },
    t.ahora,
  )

  await servicio.pedir('cama-1')
  t.avanzar(PAUSA_TRAS_FALLO_MS + 1)
  await servicio.pedir('cama-1')

  assert.equal(llamadas, 2)
})

test('sin tomas NO pausa: es del paciente, no del motor', async () => {
  const t = reloj()
  let llamadas = 0
  const servicio = crearServicioPrediccion(
    async () => {
      llamadas += 1
      return { data: { estado: 'sin_tomas', prediccion: null, mensaje: '' }, error: null }
    },
    t.ahora,
  )

  // Una cama recien ocupada no puede dejar sin estimacion al resto de la sala.
  await servicio.pedir('cama-1')
  await servicio.pedir('cama-2')
  assert.equal(llamadas, 2)
  assert.ok(!servicio.enPausa())
})

test('una respuesta buena levanta la pausa', async () => {
  const t = reloj()
  let falla = true
  const servicio = crearServicioPrediccion(
    async () =>
      falla
        ? { data: { estado: 'dormido', prediccion: null, mensaje: '' }, error: null }
        : { data: { estado: 'ok', prediccion: PREDICCION, mensaje: '' }, error: null },
    t.ahora,
  )

  await servicio.pedir('cama-1')
  assert.ok(servicio.enPausa())

  falla = false
  t.avanzar(PAUSA_TRAS_FALLO_MS + 1)
  await servicio.pedir('cama-1')

  assert.ok(!servicio.enPausa())
})

// -- la explicación que no se sostiene no se muestra -----------------------------------------

test('se descarta una explicación que no reconstruye la probabilidad', () => {
  const rota: Prediccion = {
    ...PREDICCION,
    explicacion: { ...PREDICCION.explicacion!, reconstruye_la_probabilidad: false },
  }
  const depurada = depurarExplicacion(rota)

  // La probabilidad se conserva; lo que se tira es la explicacion equivocada.
  assert.equal(depurada.explicacion, null)
  assert.equal(depurada.probabilidad, PREDICCION.probabilidad)
})

test('una explicación consistente se conserva entera', () => {
  assert.deepEqual(depurarExplicacion(PREDICCION).explicacion, PREDICCION.explicacion)
})

test('la predicción que llega por el servicio ya viene depurada', async () => {
  const rota: Prediccion = {
    ...PREDICCION,
    explicacion: { ...PREDICCION.explicacion!, reconstruye_la_probabilidad: false },
  }
  const servicio = crearServicioPrediccion(respuesta({ prediccion: rota }))
  const r = await servicio.pedir('paciente-1')

  if (r.estado !== 'ok') throw new Error(`esperaba ok, vino ${r.estado}`)
  assert.equal(r.prediccion.explicacion, null)
})
