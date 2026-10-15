# Edge Function `prediccion` (SCRUM-64)

Puente entre la aplicación clínica y el motor de IA.

Nació porque el Space era privado y su token no podía vivir en el navegador. **El
15/10/2026 el Space pasó a público**, así que el token quedó opcional y esa razón ya no
aplica. El puente se sostiene por las tres que siempre importaron: la base se consulta con
el **JWT de quien llama** (RLS, no `service_role`), acá vive la **traducción** del
vocabulario de la base al del modelo —que es donde se corren las columnas sin que nada
falle— y acá se decide, en un solo lugar, **qué se le dice a la pantalla cuando el motor
no está**.

## Desplegar

El secreto primero. **No va al repositorio ni a `.env` del cliente.**

```bash
supabase secrets set ZAHA_API_URL=https://zaha-cdss-inferencia.hf.space/api
supabase functions deploy prediccion
```

**Mergear el PR no despliega la función.** El código de Supabase vive en este repositorio
pero se publica aparte, con el comando de arriba; mientras no se corra, en producción
sigue el código anterior. Costó una confusión: la versión que reporta el panel sube
aunque el contenido sea el mismo, así que el número de versión no sirve para saber qué
está corriendo — hay que mirar el `ezbr_sha256` o el código.

> **El `/api` del final no es opcional.** La API vive montada bajo `/api` dentro del
> servidor de Gradio del Space; sin ese sufijo, esta función pediría `/prediccion` en la
> raíz y recibiría la pantalla de demostración en vez de JSON. El porqué está en
> `deploy/hf_space/app.py`.

`ZAHA_API_TOKEN` es **opcional**: sólo hace falta si el Space vuelve a ser privado. Si
está cargado, la función lo manda; si no, no manda cabecera de autorización. Cuando haga
falta, es un token de la cuenta `Zaha-CDSS` con permiso de **lectura** sobre el Space —y
si es *fine-grained*, hay que marcarle explícitamente ese repositorio, porque si no
Hugging Face responde **404** y el síntoma es idéntico al de una ruta equivocada.

## Usar

```bash
curl -X POST "$SUPABASE_URL/functions/v1/prediccion" \
  -H "Authorization: Bearer $JWT_DEL_USUARIO" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "<uuid>"}'
```

`sensibilidad_objetivo` es opcional (`0.5`, `0.6`, `0.7`, `0.8`).

## Qué devuelve

Siempre **200**, con un campo `estado`:

| `estado` | Qué pasó | Qué hace la interfaz |
|---|---|---|
| `ok` | Hay estimación en `prediccion` | Mostrarla, separada del puntaje NEWS2 |
| `dormido` | El Space está despertando (503/504, o más de 8 s) | Mostrar sólo NEWS2 |
| `caido` | El motor no está disponible, o contestó algo que no es JSON | Mostrar sólo NEWS2 |
| `sin_tomas` | El paciente no tiene mediciones vigentes | Mostrar sólo NEWS2 |

Que los tres últimos sean 200 y no un error es deliberado: **para la aplicación, que no
haya estimación no es una falla**. El puntaje NEWS2 lo calcula un trigger de la base y
nunca dependió de este servicio (ADR-004). Un 500 haría que la pantalla pareciera rota por
algo que es opcional. Es SCRUM-65 visto desde este lado.

## Tres decisiones que conviene conocer antes de tocar esto

**No se usa la `service_role` key.** La base se consulta con el JWT de quien llama, así
que RLS se aplica igual que en el navegador. Con la `service_role` esta función sería un
agujero para leer la historia clínica de cualquier paciente.

**Se manda la última toma vigente, no el historial.** El título del issue dice "historial"
porque se escribió cuando la planificación daba por hecho un modelo temporal. El modelo
desplegado es de corte transversal —una fila por paciente— y la API acepta **una**
observación. La parte temporal sigue colgando de SCRUM-57.

**ACVPU se colapsa al binario `confusion` hacia el lado seguro.** El modelo sólo conoce
"confuso sí/no", pero ACVPU tiene cinco niveles y V, P y U son *peores* que C. Todo lo que
no sea `A` cuenta como `1`: mapear un paciente que no responde a `0` le diría al modelo
que está alerta. El costo es que el modelo no distingue confusión de coma, y eso es un
límite de la cohorte de entrenamiento.

## Probar el mapeo

La lógica pura está separada en `mapeo.ts` justamente para poder probarla sin Deno:

```bash
node --test supabase/functions/prediccion/mapeo.test.ts
```
