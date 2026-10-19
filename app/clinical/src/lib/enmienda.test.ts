/**
 * Pruebas de la enmienda de una toma.
 *
 *     node --test app/clinical/src/lib/enmienda.test.ts
 *
 * Lo que importa: que la corrección conserve el momento de la observación, que no se
 * pueda mandar una enmienda vacía ni sin motivo, y que no se pueda corregir una versión
 * que ya fue corregida. La base también rechaza los dos últimos casos; esto los ataja
 * antes, con un mensaje que la enfermera entiende.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { cambios, construirEnmienda, motivoValido, MOTIVO_MINIMO, type TomaOriginal } from './enmienda.ts'

const AUTOR = '11111111-1111-1111-1111-111111111111'
const NUEVO = '22222222-2222-2222-2222-222222222222'

const ORIGINAL: TomaOriginal = {
  id: '8b0d1c7e-1111-4a2b-9c3d-000000000001',
  encounter_id: 'e0000000-0000-0000-0000-000000000001',
  patient_id: 'p0000000-0000-0000-0000-000000000001',
  recorded_at: '2026-10-19T08:00:00.000Z',
  superseded_by: null,
  respiratory_rate: 8,
  oxygen_saturation: 96,
  supplemental_oxygen: false,
  temperature: 36.8,
  systolic_bp: 125,
  heart_rate: 80,
  consciousness_level: 'A',
}

const { id: _i, encounter_id: _e, patient_id: _p, recorded_at: _r, superseded_by: _s, ...VALORES } =
  ORIGINAL

const MOTIVO = 'Se tipeó 8 en lugar de 18'

test('la enmienda conserva el momento de la observación original', () => {
  const f = construirEnmienda(ORIGINAL, { ...VALORES, respiratory_rate: 18 }, MOTIVO, AUTOR, NUEVO)
  assert.equal(f.recorded_at, ORIGINAL.recorded_at)
  assert.equal(f.amends_id, ORIGINAL.id)
  assert.equal(f.id, NUEVO)
  assert.equal(f.recorded_by, AUTOR)
  assert.equal(f.respiratory_rate, 18)
  assert.equal(f.encounter_id, ORIGINAL.encounter_id)
  assert.equal(f.patient_id, ORIGINAL.patient_id)
})

test('una enmienda sin cambios se rechaza', () => {
  assert.throws(() => construirEnmienda(ORIGINAL, VALORES, MOTIVO, AUTOR, NUEVO), /ningún valor/)
})

test('el motivo exige el mismo mínimo que la base, sin contar los bordes', () => {
  assert.equal(motivoValido('x'.repeat(MOTIVO_MINIMO)), true)
  assert.equal(motivoValido('x'.repeat(MOTIVO_MINIMO - 1)), false)
  assert.equal(motivoValido(`   ${'x'.repeat(MOTIVO_MINIMO - 1)}   `), false)
  assert.throws(
    () => construirEnmienda(ORIGINAL, { ...VALORES, heart_rate: 90 }, 'error', AUTOR, NUEVO),
    /motivo/,
  )
})

test('el motivo viaja sin los espacios de los bordes', () => {
  const f = construirEnmienda(ORIGINAL, { ...VALORES, heart_rate: 90 }, `  ${MOTIVO}  `, AUTOR, NUEVO)
  assert.equal(f.amendment_reason, MOTIVO)
})

test('no se corrige una versión que ya fue corregida', () => {
  assert.throws(
    () =>
      construirEnmienda({ ...ORIGINAL, superseded_by: NUEVO }, { ...VALORES, heart_rate: 90 }, MOTIVO, AUTOR, NUEVO),
    /versión vigente/,
  )
})

test('no se firma una enmienda sin autor', () => {
  assert.throws(() => construirEnmienda(ORIGINAL, { ...VALORES, heart_rate: 90 }, MOTIVO, '', NUEVO), /autor/)
})

test('los cambios salen en el orden del formulario y legibles', () => {
  const c = cambios(VALORES, {
    ...VALORES,
    consciousness_level: 'C',
    respiratory_rate: 18,
    supplemental_oxygen: true,
  })
  assert.deepEqual(c, [
    { etiqueta: 'Frecuencia respiratoria', antes: '8 rpm', despues: '18 rpm' },
    { etiqueta: 'Oxígeno suplementario', antes: 'Aire ambiente', despues: 'Con oxígeno' },
    { etiqueta: 'Consciencia (ACVPU)', antes: 'Alerta', despues: 'Confusión nueva' },
  ])
})
