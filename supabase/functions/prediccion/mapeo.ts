/**
 * Traducción entre el vocabulario de la base y el de la API de inferencia (SCRUM-64).
 *
 * POR QUÉ ESTE ARCHIVO ESTÁ SEPARADO DE `index.ts`
 * Acá no hay Deno, ni red, ni Supabase: sólo funciones puras. Así la parte que puede
 * equivocarse en silencio —el mapeo de parámetros— se prueba con `node --test`, sin
 * levantar nada. `index.ts` queda con el transporte, que es lo que no se puede probar
 * sin un entorno real.
 *
 * EL NOMBRE DE CADA PARÁMETRO CAMBIA DOS VECES EN EL CAMINO
 * La base habla inglés (`respiratory_rate`), el motor de IA habla castellano
 * (`frecuencia_respiratoria`) porque se entrenó sobre una cohorte traducida. Ese salto es
 * exactamente donde se corren las columnas sin que nada falle: un mapeo equivocado sigue
 * devolviendo una probabilidad plausible, de otro paciente. Por eso el mapeo es explícito
 * y tiene prueba.
 */

/** Una toma vigente, tal como sale de `vital_records`. */
export type TomaDeLaBase = {
  id: string;
  recorded_at: string;
  respiratory_rate: number;
  oxygen_saturation: number;
  temperature: number;
  systolic_bp: number;
  heart_rate: number;
  consciousness_level: "A" | "C" | "V" | "P" | "U";
};

/** Lo que espera `POST /prediccion` del motor. El orden no importa: lo reordena la API. */
export type ObservacionParaLaApi = {
  frecuencia_respiratoria: number;
  spo2: number;
  temperatura: number;
  presion_sistolica: number;
  frecuencia_cardiaca: number;
  confusion: 0 | 1;
  edad: number;
};

/**
 * ACVPU → el binario `confusion` que conoce el modelo.
 *
 * ESTA ES LA DECISIÓN CLÍNICA DEL ARCHIVO, Y VA HACIA EL LADO SEGURO.
 * El modelo se entrenó sobre una cohorte que sólo registraba `confusion` sí/no, y en esa
 * traducción `confusion = 1` quedó como "C". Pero ACVPU tiene cinco niveles, y V, P y U
 * son *peores* que C: un paciente que sólo responde al dolor está más comprometido que
 * uno confuso. NEWS2 los puntúa a los cuatro igual, con 3 puntos.
 *
 * Mapear V, P o U a `confusion = 0` diría que un paciente inconsciente está alerta, que
 * es el error en la dirección peligrosa. Así que todo lo que no sea "A" cuenta como 1.
 *
 * El costo de esta decisión es que el modelo no distingue entre confusión y coma. Eso es
 * un límite de la cohorte de entrenamiento, no de este mapeo, y está declarado.
 */
export function aConfusion(nivel: TomaDeLaBase["consciousness_level"]): 0 | 1 {
  return nivel === "A" ? 0 : 1;
}

/**
 * Edad en años cumplidos a la fecha de la toma, no a la de hoy.
 *
 * Usar la fecha de hoy daría una edad distinta según cuándo se consulta una toma vieja, y
 * la misma observación devolvería dos predicciones diferentes.
 */
export function edadEnLaToma(fechaDeNacimiento: string, momentoDeLaToma: string): number {
  const nacimiento = new Date(fechaDeNacimiento);
  const toma = new Date(momentoDeLaToma);
  if (Number.isNaN(nacimiento.getTime()) || Number.isNaN(toma.getTime())) {
    throw new Error("fecha invalida al calcular la edad");
  }

  let edad = toma.getUTCFullYear() - nacimiento.getUTCFullYear();
  const mes = toma.getUTCMonth() - nacimiento.getUTCMonth();
  if (mes < 0 || (mes === 0 && toma.getUTCDate() < nacimiento.getUTCDate())) {
    edad -= 1;
  }
  return edad;
}

export function aObservacion(
  toma: TomaDeLaBase,
  fechaDeNacimiento: string,
): ObservacionParaLaApi {
  return {
    frecuencia_respiratoria: toma.respiratory_rate,
    spo2: toma.oxygen_saturation,
    temperatura: Number(toma.temperature),
    presion_sistolica: toma.systolic_bp,
    frecuencia_cardiaca: toma.heart_rate,
    confusion: aConfusion(toma.consciousness_level),
    edad: edadEnLaToma(fechaDeNacimiento, toma.recorded_at),
  };
}

/**
 * ¿El motor contestó JSON?
 *
 * EL ESTADO HTTP NO ALCANZA, Y ESO COSTÓ UN 500 CORRIENDO LA APLICACIÓN.
 * Hugging Face sirve páginas HTML **con estado 2xx**: la pantalla de demostración en la
 * raíz del Space y el aviso de que el Space está despertando. Una de esas llegó acá, pasó
 * por `estadoSegunRespuesta` como "ok" —el estado era 2xx, no había nada que objetar— y
 * `respuesta.json()` reventó con un `SyntaxError` que nadie atrapaba.
 *
 * Lo que convirtió el detalle en un problema serio: el 500 que devuelve el runtime cuando
 * una excepción escapa **no lleva las cabeceras CORS de esta función**, así que el
 * navegador lo descartó sin leerlo y la aplicación reportó «no se pudo enviar el pedido a
 * la Edge Function». Es decir: el síntoma de una función que no existe, por un motor que
 * contestó de más.
 *
 * Se mira el tipo declarado y no se intenta adivinar por el contenido: si el motor dice
 * que manda HTML, no hay nada que parsear.
 */
export function pareceJson(contentType: string | null | undefined): boolean {
  if (!contentType) return false;
  // `application/json` y `application/problem+json`, con o sin `; charset=utf-8`.
  // El `(;|$)` del final es lo que evita que `application/jsonp` pase por JSON.
  return /^application\/([\w.-]+\+)?json\s*(;|$)/i.test(contentType.trim());
}

/**
 * La URL exacta que se le pide al motor.
 *
 * Tolera las barras de sobra porque el valor sale de un secreto que se pega a mano en un
 * panel: `…/api`, `…/api/` y `…/api//` tienen que dar todos lo mismo.
 */
export function urlDePrediccion(urlBase: string): string {
  return `${urlBase.replace(/\/+$/, "")}/prediccion`;
}

/**
 * Lo único de la URL que se puede registrar.
 *
 * Se registra el camino y NO la URL entera a propósito: lo que hay que poder ver en un
 * log es si el `/api` está donde tiene que estar, y para eso el host no aporta nada. Si
 * alguien pega cualquier cosa en el secreto, esa cualquier cosa no termina en los logs.
 */
export function caminoRegistrable(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    return "(URL invalida)";
  }
}

/**
 * Qué le contestamos a la aplicación cuando el motor no está.
 *
 * `dormido` y `caido` NO son errores para quien llama: la aplicación sigue mostrando
 * NEWS2, que se calcula en la base y nunca dependió de este servicio (ADR-004). Por eso
 * la Edge Function responde 200 con `estado` y la interfaz decide. Un 500 haría que la
 * pantalla entera pareciera rota por algo que es opcional.
 */
export type Estado = "ok" | "dormido" | "caido" | "sin_tomas";

export function estadoSegunRespuesta(status: number): Estado {
  // 503 es lo que devuelve un Space que esta despertando. 504 lo pone el proxy.
  if (status === 503 || status === 504) return "dormido";
  if (status >= 200 && status < 300) return "ok";
  return "caido";
}

/** Mensaje para la interfaz. Nunca inventa una predicción ni sugiere que la haya. */
export function explicarEstado(estado: Estado): string {
  switch (estado) {
    case "ok":
      return "";
    case "dormido":
      return "El motor predictivo está despertando. El puntaje NEWS2 no depende de él.";
    case "caido":
      return "El motor predictivo no está disponible. El puntaje NEWS2 no depende de él.";
    case "sin_tomas":
      return "El paciente no tiene mediciones vigentes para estimar.";
  }
}
