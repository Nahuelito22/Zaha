# 🎯 Épica 4 - Paso 0: Definición de la Etiqueta (Label Spec)

> **v2 — 2026-08-25.** Revisada tras la revisión de literatura (NotebookLM, 300+ fuentes).
> Cambios respecto de v1: horizonte 12 h → **24 h**, se agregan variables estáticas,
> indicadores de ausencia, y la tasa de alertas como métrica principal.
>
> **La decisión más determinante de todo el proyecto de ML.** De acá salen las métricas,
> el balance de clases y si el resultado significa algo. Se define ANTES de tocar un modelo.

---

## Idea base

Un modelo supervisado aprende `X → y`. Para cada ejemplo necesita una **pregunta (X)**
y una **respuesta correcta (y)**. La "etiqueta" es esa respuesta.

Acá la pregunta no es *"¿este paciente está grave?"* (eso ya lo contesta NEWS2) sino:

> **"Dado todo lo que sé de este paciente hasta el momento t, ¿se va a deteriorar pronto?"**

Esa respuesta **no existe en los datos**: nadie escribió una columna "se va a deteriorar".
Hay que **fabricarla** a partir de lo que efectivamente pasó después.

---

## Las 5 piezas

### 1. Unidad de predicción — ¿qué es una fila?
**No es un paciente. Es un paciente en un momento `t`.**

Cada carga de signos vitales es un punto de predicción. Un paciente con 20 registros
genera hasta 20 ejemplos. (En la literatura: enfoque *sliding window* o *landmark*.)

### 2. Ventana de observación (lookback)
**Decisión: 24 h de registros previos.**

Rango en la literatura: 2 h a 48 h; valor típico 24–48 h. Remuestreo en grilla de 1–2 h
(estándar en MIMIC-IV).

> ⚠️ Ver ADR-005: la evidencia sugiere que el **snapshot actual** puede contener casi
> toda la señal. El lookback de 24 h existe para **poner esa hipótesis a prueba**,
> no porque demos por sentado que aporta.

### 3. Horizonte de predicción (lookahead)
**Decisión: 24 h como principal. Reportar 6 h y 12 h como análisis de sensibilidad.**

*(v1 decía 12 h.)* Corregido: los estudios a gran escala (Birmingham, Oxford) usan el
compuesto *muerte o transferencia a UCI dentro de 24 h*. Alinearse con el estándar hace
los resultados comparables con la literatura publicada.

### 4. El evento — ¿qué cuenta como "deterioro"?
**Decisión: desenlace compuesto = `pase a UCI` OR `muerte intrahospitalaria`.**

Es el desenlace más usado en estudios a gran escala. Ambos limpios en MIMIC-IV-ED.

> ⚠️ **TRAMPA A EVITAR: no usar "NEWS2 ≥ 7" como etiqueta.** Sería **circular** —
> entrenar un modelo para predecir un número que ya calculás con un trigger de Postgres.
> La etiqueta debe ser un **hecho clínico real**, independiente del score.

### 5. Ventana ciega (blanking period)
**Decisión: el evento cuenta si ocurre en `(t + 1h, t + 24h]`.** Se excluye la primera hora.

Sin esto el modelo "predice" lo que ya está pasando: eso es **detección**, no alerta
temprana. La hora de margen fuerza predicción genuina y deja tiempo real de intervención.

---

## Definición formal

Para cada registro de signos vitales en el momento `t` de un paciente:

| | |
|---|---|
| **X** | Secuencia de vitales en `[t − 24h, t]` + indicadores de ausencia + variables estáticas |
| **y** | `1` si ocurre {pase a UCI ∪ muerte} dentro de `(t + 1h, t + 24h]`, si no `0` |

**Variables estáticas (indispensables):** edad, sexo, y una medida de comorbilidad.
La literatura confirma que agregarlas mejora el AUROC de forma estadísticamente
significativa en cualquier modelo, NEWS2 incluido.

> 🚨 **Riesgo de leakage con la comorbilidad.** Los códigos ICD en MIMIC se asignan
> **retrospectivamente al alta**. Calcular un índice de Charlson desde ahí sería usar
> información del futuro. Opciones a evaluar: usar solo diagnósticos de ingreso, o
> prescindir de Charlson y quedarse con edad + sexo. **Pendiente de resolver.**

**Indicadores de ausencia (missingness).** Para cada parámetro se agrega una feature
binaria "¿se midió en esta ventana?". Resuelve el debate abierto de la literatura
(¿imputar o no?) usando ambas señales: la ausencia de una medición **es en sí misma
información clínica** — si la enfermera no tomó el signo, suele indicar estabilidad.

**Se descartan los `t` donde:**
- El paciente ya está en UCI (el evento ya ocurrió).
- El paciente ya fue dado de alta.
- Hay menos de 2 registros previos de vitales.

---

## Métricas

**Principal (ver ADR-005): tasa de alertas por 100 pacientes-día, a sensibilidad
igualada con NEWS2 ≥ 5.** Referencia de la literatura a batir: **37.6 alertas por
100 pacientes-día**, que afectan al 12.3% de los pacientes diariamente.

**Secundarias:** AUPRC · Número Necesario a Alertar (NNA) · sensibilidad · especificidad · PPV.

> ❌ **Accuracy queda prohibida.** Con prevalencia de ~0.22–5%, un modelo que prediga
> "nadie se deteriora" saca 99.78% de accuracy con 0% de sensibilidad.

---

## Consecuencias metodológicas

### Fuga de información (leakage) — tres fuentes
1. **Por paciente:** el split train/test va **por paciente, nunca por fila**.
2. **Temporal:** ninguna feature puede usar información posterior a `t`
   (cuidado con normalizaciones o imputaciones calculadas sobre el dataset completo).
3. **Por codificación retrospectiva:** ver la advertencia sobre ICD/Charlson arriba.

### Comparación contra el baseline
NEWS2 crudo se evalúa **con esta misma etiqueta y este mismo split**. Única forma
de que la comparación sea honesta.

### Limitaciones a declarar en la tesis
- **Paradoja del deterioro:** si el sistema funciona, la alerta temprana dispara una
  intervención que **evita** el desenlace — y el modelo parece falsamente ineficaz en
  evaluación retrospectiva. Limitación intrínseca de este diseño; declararla explícitamente.
- **Ámbito:** MIMIC-IV-ED es guardia, no sala general. NEWS2 cae en urgencias para
  sepsis (AUROC 0.66) y COVID-19 (0.59) por hipoxemia silenciosa. Ver ADR-006:
  esos subgrupos se analizan por separado.
- **Centro único:** MIMIC proviene de un solo hospital (Beth Israel Deaconess, Boston).
  Riesgo de sesgo local y generalización externa limitada.

---

## Pendiente de decidir

- [ ] ¿El compuesto incluye también *paro / activación de equipo de respuesta rápida*?
- [ ] Resolución del leakage de comorbilidad (Charlson vs. diagnósticos de ingreso vs. omitir).
- [ ] Tratamiento de pacientes con orden de no-reanimar (DNR): distorsionan la mortalidad.
- [ ] Estrategia de imputación dentro de la ventana (interpolación vs. forward-fill),
      complementaria a los indicadores de ausencia.
