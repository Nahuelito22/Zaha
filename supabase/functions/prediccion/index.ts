/**
 * Edge Function: estimación de deterioro para un paciente (SCRUM-64).
 *
 * EL PUENTE ENTRE LA APLICACIÓN Y EL MOTOR, Y POR QUÉ HACE FALTA
 * El Space de Hugging Face es **privado**: sólo se llega con un token de escritura de la
 * cuenta Zaha-CDSS. Ese token no puede vivir en el navegador —publicarlo sería regalar el
 * acceso—, así que la aplicación clínica no llama al motor: llama acá, y esta función,
 * que corre del lado del servidor, es la única que tiene el token.
 *
 * LO QUE ESTA FUNCIÓN NO HACE
 * - **No calcula NEWS2.** La escala la calcula un trigger de la base y no depende de nada
 *   de esto (ADR-004). Si el motor está dormido o caído, la respuesta lo declara y la
 *   aplicación sigue mostrando la escala.
 * - **No usa la service_role key.** Consulta la base con el JWT de quien llama, así que
 *   las políticas RLS se aplican igual que en el navegador. Si no fuera así, esta función
 *   sería un agujero para leer la historia clínica de cualquier paciente.
 * - **No inventa una predicción.** Si el motor no contesta, no hay número.
 *
 * SOBRE EL "HISTORIAL" DEL TÍTULO DEL ISSUE
 * SCRUM-64 se escribió cuando la planificación daba por hecho un modelo temporal. El
 * modelo que quedó desplegado es de corte transversal: se entrenó con una fila por
 * paciente y la API acepta **una** observación. Mandarle el historial no tendría dónde
 * entrar. Así que se manda la última toma vigente, y la parte temporal sigue colgando de
 * SCRUM-57, que depende de datos que todavía no tenemos.
 *
 * Secretos que necesita:
 *   ZAHA_API_URL    https://zaha-cdss-inferencia.hf.space/api
 *   ZAHA_API_TOKEN  token de Hugging Face con acceso de LECTURA al Space privado
 *
 * **El `/api` del final no es opcional.** La API vive montada bajo `/api` dentro del
 * servidor de Gradio del Space, porque ZeroGPU obliga a que el servidor lo levante Gradio
 * (ver `deploy/hf_space/app.py`). Sin ese sufijo, el `fetch` de más abajo pediría
 * `/prediccion` en la raíz y recibiría la pantalla de demostración en HTML en vez de JSON.
 */

import { createClient } from "jsr:@supabase/supabase-js@2";

import {
  aObservacion,
  estadoSegunRespuesta,
  explicarEstado,
  type Estado,
  type TomaDeLaBase,
} from "./mapeo.ts";

// Un Space dormido tarda decenas de segundos en despertar. No se espera: se contesta
// "dormido" y se deja que el proximo pedido lo encuentre despierto. Una pantalla de
// triage que se cuelga 40 s es peor que una sin estimacion.
const TIEMPO_LIMITE_MS = 8_000;

// LA LISTA DE CABECERAS PERMITIDAS TIENE QUE INCLUIR LAS QUE MANDA supabase-js.
// Costo encontrarlo corriendo la app: decia solo "authorization, content-type", y
// `functions.invoke` manda ademas `apikey` y `x-client-info`. El preflight respondia
// 200, el navegador bloqueaba el POST por una cabecera no autorizada, y en los registros
// de la funcion se veian OPTIONS y NINGUN POST. Del lado del cliente no habia error
// visible: la degradacion elegante lo convertia en "el motor no esta disponible".
//
// O sea: el sintoma era identico al de un Space caido, y la causa estaba en esta linea.
const CABECERAS = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, content-type, apikey, x-client-info, x-supabase-api-version",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function responder(cuerpo: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: CABECERAS });
}

function degradado(estado: Estado, extra: Record<string, unknown> = {}): Response {
  // 200 a proposito: para la aplicacion esto no es un error, es que la estimacion no esta
  // disponible. El NEWS2 sigue en pantalla.
  return responder({
    estado,
    prediccion: null,
    mensaje: explicarEstado(estado),
    ...extra,
  });
}

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CABECERAS });
  if (req.method !== "POST") return responder({ error: "usar POST" }, 405);

  const autorizacion = req.headers.get("Authorization");
  if (!autorizacion) return responder({ error: "falta la cabecera Authorization" }, 401);

  const urlDelMotor = Deno.env.get("ZAHA_API_URL");
  const tokenDelMotor = Deno.env.get("ZAHA_API_TOKEN");
  if (!urlDelMotor || !tokenDelMotor) {
    // Es un error de configuracion, no del motor. Se distingue para que no parezca que
    // el Space esta caido cuando lo que falta es un secreto.
    console.error("faltan ZAHA_API_URL o ZAHA_API_TOKEN en los secretos");
    return degradado("caido");
  }

  let patient_id: string | undefined;
  let sensibilidad_objetivo: number | undefined;
  try {
    const cuerpo = await req.json();
    patient_id = cuerpo?.patient_id;
    sensibilidad_objetivo = cuerpo?.sensibilidad_objetivo;
  } catch {
    return responder({ error: "cuerpo JSON invalido" }, 400);
  }
  if (!patient_id) return responder({ error: "falta patient_id" }, 400);

  // El JWT de quien llama, no la service_role: RLS se aplica igual que en el navegador.
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: autorizacion } } },
  );

  const { data: paciente, error: errorPaciente } = await supabase
    .from("patients")
    .select("date_of_birth")
    .eq("id", patient_id)
    .single();

  if (errorPaciente || !paciente) {
    // Puede ser que no exista o que RLS no deje verlo. No se distingue a proposito: decir
    // "existe pero no podes verlo" ya filtra que existe.
    return responder({ error: "paciente no encontrado" }, 404);
  }

  // La ultima toma VIGENTE. `superseded_by IS NULL` descarta las enmendadas: estimar
  // sobre un valor que ya fue corregido seria explicar una alerta con un dato que la
  // propia base considera erroneo.
  const { data: tomas, error: errorTomas } = await supabase
    .from("vital_records")
    .select(
      "id, recorded_at, respiratory_rate, oxygen_saturation, temperature, " +
        "systolic_bp, heart_rate, consciousness_level",
    )
    .eq("patient_id", patient_id)
    .is("superseded_by", null)
    .order("recorded_at", { ascending: false })
    .limit(1);

  if (errorTomas) {
    console.error("error leyendo vital_records:", errorTomas.message);
    return responder({ error: "no se pudo leer la medicion" }, 500);
  }
  if (!tomas || tomas.length === 0) return degradado("sin_tomas");

  const toma = tomas[0] as TomaDeLaBase;
  const observacion = aObservacion(toma, paciente.date_of_birth);

  const control = new AbortController();
  const reloj = setTimeout(() => control.abort(), TIEMPO_LIMITE_MS);

  let respuesta: Response;
  try {
    respuesta = await fetch(`${urlDelMotor.replace(/\/$/, "")}/prediccion`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // El token NUNCA se registra. Si esto aparece en un log, es una filtracion.
        Authorization: `Bearer ${tokenDelMotor}`,
      },
      body: JSON.stringify({
        observacion,
        ...(sensibilidad_objetivo !== undefined ? { sensibilidad_objetivo } : {}),
      }),
      signal: control.signal,
    });
  } catch (e) {
    // AbortError incluido: un Space que no contesta en 8 s esta despertando.
    const dormido = e instanceof DOMException && e.name === "AbortError";
    console.error("el motor no respondio:", dormido ? "timeout" : String(e));
    return degradado(dormido ? "dormido" : "caido");
  } finally {
    clearTimeout(reloj);
  }

  const estado = estadoSegunRespuesta(respuesta.status);
  if (estado !== "ok") {
    console.error(`el motor respondio ${respuesta.status}`);
    return degradado(estado);
  }

  const prediccion = await respuesta.json();

  return responder({
    estado: "ok",
    // Qué observación se usó: sin esto la interfaz no puede decir "estimado sobre la
    // toma de las 14:30" y la predicción parecería flotar sobre el paciente entero.
    medicion: { id: toma.id, recorded_at: toma.recorded_at },
    prediccion,
    mensaje: "",
  });
});
