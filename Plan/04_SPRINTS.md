# 🏃 Plan de Sprints — Zaha CDSS

**Definido el 2026-08-27.** Cadencia de 2 semanas, cierre el 20/11/2026, dejando la última
semana de noviembre libre para la presentación final.

Los sprints 1 y 2 son **retroactivos**: cubren trabajo ya terminado y sus fechas salen del
historial real de git (`git log --reverse`). El hueco entre el 12/06 y el 17/08 es el receso
de cursada; no se inventan sprints vacíos para taparlo.

Los sprints se crean **a mano desde la UI** (Backlog → Crear sprint): el MCP de Atlassian no
expone tableros ni sprints. La asignación de issues sí se puede automatizar.

---

## Resumen

| # | Nombre | Fechas | Issues | Foco |
|---|--------|--------|-------:|------|
| 1 | Fundaciones | 21/05 – 12/06 | 7 | Monorepo, ramas, credenciales aisladas |
| 2 | Motor determinístico NEWS2 | 17/08 – 28/08 | 13 | Esquema FHIR-like, NEWS2, RLS, append-only |
| 3 | PWA: esqueleto y carga de vitales | 31/08 – 11/09 | 8 | React+Vite, auth, formulario one-click, **PhysioNet** |
| 4 | PWA: tablero y offline | 14/09 – 25/09 | 8 | Dashboard de triage, service worker, cola Dexie |
| 5 | Cierre de PWA y datos | 28/09 – 09/10 | 9 | Accesibilidad, ingesta MIMIC-IV-ED, etiqueta v2 |
| 6 | Modelado y comparativa | 12/10 – 23/10 | 9 | XGBoost, LSTM, tasa de alertas, ONNX |
| 7 | Inferencia e integración | 26/10 – 06/11 | 9 | FastAPI, HF Spaces, explicabilidad, acuse |
| 8 | Cumplimiento y entrega | 09/11 – 20/11 | 5 | Leyes, gestión de riesgos, presentación final |

**Total: 68 issues.** Las 6 épicas (`SCRUM-6`..`SCRUM-11`) no se asignan a sprints: en Scrum
las épicas atraviesan sprints, no viven dentro de uno.

---

## Sprint 1 — Fundaciones
**21/05/2026 – 12/06/2026 · 7 issues · terminado**

> **Objetivo:** que el monorepo compile y que nadie pueda escribir en `main` sin PR.

`SCRUM-12` `SCRUM-13` `SCRUM-14` `SCRUM-15` `SCRUM-16` `SCRUM-17` `SCRUM-18`

---

## Sprint 2 — Motor determinístico NEWS2
**17/08/2026 – 28/08/2026 · 13 issues · terminado**

> **Objetivo:** una base capaz de recibir signos vitales crudos y devolver el nivel de riesgo
> al instante, con el registro clínico protegido de sobreescrituras.

`SCRUM-19` `SCRUM-20` `SCRUM-21` `SCRUM-22` `SCRUM-23` `SCRUM-24` `SCRUM-25` `SCRUM-26`
`SCRUM-27` `SCRUM-28` `SCRUM-29` `SCRUM-30` `SCRUM-31`

Cierra con las migraciones aplicadas, 21/21 casos clínicos y 17/17 aserciones de enmienda.

---

## Sprint 3 — PWA: esqueleto y carga de vitales
**31/08/2026 – 11/09/2026 · 8 issues · SIN CÓDIGO PENDIENTE al 30/08**

> **Objetivo:** poder entrar a `/app` con un usuario real y cargar una toma de signos vitales
> que quede guardada con su score. Y desbloquear PhysioNet.

**Estado al 30/08/2026 — el objetivo está cumplido antes de que el sprint empiece.**
`SCRUM-32`, `34`, `36`, `37`, `38` y `39` en **Done**, todos mergeados a `main`
(PR #2 a #5). Queda `SCRUM-77`, que es redacción, y `SCRUM-48`, que depende de un
revisor externo.

Se adelantó además `SCRUM-40` del sprint 4 (detalle de paciente con desglose e
historial), y `SCRUM-41` quedó cumplido de arrastre al corregir el indicador de
antigüedad. Conviene revisar su criterio de aceptación y cerrarlo formalmente.

| Issue | Qué | Estado |
|---|---|---|
| `SCRUM-48` | **BLOQUEANTE:** completar el credentialing de PhysioNet | 🟡 solicitud enviada el 30/08, en espera |
| `SCRUM-32` | HU-01 — Módulo de carga rápida de signos vitales | ✅ |
| `SCRUM-34` | Scaffold SPA React + Vite + TS para `/app` | ✅ |
| `SCRUM-36` | Aplicar la capa de marca a landing y login | ✅ |
| `SCRUM-37` | Aplicar la capa clínica a `/app` | ✅ |
| `SCRUM-38` | Autenticación Supabase Auth + selección de rol | ✅ |
| `SCRUM-39` | Formulario one-click de los 7 parámetros | ✅ |
| `SCRUM-77` | Actualizar el TP con las decisiones nuevas | ⬜ redacción |

> ⚠️ `SCRUM-48` va primero en el sprint aunque no dependa de nada del código: la revisión de
> PhysioNet tarda de días a semanas y bloquea las épicas 4 y 5 enteras. Es el riesgo #1 del
> cronograma.

---

## Sprint 4 — PWA: tablero y offline
**14/09/2026 – 25/09/2026 · 8 issues**

> **Objetivo:** ver la sala completa ordenada por riesgo, y que la carga siga funcionando sin
> señal.

| Issue | Qué | Estado |
|---|---|---|
| `SCRUM-33` | HU-06 — Dashboard de triage dinámico | ⬜ |
| `SCRUM-40` | Detalle de paciente con desglose del score por parámetro | ✅ **adelantado el 30/08** |
| `SCRUM-41` | Indicador de antigüedad de la medición | 🟡 cumplido de arrastre, falta cerrarlo |
| `SCRUM-42` | Dashboard clínico con orden dinámico por riesgo |
| `SCRUM-43` | PWA: manifiesto + service worker |
| `SCRUM-44` | Cola offline con Dexie y reconciliación |
| `SCRUM-35` | Landing en Astro |
| `SCRUM-49` | Firmar el DUA específico de MIMIC-IV-ED |

---

## Sprint 5 — Cierre de PWA y datos
**28/09/2026 – 09/10/2026 · 9 issues**

> **Objetivo:** cerrar la aplicación clínica y tener el dataset listo y etiquetado para
> entrenar.

| Issue | Qué |
|---|---|
| `SCRUM-45` | Auditoría de accesibilidad: contraste y codificación redundante |
| `SCRUM-46` | Validación clínica de los mockups |
| `SCRUM-47` | HU-03 — Motor de IA y alertas predictivas |
| `SCRUM-50` | Pipeline de ingesta con datos sintéticos |
| `SCRUM-51` | Descarga y limpieza de MIMIC-IV-ED |
| `SCRUM-52` | Esquemas de validación con Pydantic / Pandera |
| `SCRUM-53` | Implementar la definición de etiqueta v2 |
| `SCRUM-70` | HU-05 — Estructura FHIR y trazabilidad legal |
| `SCRUM-72` | Log de auditoría inalterable de alertas y acuses |

---

## Sprint 6 — Modelado y comparativa
**12/10/2026 – 23/10/2026 · 9 issues**

> **Objetivo:** el resultado defendible de la tesis — igualar la sensibilidad de NEWS2
> reduciendo la tasa de alertas.

| Issue | Qué |
|---|---|
| `SCRUM-54` | Split por paciente y control de fuga temporal |
| `SCRUM-55` | Análisis exploratorio de datos |
| `SCRUM-56` | Baseline XGBoost sobre el snapshot actual |
| `SCRUM-57` | LSTM sobre series de 48 h — hipótesis bajo prueba |
| `SCRUM-58` | **Comparativa de tasa de alertas a sensibilidad igualada** |
| `SCRUM-59` | Exportar el modelo elegido a ONNX |
| `SCRUM-60` | Documentar el caveat de NEWS2 en urgencias |
| `SCRUM-71` | Mapear el esquema propio a recursos FHIR |
| `SCRUM-76` | Redacción del marco teórico de la tesis |

---

## Sprint 7 — Inferencia e integración
**26/10/2026 – 06/11/2026 · 9 issues**

> **Objetivo:** el sistema completo de punta a punta, y que siga siendo seguro cuando la IA
> no responde.

| Issue | Qué |
|---|---|
| `SCRUM-61` | HU-04 — Alertas explicables y flujo one-click |
| `SCRUM-62` | API REST con FastAPI y onnxruntime |
| `SCRUM-63` | Desplegar la API en Hugging Face Spaces |
| `SCRUM-64` | Edge Function que envía el historial a la API |
| `SCRUM-65` | Degradación elegante: si el Space duerme, NEWS2 sigue |
| `SCRUM-66` | Explicabilidad: contribución por parámetro |
| `SCRUM-67` | Mostrar la predicción separada del score determinístico |
| `SCRUM-68` | Flujo one-click: validar / posponer con acuse |
| `SCRUM-73` | Encuadre SaMD y disposición ANMAT 9688/19 |

---

## Sprint 8 — Cumplimiento y entrega
**09/11/2026 – 20/11/2026 · 5 issues**

> **Objetivo:** cerrar el encuadre regulatorio y llegar a la defensa con todo entregado.

| Issue | Qué |
|---|---|
| `SCRUM-69` | Medir la tasa de alertas real de la app vs. la referencia |
| `SCRUM-74` | Cumplimiento Ley 25.326 y Ley 27.706 |
| `SCRUM-75` | Documento de gestión de riesgos del dispositivo |
| `SCRUM-78` | Manual de usuario para enfermería |
| `SCRUM-79` | Presentación final de Prácticas Profesionales 3 |

Sprint deliberadamente liviano: es el de la entrega, y siempre aparece trabajo que se
arrastra de los anteriores.

---

## Criterios usados para repartir

1. **El bloqueante primero.** `SCRUM-48` (PhysioNet) entra en el sprint 3 aunque su resultado
   se use recién en el 5. La demora es externa y no se puede comprimir después.
2. **Nada depende de algo del mismo sprint que aún no existe.** La épica 5 va entera después
   de que el modelo esté exportado a ONNX (sprint 6).
3. **Lo académico se distribuye, no se apila al final.** Marco teórico, SaMD y actualización
   del TP quedan repartidos entre los sprints 3, 6 y 7 para que el sprint 8 no sea una pared.
4. **Las épicas no se meten en sprints.** Atraviesan varios; el issue va al sprint, la épica
   queda como contenedor.

---

## Bitácora — 2026-08-30

Jornada larga. Sprint 3 cerrado de código antes de empezar, PR #2 a #5 mergeados.

**Decisiones que condicionan sprints futuros:**

1. **La app es mobile-first estricta.** Dos breakpoints en todo `app/clinical`, los dos
   `sm:` (640px), y el contenido capado en `max-w-3xl` (768px). Arriba de eso no hay
   diseño: se centra y deja de crecer. Coherente con HU-01 (tablet vertical al pie de la
   cama), pero **`SCRUM-42` lo rompe**: `.ctable` supone una tabla, que es formato de
   tablet horizontal o monitor del office. Definir el breakpoint ancho en el sistema de
   diseño, una vez, antes de escribir la pantalla.
2. **`orientation: 'portrait'` en el manifiesto bloquea la rotación** de la PWA instalada.
   Al pie de la cama está bien; en un carro o soporte del office, no. Decidirlo en
   `SCRUM-43`, no heredarlo.
3. **El sistema de diseño va en `@layer components`.** Tailwind v4 mete lo suyo en capas y
   el CSS sin capa le gana a todas: las utilities estaban siendo decorativas en todo el
   proyecto. Documentado en `design_system/README.md`.
4. **Las tipografías se cargan con `<link>` en la página**, no con `@import` en las hojas:
   al concatenar dos capas, el `@import` de la segunda se descarta en silencio.
5. **Una cama sin score no es "riesgo bajo".** Tiene su propia categoría (`PESO_SIN_SCORE`)
   y se dibuja con `.score-incomplete`. **Queda abierto dónde va en el orden de la sala** —
   es una decisión clínica, no de código: validar en `SCRUM-46`.

**Sobre el hito 21/09 de la planilla de la cátedra:** está cumplido. El último punto que
faltaba era "función historial pacientes", que cubrió `SCRUM-40`. Ver la nota sobre la
planilla en la memoria del proyecto.

**Recomendado para retomar:** `SCRUM-43` (el más acotado), después `SCRUM-42` con la
decisión de responsive ya tomada. `SCRUM-44` (cola offline con Dexie) es la pieza más
difícil del sprint 4 —reconciliar escrituras contra una tabla append-only donde el score lo
calcula el servidor— y conviene empezarla con la cabeza fresca. `SCRUM-50` (pipeline
sintético) es la única cobertura contra una demora larga de PhysioNet.
