/**
 * Pruebas del acuse de alertas (SCRUM-68).
 *
 *     node --test app/clinical/src/lib/alertas.test.ts
 *
 * Lo que se verifica es la diferencia entre posponer y descartar, que es la decisión
 * de fondo del ticket: una alerta pospuesta tiene plazo y vuelve; una resuelta no.
 * Equivocarse acá no rompe nada visible — contamina la métrica de ruido que el
 * proyecto existe para medir.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  construirAcuse,
  etiquetaAccion,
  MINUTOS_POSPONER,
} from './alertas.ts'

const PERFIL = '11111111-1111-1111-1111-111111111111'
const AHORA = new Date('2026-10-14T18:00:00.000Z')

test('validar deja la alerta reconocida y sin plazo', () => {
  const a = construirAcuse('validar', PERFIL, AHORA)
  assert.equal(a.status, 'reconocida')
  assert.equal(a.postponed_until, null)
  assert.equal(a.acknowledged_by, PERFIL)
  assert.equal(a.acknowledged_at, AHORA.toISOString())
})

test('validar limpia el plazo de una alerta que venia pospuesta', () => {
  // Dejar el plazo diria que sigue esperando algo que ya se resolvio.
  assert.equal(construirAcuse('validar', PERFIL, AHORA).postponed_until, null)
})

test('posponer deja plazo futuro, no descarta', () => {
  const a = construirAcuse('posponer', PERFIL, AHORA)
  assert.equal(a.status, 'pospuesta')
  assert.notEqual(a.status, 'descartada')
  assert.ok(a.postponed_until !== null)
  assert.ok(new Date(a.postponed_until!) > AHORA)
})

test('el plazo por defecto son los minutos declarados', () => {
  const a = construirAcuse('posponer', PERFIL, AHORA)
  const minutos = (new Date(a.postponed_until!).getTime() - AHORA.getTime()) / 60_000
  assert.equal(minutos, MINUTOS_POSPONER)
})

test('se puede posponer por otro plazo', () => {
  const a = construirAcuse('posponer', PERFIL, AHORA, 90)
  const minutos = (new Date(a.postponed_until!).getTime() - AHORA.getTime()) / 60_000
  assert.equal(minutos, 90)
})

test('un plazo de cero o negativo se rechaza acá, no en Postgres', () => {
  // La base tiene el CHECK, pero un error de Postgres al pie de una cama no
  // le dice nada a nadie.
  for (const m of [0, -5]) {
    assert.throws(() => construirAcuse('posponer', PERFIL, AHORA, m), /plazo futuro/)
  }
})

test('sin identidad no se acusa', () => {
  // `alerta_resuelta_tiene_firma` lo rechazaria igual; fallar acá da un error legible.
  assert.throws(() => construirAcuse('validar', '', AHORA), /sin identidad/)
})

test('el acuse no toca ningun campo clinico', () => {
  // El trigger `guard_alert_acknowledgement` rechaza el UPDATE entero si llega
  // cualquier otro campo. Esta prueba congela el contrato del lado del cliente.
  const esperadas = ['status', 'acknowledged_by', 'acknowledged_at', 'postponed_until']
  for (const accion of ['validar', 'posponer'] as const) {
    assert.deepEqual(Object.keys(construirAcuse(accion, PERFIL, AHORA)).sort(), [...esperadas].sort())
  }
})

test('el boton dice el plazo, para que posponer no sea una caja negra', () => {
  assert.equal(etiquetaAccion('validar'), 'Validar')
  assert.match(etiquetaAccion('posponer'), /30 min/)
  assert.match(etiquetaAccion('posponer', 90), /90 min/)
})
