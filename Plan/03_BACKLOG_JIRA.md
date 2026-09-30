# Backlog de Jira — Zaha CDSS

Fuente: fusión del **TP N°1 (Ghilardi–Garcia)** — historias HU-01..HU-06, User Story Map,
3 iteraciones — con la **Carta Magna** (`00_CARTA_MAGNA.md`) y los **ADRs**
(`02_DECISIONES_TECNICAS.md`).

Sitio: `zahacdss.atlassian.net` · Proyecto destino: **ZAHA** (a crear) · cloudId
`114740e6-3414-4cd7-87d2-2bf228b0bd3b`

---

## Reparto de trabajo

| Persona | Rol en Jira | Alcance real |
| --- | --- | --- |
| **Nahuel Ghilardi** | Dev / Tech Lead | Todo el código. Commits 100% de su autoría. |
| **Gustavo Garcia** | Analista funcional / QA | Historias de UX y validación clínica; documentación académica. |
| **(tercer integrante)** | Analista de cumplimiento / Documentación | Marco regulatorio, tesis, entregables de cátedra. |

> El reparto en Jira simula trabajo complementario a efectos académicos. El desarrollo
> es de Nahuel; el registro de commits en GitHub refleja la autoría real.
> Se preserva la asignación original del TP (HU-01, HU-04, HU-06 → Gustavo) para que
> coincida con lo que la cátedra ya vio.

## Iteraciones (del User Story Map original)

| Iteración | Nombre | Contenido |
| --- | --- | --- |
| 1 | MVP — Registro y Score | Login, carga de vitales, NEWS2 determinístico, logs básicos |
| 2 | Inteligencia y Alertas | Motor de IA, alertas explicables, flujo One-Click, logs avanzados |
| 3 | Gestión e Interoperabilidad | HL7 FHIR, dashboard de triage, auditoría y trazabilidad legal |

Etiquetas: `iteracion-1`, `iteracion-2`, `iteracion-3`.
Etiquetas de área: `backend`, `frontend`, `ml`, `infra`, `regulatorio`, `academico`.

---

# ÉPICA 1 — Infraestructura y Setup Base
`iteracion-1` · `infra` · Asignada: Nahuel
> Establecer el monorepo, repositorios, reglas de rama y entornos. Entregable: estructura
> de carpetas compilando sin errores.

| # | Tipo | Resumen | Estado | Asignado |
| --- | --- | --- | --- | --- |
| 1.1 | Tarea | Inicializar repositorio `Nahuelito22/Zaha` con protección de rama `main` | ✅ Listo | Nahuel |
| 1.2 | Tarea | Configurar monorepo (`/app`, `/supabase`, `/ml_engine`) | ✅ Listo | Nahuel |
| 1.3 | Tarea | Aislar credenciales: cuenta dedicada `zaha.cdss@gmail.com` para Supabase / Jira / Hugging Face | ✅ Listo | Nahuel |
| 1.4 | Tarea | Configurar integraciones base (Astro + Tailwind) para la landing | ✅ Listo | Nahuel |
| 1.5 | Tarea | Activar el ruleset `Don't-Merge-Before-Pr` (hoy en `enforcement: disabled`) | ⬜ Pendiente | Nahuel |
| 1.6 | Tarea | Definir y documentar el flujo git: `Nahuel_Develop` → PR → `main` | ✅ Listo | Nahuel |
| 1.7 | Tarea | Sumar a Gustavo y al tercer integrante como colaboradores del repo | ⬜ Pendiente | Nahuel |

---

# ÉPICA 2 — Backend y Motor Determinístico NEWS2
`iteracion-1` · `backend` · Asignada: Nahuel
> La base de datos inspirada en FHIR y la lógica matemática en la nube. Entregable: base
> capaz de recibir datos crudos y devolver niveles de riesgo instantáneamente.

### HU-02 — Motor Determinístico de Cálculo NEWS2
*Como enfermero/a de sala, quiero un sistema que devuelva el puntaje exacto de riesgo
instantáneamente, para conocer la gravedad del paciente y evitar el cálculo mental manual.*
Prioridad: Alta · Riesgo: Medio · Puntos: 5 · Iteración 1 · **Nahuel Ghilardi**

**Validación**
- El sistema automatiza el cálculo de la escala validada internacionalmente NEWS2.
- El algoritmo categoriza el riesgo de inmediato, reduciendo la fatiga mental.
- El cálculo es reproducible: mismo input → mismo score, siempre.

| # | Tipo | Resumen | Estado | Asignado |
| --- | --- | --- | --- | --- |
| 2.1 | Tarea | Migración de esquema: `profiles`, `patients`, `encounters`, `vital_records`, `alerts` | 🟡 Escrita, sin aplicar | Nahuel |
| 2.2 | Tarea | CHECKs de rango fisiológico plausible en `vital_records` | 🟡 Escrita, sin aplicar | Nahuel |
| 2.3 | Tarea | 7 funciones puras `news2_score_*` + `news2_risk_level` | 🟡 Escrita, sin aplicar | Nahuel |
| 2.4 | Tarea | Trigger de cálculo automático y emisión de alertas | 🟡 Escrita, sin aplicar | Nahuel |
| 2.5 | Tarea | Escala de SpO2 desacoplada del O2 suplementario (`encounters.spo2_scale` como prescripción) | 🟡 Escrita, sin aplicar | Nahuel |
| 2.6 | Tarea | Denormalizar `spo2_scale_used` para reproducibilidad histórica del score | 🟡 Escrita, sin aplicar | Nahuel |
| 2.7 | Tarea | Separar `recorded_at` de `created_at` | 🟡 Escrita, sin aplicar | Nahuel |
| 2.8 | Tarea | Row Level Security: helper `current_profile_role()` + políticas por rol | 🟡 Escrita, sin aplicar | Nahuel |
| 2.9 | Tarea | Guardas anti-escalada de privilegios en las políticas de `profiles` | 🟡 Escrita, sin aplicar | Nahuel |
| 2.10 | Tarea | Suite de 21 casos clínicos contra las funciones puras (éxito = cero filas) | 🟡 Escrita, sin correr | Gustavo |
| 2.11 | Tarea | Aplicar migraciones al proyecto remoto y correr los tests | ⬜ Pendiente | Nahuel |
| 2.12 | **Decisión** | Definir si `vital_records` pasa a append-only con enmiendas versionadas | ⬜ Abierta | Nahuel |

> **2.12 es bloqueante de la Épica 3.** Hoy `vital_records` es editable y sobrescribe. Para
> valor legal debería ser append-only: un registro clínico no se pisa, se enmienda dejando
> el original visible. Cambia el modelo que consume el frontend, así que hay que resolverlo
> **antes** de escribir la PWA, no después.

---

# ÉPICA 3 — Frontend PWA y Landing Page
`iteracion-1` / `iteracion-2` · `frontend`
> La interfaz pública y el sistema clínico de bolsillo. Entregable: PWA instalable
> consumiendo la base real.

### HU-01 — Módulo de Carga Rápida de Signos Vitales
*Como enfermero/a de sala, quiero cargar signos vitales desde la tablet, para registrar el
estado del paciente de forma instantánea en el punto de cuidado sin requerir papel.*
Prioridad: Alta · Riesgo: Bajo · Puntos: 3 · Iteración 1 · **Gustavo Garcia**

**Validación**
- La interfaz permite ingresar rápidamente los 7 parámetros vitales rutinarios.
- Diseño adaptado a pantallas táctiles, targets de 44 px mínimo (se carga con guantes).
- Un vital sin cargar se marca explícitamente: NEWS2 sobre datos incompletos no es un
  NEWS2 válido y la interfaz tiene que decirlo.

### HU-06 — Dashboard de Triage Dinámico
*Como jefe/a de enfermería, quiero visualizar un panel con el nivel de riesgo de todos los
pacientes internados, para distribuir la carga laboral equitativamente.*
Prioridad: Media · Riesgo: Medio · Puntos: 5 · Iteración 3 · **Gustavo Garcia**

**Validación**
- Lista dinámica de pacientes ordenada por alertas activas y puntaje NEWS2.
- Consume datos del backend en tiempo real.

| # | Tipo | Resumen | Estado | Asignado |
| --- | --- | --- | --- | --- |
| 3.1 | Tarea | Scaffold SPA React + Vite + TS para `/app` (ADR-001) | ⬜ Pendiente | Nahuel |
| 3.2 | Tarea | Landing en Astro: producto, tecnología y créditos de datos | ⬜ Pendiente | Nahuel |
| 3.3 | Tarea | Aplicar la capa de marca (`design_system/brand.css`) a landing y login | ⬜ Pendiente | Nahuel |
| 3.4 | Tarea | Aplicar la capa clínica (`design_system/clinical.css`) a `/app` | ⬜ Pendiente | Nahuel |
| 3.5 | Tarea | Autenticación Supabase Auth + selección de rol (Enfermero, Médico, Jefe) | ⬜ Pendiente | Nahuel |
| 3.6 | Tarea | Formulario one-click de carga de los 7 parámetros vitales | ⬜ Pendiente | Nahuel |
| 3.7 | Tarea | Vista de detalle de paciente con desglose del score por parámetro | ⬜ Pendiente | Nahuel |
| 3.8 | Tarea | Dashboard clínico con orden dinámico por riesgo | ⬜ Pendiente | Nahuel |
| 3.9 | Tarea | Indicador de antigüedad de la medición (un NEWS2 de hace 6 h no vale lo mismo) | ⬜ Pendiente | Nahuel |
| 3.10 | Tarea | PWA: manifiesto + service worker con `vite-plugin-pwa` | ⬜ Pendiente | Nahuel |
| 3.11 | Tarea | Cola offline con Dexie y reconciliación al reconectar | ⬜ Pendiente | Nahuel |
| 3.12 | Tarea | Auditoría de accesibilidad: contraste, codificación redundante color+texto+forma | ⬜ Pendiente | Gustavo |
| 3.13 | Tarea | Validación clínica de los mockups con datos ficticios de Clínica Médica (24 camas) | ⬜ Pendiente | Gustavo |

---

# ÉPICA 4 — Data Engineering y Motor de IA
`iteracion-2` · `ml` · Asignada: Nahuel
> Procesamiento de series temporales médicas y entrenamiento del modelo. Entregable:
> modelo entrenado y exportado a ONNX.

### HU-03 — Motor de Inteligencia Artificial y Alertas Predictivas
*Como médico/a de guardia, quiero recibir alertas predictivas de deterioro horas antes de la
descompensación, para aplicar intervenciones tempranas y preventivas.*
Prioridad: Media · Riesgo: Alto · Puntos: 8 · Iteración 2 · **Nahuel Ghilardi**

**Validación**
- El modelo analiza la tendencia temporal de los parámetros vitales.
- La IA funciona como copiloto y **nunca** toma decisiones finales.
- **Métrica principal: tasa de alertas a sensibilidad igualada a NEWS2** (referencia a batir:
  37,6 alertas por 100 pacientes-día). No AUROC, no accuracy.

| # | Tipo | Resumen | Estado | Asignado |
| --- | --- | --- | --- | --- |
| 4.1 | Tarea | Completar el credentialing de PhysioNet (identidad + referente) | ⬜ **Bloqueante** | Nahuel |
| 4.2 | Tarea | Firmar el DUA específico de MIMIC-IV-ED | ⬜ Bloqueada por 4.1 | Nahuel |
| 4.3 | Tarea | Pipeline de ingesta con datos sintéticos para desarrollar sin esperar la credencial | ⬜ Pendiente | Nahuel |
| 4.4 | Tarea | Descarga y limpieza de MIMIC-IV-ED | ⬜ Bloqueada por 4.2 | Nahuel |
| 4.5 | Tarea | Esquemas de validación estricta con Pydantic / Pandera | ⬜ Pendiente | Nahuel |
| 4.6 | Tarea | Implementar la etiqueta v2: y=1 si {UCI o muerte} en `(t+1h, t+24h]`, lookback 24 h, ventana ciega 1 h | ⬜ Pendiente | Nahuel |
| 4.7 | Tarea | Split por paciente (nunca por fila) y control de fuga temporal | ⬜ Pendiente | Nahuel |
| 4.8 | Tarea | EDA en notebooks | ⬜ Pendiente | Nahuel |
| 4.9 | Tarea | Baseline XGBoost sobre el snapshot actual | ⬜ Pendiente | Nahuel |
| 4.10 | Tarea | LSTM sobre series de 48 h — **hipótesis bajo prueba**, no protagonista | ⬜ Pendiente | Nahuel |
| 4.11 | Tarea | Comparativa tasa de alertas @ sensibilidad NEWS2 entre baseline, XGBoost y LSTM | ⬜ Pendiente | Nahuel |
| 4.12 | Tarea | Exportar el modelo elegido a ONNX | ⬜ Pendiente | Nahuel |
| 4.13 | Tarea | Documentar el caveat: NEWS2 rinde peor en urgencias (sepsis AUROC 0.66, COVID 0.59) | ⬜ Pendiente | Tercer integrante |

> **4.1 es el bloqueante principal del proyecto.** La revisión de PhysioNet tarda de días a
> semanas y la entrega es en noviembre de 2026. La solicitud va con el instituto real,
> job title `Student`, país Argentina y la profesora de Prácticas 3 como referente
> (avisándole antes). Declarar "MIT" se rechaza y un rechazo complica reaplicar.

---

# ÉPICA 5 — API de Inferencia e Integración
`iteracion-2` / `iteracion-3` · `backend` · `ml` · Asignada: Nahuel
> Conectar el modelo predictivo con la aplicación clínica. Entregable: sistema completo
> funcionando de extremo a extremo.

### HU-04 — Interfaz de Alertas Explicables y Flujo "One-Click"
*Como profesional receptor de alertas, quiero recibir notificaciones tempranas que no sean
una "caja negra", para tomar decisiones clínicas fundamentadas de manera ágil.*
Prioridad: Alta · Riesgo: Medio · Puntos: 5 · Iteración 2 · **Gustavo Garcia**

**Validación**
- El sistema explica **por qué** alerta.
- Flujo "One-Click" implementado (validar o posponer).
- El diseño mitiga la fatiga de alertas integrándose en el flujo de trabajo.

| # | Tipo | Resumen | Estado | Asignado |
| --- | --- | --- | --- | --- |
| 5.1 | Tarea | API REST con FastAPI sirviendo el modelo con `onnxruntime` (ADR-004) | ⬜ Pendiente | Nahuel |
| 5.2 | Tarea | Desplegar la API en Hugging Face Spaces | ⬜ Pendiente | Nahuel |
| 5.3 | Tarea | Edge Function de Supabase que envía el historial del paciente a la API | ⬜ Pendiente | Nahuel |
| 5.4 | Tarea | **Degradación elegante**: si el Space duerme, NEWS2 determinístico sigue funcionando | ⬜ Pendiente | Nahuel |
| 5.5 | Tarea | Explicabilidad de la predicción (contribución por parámetro) | ⬜ Pendiente | Nahuel |
| 5.6 | Tarea | Mostrar la predicción en `/app` visualmente separada del score determinístico | ⬜ Pendiente | Nahuel |
| 5.7 | Tarea | Flujo One-Click: validar / posponer alerta, con registro del acuse | ⬜ Pendiente | Nahuel |
| 5.8 | Tarea | Medir la tasa de alertas real de la app y compararla con la referencia | ⬜ Pendiente | Gustavo |

---

# ÉPICA 6 — Marco Regulatorio, Auditoría y Entregables Académicos
`iteracion-3` · `regulatorio` · `academico`
> No estaba en la Carta Magna pero sí en el TP (HU-05) y es donde vive el trabajo de los
> otros dos integrantes.

### HU-05 — Estructura de Datos FHIR y Trazabilidad Legal
*Como administrador del sistema, quiero asegurar la interoperabilidad provincial y el
registro inalterable de cada alerta emitida, para protección legal del enfermero y la
institución.*
Prioridad: Alta · Riesgo: Alto · Puntos: 8 · Iteración 3 · **Nahuel Ghilardi**

**Validación**
- El sistema se estructura bajo HL7 FHIR para conectarse al Bus de Interoperabilidad provincial.
- Usa recursos FHIR específicos: `Observation`, `Patient`, `RiskAssessment`.

| # | Tipo | Resumen | Estado | Asignado |
| --- | --- | --- | --- | --- |
| 6.1 | Tarea | Mapear el esquema propio a recursos FHIR (`Observation`, `Patient`, `RiskAssessment`) | ⬜ Pendiente | Nahuel |
| 6.2 | Tarea | Log de auditoría inalterable de cada alerta emitida y cada acuse | ⬜ Pendiente | Nahuel |
| 6.3 | Tarea | Encuadre SaMD y disposición ANMAT 9688/19 | ⬜ Pendiente | Tercer integrante |
| 6.4 | Tarea | Cumplimiento Ley 25.326 (datos personales) y Ley 27.706 | ⬜ Pendiente | Tercer integrante |
| 6.5 | Tarea | Documento de gestión de riesgos del dispositivo | ⬜ Pendiente | Tercer integrante |
| 6.6 | Tarea | Redacción del marco teórico de la tesis | ⬜ Pendiente | Gustavo |
| 6.7 | Tarea | Actualizar el TP con las decisiones nuevas (reencuadre ADR-005, MIMIC-IV-ED) | ⬜ Pendiente | Gustavo |
| 6.8 | Tarea | Manual de usuario para personal de enfermería | ⬜ Pendiente | Tercer integrante |
| 6.9 | Tarea | Presentación final de Prácticas Profesionales 3 | ⬜ Pendiente | Los tres |

---

## Cambios respecto del TP original

1. **Se agrega la Épica 6.** HU-05 estaba suelta; ahora tiene su épica junto a todo el
   trabajo regulatorio y académico, que es donde entran los otros dos integrantes.
2. **HU-03 cambia de objetivo.** En el TP la meta era "predecir deterioro". Tras el
   reencuadre del ADR-005 la métrica es **tasa de alertas a sensibilidad igualada**, no
   precisión. La LSTM pasó de protagonista a hipótesis bajo prueba: si no aporta, ese
   también es un hallazgo reportable.
3. **Se explicita el bloqueante de PhysioNet** (4.1) como tarea con dueño y no como
   supuesto. Es el riesgo #1 del cronograma.
4. **Aparece la decisión abierta 2.12** (append-only) como issue de decisión, porque
   bloquea la Épica 3.
5. **Se agregan las tareas de degradación elegante** (5.4) y de separación visual entre
   score determinístico y predicción (5.6), derivadas del ADR-004.
6. **El dataset es MIMIC-IV-ED**, no MIMIC-IV completo (ADR-002/006), con su caveat
   declarado (4.13).
7. **Se quitan las referencias a "Sentinel-NEWS2"** y a la tablet EXO MEMO como hardware
   fijo: el producto es Zaha y la PWA es agnóstica de dispositivo (ADR-001).
8. **TensorFlow / `.keras` sale**; el entregable del modelo es ONNX (ADR-004).
