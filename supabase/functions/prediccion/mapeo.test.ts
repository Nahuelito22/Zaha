/**
 * Pruebas del mapeo base → motor de IA (SCRUM-64).
 *
 *     node --test supabase/functions/prediccion/mapeo.test.ts
 *
 * Node 24 ejecuta TypeScript directamente, así que esto no necesita Deno ni compilación.
 * Lo que se prueba es la parte que puede equivocarse en silencio: si un parámetro se
 * mapea al casillero de al lado, la API devuelve una probabilidad perfectamente plausible
 * —de otro paciente— y nada falla.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  aConfusion,
  aObservacion,
  edadEnLaToma,
  estadoSegunRespuesta,
  explicarEstado,
  type TomaDeLaBase,
} from "./mapeo.ts";

const TOMA: TomaDeLaBase = {
  id: "11111111-1111-1111-1111-111111111111",
  recorded_at: "2026-10-13T14:30:00Z",
  respiratory_rate: 26,
  oxygen_saturation: 91,
  temperature: 38.4,
  systolic_bp: 96,
  heart_rate: 122,
  consciousness_level: "A",
};

const NACIMIENTO = "1945-03-20";

test("cada parámetro cae en su casillero y ninguno se corre", () => {
  const o = aObservacion(TOMA, NACIMIENTO);
  assert.equal(o.frecuencia_respiratoria, 26);
  assert.equal(o.spo2, 91);
  assert.equal(o.temperatura, 38.4);
  assert.equal(o.presion_sistolica, 96);
  assert.equal(o.frecuencia_cardiaca, 122);
});

test("la observación lleva exactamente las siete claves que la API espera", () => {
  const esperadas = [
    "frecuencia_respiratoria",
    "spo2",
    "temperatura",
    "presion_sistolica",
    "frecuencia_cardiaca",
    "confusion",
    "edad",
  ].sort();
  assert.deepEqual(Object.keys(aObservacion(TOMA, NACIMIENTO)).sort(), esperadas);
});

test("ningún parámetro distinto comparte valor, así que un cruce se vería", () => {
  // Si dos campos tuvieran el mismo numero, un mapeo cruzado pasaria desapercibido.
  const o = aObservacion(TOMA, NACIMIENTO);
  const valores = [
    o.frecuencia_respiratoria,
    o.spo2,
    o.temperatura,
    o.presion_sistolica,
    o.frecuencia_cardiaca,
  ];
  assert.equal(new Set(valores).size, valores.length);
});

// -- la decisión clínica del archivo --------------------------------------------------

test("sólo 'A' cuenta como sin confusión", () => {
  assert.equal(aConfusion("A"), 0);
});

test("V, P y U cuentan como confusión, no como alerta", () => {
  // Es el error en la direccion peligrosa: mapear un paciente que no responde a
  // `confusion = 0` le diria al modelo que esta alerta.
  for (const nivel of ["C", "V", "P", "U"] as const) {
    assert.equal(aConfusion(nivel), 1, `${nivel} tendria que contar como confusion`);
  }
});

// -- la edad ---------------------------------------------------------------------------

test("la edad se calcula a la fecha de la toma, no a la de hoy", () => {
  // La misma observacion tiene que dar siempre lo mismo, se consulte cuando se consulte.
  const viejo = edadEnLaToma(NACIMIENTO, "2020-01-01T00:00:00Z");
  const nuevo = edadEnLaToma(NACIMIENTO, "2026-10-13T14:30:00Z");
  assert.equal(viejo, 74);
  assert.equal(nuevo, 81);
});

test("el cumpleaños todavía no cumplido resta un año", () => {
  assert.equal(edadEnLaToma("1945-03-20", "2026-03-19T23:00:00Z"), 80);
  assert.equal(edadEnLaToma("1945-03-20", "2026-03-20T01:00:00Z"), 81);
});

test("una fecha inválida falla en vez de devolver NaN", () => {
  assert.throws(() => edadEnLaToma("no-es-fecha", TOMA.recorded_at));
});

// -- degradación -----------------------------------------------------------------------

test("un Space despertando es 'dormido', no un error", () => {
  assert.equal(estadoSegunRespuesta(503), "dormido");
  assert.equal(estadoSegunRespuesta(504), "dormido");
});

test("200 es ok y el resto es caído", () => {
  assert.equal(estadoSegunRespuesta(200), "ok");
  assert.equal(estadoSegunRespuesta(401), "caido");
  assert.equal(estadoSegunRespuesta(500), "caido");
});

test("ningún mensaje de degradación sugiere que NEWS2 esté comprometido", () => {
  for (const estado of ["dormido", "caido"] as const) {
    const mensaje = explicarEstado(estado);
    assert.match(mensaje, /NEWS2 no depende/);
  }
});

test("el estado ok no deja mensaje", () => {
  assert.equal(explicarEstado("ok"), "");
});
