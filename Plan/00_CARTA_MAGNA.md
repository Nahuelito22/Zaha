# 🧭 Carta Magna de Desarrollo: ZAHA CDSS
**Documento Maestro de Planificación y Backlog**

## 🎯 Objetivo del Documento
Proveer un mapa de ruta técnico estricto para el desarrollo secuencial de Zaha. Los agentes de IA deben consultar este documento y los sub-planes correspondientes antes de ejecutar código, asegurando la cohesión del Monorepo.

> **Estado al 2026-08-27.** Épicas 1 y 2 terminadas y aplicadas. Épica 3 en curso (Sprint 3).
> Documentos que hay que leer junto con este:
> - `02_DECISIONES_TECNICAS.md` — los ADR. Mandan sobre este documento.
> - `04_SPRINTS.md` — el reparto del backlog en 8 sprints hasta el 20/11/2026.
> - `05_PREPARACION.md` — stack, notebooks, entrenamiento local vs. nube, y las
>   reglas de manejo de datos restringidos de PhysioNet. **Leer antes de tocar datos.**

---

## 📦 ÉPICA 1: Infraestructura y Setup Base (Foundation)
**Estado:** ✅ Terminada
**Objetivo:** Establecer el Monorepo, repositorios, reglas de ramas y entornos de desarrollo.
* [x] Inicializar repositorio en GitHub con protección de rama `main`.
* [x] Configurar Monorepo (`/app`, `/supabase`, `/ml_engine`).
* [x] Aislar credenciales: Crear cuentas dedicadas para Supabase y Hugging Face.
* [x] Ruleset `Don't-Merge-Before-Pr` activo. Flujo: `Nahuel_Develop` → PR → `main`.
* [x] *Entregable:* Estructura de carpetas compilando sin errores.

## 🗄️ ÉPICA 2: Backend y Motor Determinístico (El MVP Core)
**Estado:** ✅ Terminada — aplicada a Supabase y verificada
**Objetivo:** Construir la base de datos inspirada en FHIR y la lógica matemática en la nube.
* [x] Migraciones: `profiles`, `patients`, **`encounters`**, `vital_records`, `alerts`.
* [x] Motor NEWS2 como 7 funciones puras + trigger de cálculo y emisión de alertas.
* [x] Row Level Security con políticas por rol y guardas anti-escalada de privilegios.
* [x] **`vital_records` es append-only** con enmiendas versionadas (ADR de `SCRUM-31`).
* [x] Seed de desarrollo con datos ficticios (`supabase/seed.sql`).
* [x] *Entregable:* Base capaz de recibir datos crudos y devolver niveles de riesgo al instante.

**Lo que hay que saber antes de tocarla:**
- La escala de SpO₂ vive en `encounters`, es una **prescripción médica** y no se infiere del
  oxígeno suplementario. `vital_records.spo2_scale_used` la copia para reproducibilidad.
- La consciencia es **ACVPU**, no AVDI: la C de confusión nueva puntúa 3.
- Corregir una toma es **insertar una enmienda** con motivo, nunca un `UPDATE`.
- La app lee de la vista `vital_records_vigentes`, no de la tabla.

## 📱 ÉPICA 3: Frontend PWA y Landing Page (La Cara Visible)
**Estado:** 🟡 En curso — Sprint 3
**Objetivo:** Desarrollar la interfaz pública y el sistema clínico de bolsillo.

Estructura decidida (ADR-001): **dos proyectos separados**, no islas de React en Astro.
```
app/
├── landing/     Astro + Tailwind      → la landing pública
└── clinical/    Vite + React 19 + TS  → la PWA clínica, servida bajo /app
```
* [x] Scaffold de `app/clinical` y mudanza del Astro a `app/landing`.
* [x] Autenticación con Supabase Auth y lectura del rol desde `profiles`.
* [x] Flujo de carga de los 7 parámetros vitales (HU-01).
* [x] Sala ordenada por riesgo clínico.
* [ ] **Landing Page (`/`):** presentación del producto, tecnología y créditos de datos.
* [ ] **Dashboard de triage** con orden dinámico y detalle por paciente.
* [ ] Manifiesto y Service Worker (offline con vite-plugin-pwa + Dexie).
* [ ] Auditoría de accesibilidad: contraste y codificación redundante.
* [ ] *Entregable:* PWA instalable en iOS/Android consumiendo la base de datos real.

**Regla de diseño que no se negocia:** la capa de **marca** (crema, terracota, Caprasimo) va en
landing y login. La capa **clínica** (neutros fríos, acento azul) va en `/app`. Rojo, ámbar y
verde quedan reservados en exclusiva a los 4 niveles NEWS2, y cada nivel se codifica con
color **más** forma **más** texto.

## 🧠 ÉPICA 4: Data Engineering y Motor IA (El Cerebro)
**Estado:** ⚪ Bloqueada por la credencial de PhysioNet (`SCRUM-48`, enviada)
**Objetivo:** Igualar la sensibilidad de NEWS2 **reduciendo la tasa de alertas**.
* [ ] Pipeline de ingesta con datos sintéticos (andamio, mientras llega MIMIC).
* [ ] Descarga y limpieza de **MIMIC-IV-ED** (no MIMIC-IV completo).
* [ ] Esquemas de validación estricta con Pydantic / Pandera.
* [ ] Etiqueta v2 y split **por paciente**.
* [ ] **Reproducir NEWS2 sobre la cohorte real** y medir su tasa de alertas (`SCRUM-80`).
* [ ] Baseline XGBoost sobre el snapshot; LSTM como hipótesis bajo prueba.
* [ ] Comparativa de tasa de alertas a sensibilidad igualada.
* [ ] *Entregable:* Modelo entrenado y exportado a **ONNX**.

> ⚠️ **El objetivo NO es ganarle a NEWS2 en AUROC** (ADR-005). NEWS2 solo alcanza 0,908 y el
> mejor modelo publicado 0,925: esa tesis sería marginal e indefendible. La métrica principal
> es la **tasa de alertas a sensibilidad igualada**. Nunca reportar accuracy (prevalencia
> 0,22–5%) ni usar "NEWS2 ≥ 7" como etiqueta (sería circular).
>
> El dataset de Kaggle **no sirve como producto**: una toma por paciente, sin desenlace, y le
> faltan 2 de los 7 parámetros de NEWS2. Solo sirve de andamio.

## 🔌 ÉPICA 5: API de Inferencia e Integración (El Sistema Vivo)
**Estado:** ⚪ Pendiente — depende de la Épica 4
**Objetivo:** Conectar el modelo predictivo con la aplicación clínica.
* [ ] API REST con FastAPI sirviendo el modelo con **onnxruntime**.
* [ ] Desplegar la API en Hugging Face Spaces.
* [ ] Edge Function de Supabase que envía el historial del paciente a la API.
* [ ] **Degradación elegante:** si el Space duerme, NEWS2 sigue funcionando igual.
* [ ] Explicabilidad de la predicción y flujo one-click con registro del acuse.
* [ ] *Entregable:* Sistema completo funcionando de extremo a extremo.

## ⚖️ ÉPICA 6: Marco Regulatorio, Auditoría y Entregables Académicos
**Estado:** ⚪ Pendiente, repartida entre los sprints 3, 6, 7 y 8
**Objetivo:** Encuadre del producto como SaMD, trazabilidad legal y entregables de la cátedra.
* [ ] Mapear el esquema propio a recursos FHIR (Observation, Patient, RiskAssessment).
* [ ] Log de auditoría inalterable de cada alerta y cada acuse.
* [ ] Encuadre SaMD y disposición ANMAT 9688/19.
* [ ] Cumplimiento Ley 25.326 y Ley 27.706.
* [ ] Documento de gestión de riesgos del dispositivo.
* [ ] Marco teórico de la tesis y actualización del TP.
* [ ] Manual de usuario y presentación final.
* [ ] *Entregable:* Documentación de cumplimiento y defensa de Prácticas Profesionales 3.
