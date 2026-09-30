# 🧱 Decisiones Técnicas (ADR) — ZAHA CDSS

Registro de decisiones de arquitectura. Cada una queda fechada y con su razón,
para poder defenderla y para no re-discutirla.

---

## ADR-001 — Frontend: React SPA (PWA) + Astro para la landing
**Fecha:** 2026-08-25 · **Estado:** ✅ Aceptada

### Decisión
- `/` (landing pública) → **Astro** (ya montado, es su punto fuerte).
- `/app` (aplicación clínica) → **SPA en React + Vite + TypeScript**, servida como **PWA**.
- **Descartado:** app nativa / APK.

### Razón
La app clínica necesita sesión persistente, estado en vivo, realtime y sobre todo
**offline** (enfermero al pie de la cama con wifi irregular). Astro es MPA-first:
cada navegación es una carga completa, lo que hace incómodo el service worker,
la cola offline y la rehidratación de sesión. Una SPA resuelve eso por diseño.
Una sola web responsive cubre móvil y PC sin Play Store, firmas ni builds nativos.

### Stack asociado
| Pieza | Elección |
|---|---|
| Base | React + Vite + TypeScript |
| PWA | `vite-plugin-pwa` (service worker + manifest) |
| Datos | Supabase JS + TanStack Query |
| Cola offline | Dexie (IndexedDB), sincroniza al reconectar |
| UI | Tailwind + shadcn/ui |

### Consecuencias / pendientes
- ⚠️ **Push en iOS:** las PWA en iOS requieren "Agregar a inicio" + iOS 16.4+.
  Para tablet al pie de cama con la app abierta, **Supabase Realtime alcanza**.
  No prometer push en la defensa sin validarlo antes.
- Alternativa descartada: SvelteKit (menos boilerplate, pero React gana por ecosistema).

---

## ADR-002 — Datasets: MIMIC-IV-ED como fuente principal
> ⚠️ **Ver ADR-006** para el caveat sobre el rendimiento de NEWS2 en urgencias.
**Fecha:** 2026-08-25 · **Estado:** 🟡 Aceptada, bloqueada por credencial PhysioNet

### Decisión
- **Principal:** `MIMIC-IV-ED` (módulo de guardia), tabla `vitalsign`.
- **Andamio:** dataset de Kaggle para construir la tubería mientras se destraba el acceso.
- **Descartado:** MIMIC-IV completo (`chartevents`).

### Razón
NEWS2 está diseñado y validado para pacientes de **sala/guardia, no de UCI**.
En terapia intensiva casi todos puntúan alto y la escala pierde poder discriminativo.
MIMIC-IV-ED tiene la población correcta, mediciones repetidas de casi exactamente
los parámetros NEWS2, y desenlaces limpios (internación, pase a UCI, mortalidad).
Además pesa una fracción de MIMIC-IV completo: manejable sin cluster.

### Consecuencias
- El Kaggle es **andamio, no producto**: sintético/simplificado, no defendible como evidencia.
- Bloqueante activo: credencial de PhysioNet no aprobada. Ver `Plan/epica_04_motor_ia/`.

---

## ADR-003 — Modelado: progresión baseline → GBM → LSTM → ensemble
> ⚠️ **Refinada por ADR-005** (2026-08-25): el orden y el objetivo cambiaron tras la revisión de literatura.
**Fecha:** 2026-08-25 · **Estado:** ✅ Aceptada

### Decisión
Cuatro escalones, en orden. Cada uno es un entregable válido por sí mismo.

1. **Baseline: NEWS2 crudo.** La tesis del proyecto es *"mi modelo le gana a NEWS2 solo"*.
   Sin este baseline el trabajo no tiene contra qué compararse.
2. **Gradient Boosting (XGBoost/LightGBM)** sobre features de ventana
   (último valor, delta, pendiente, mín/máx a 4h/8h/24h por parámetro).
3. **LSTM/GRU** sobre la secuencia cruda.
4. **Ensemble** (stacking o soft-voting) de 2 y 3.

### Razón
En datos clínicos tabulares el boosting suele ganarle a las redes. Es el caballo
de batalla, no el plato de prestigio. La LSTM aporta el eje de series temporales.
El ensemble cierra la idea del "pool" pero fundamentado, no como bolsa de modelos.

### Notas
- **Random Forest = bagging.** Ya cubierto como miembro del ensemble, no es familia aparte.
- **Monte Carlo reconvertido a MC Dropout:** correr la LSTM N veces con dropout activo
  en inferencia da una **banda de incertidumbre** → *"riesgo alto, confianza media"*.
  Ataca directo el requisito de "no caja negra" (HU N°4) y la fatiga de alertas.
- **Explicabilidad:** SHAP sobre el GBM produce literalmente
  *"alerta porque FR y temperatura vienen en ascenso"*. La LSTM sola no da eso limpio.
- **Métricas: NO usar accuracy.** El deterioro es evento raro (~2-5%); "nadie se deteriora"
  daría 97% de accuracy y sería inútil. Reportar **AUPRC**, **sensibilidad a tasa de
  alerta fija** y **número necesario a alertar**.

---

## ADR-004 — Inferencia: PyTorch → ONNX en Hugging Face, con degradación elegante
**Fecha:** 2026-08-25 · **Estado:** ✅ Aceptada

### Decisión
- Entrenar la LSTM en **PyTorch**, exportar a **ONNX**, servir con **`onnxruntime`**.
- **Descartado: TensorFlow/Keras.** (El README todavía lo menciona: corregir.)
- Health check honesto vía **GitHub Actions cron** a `/health` cada 6–12 h.
- El NEWS2 determinístico **nunca** depende de la API de IA.

### Razón
Importar TensorFlow son 15–20 s solos e infla el contenedor a ~2 GB. Con ONNX baja
a ~300 MB y el arranque a pocos segundos. Los Spaces gratuitos duermen tras ~48 h de
inactividad (verificar en la config del Space), así que el problema es menor de lo
temido, pero conviene no depender de eso.

Se descartó el enfoque de "script que no parezca bot": es frágil y, si violara términos,
se pierde el Space justo antes de la demo. Un health check de frente no tiene ese riesgo.

### Consecuencias
- El NEWS2 vive en un trigger de Postgres → un Space dormido significa
  *"sin predicción de tendencia por ahora"*, pero la app sigue funcionando entera.
- ⚠️ **Diseñar la UI explícitamente para ese estado degradado**, que no se rompa.
- Para la defensa: despertar el Space 10 min antes. Logística, no arquitectura.

---

## ADR-005 — Reencuadre del objetivo: reducir tasa de alertas, no maximizar AUROC
**Fecha:** 2026-08-25 · **Estado:** ✅ Aceptada · **Refina a:** ADR-003

### Contexto
La revisión de literatura (NotebookLM, 300+ fuentes) aportó evidencia que obliga a
corregir el objetivo original. Estudio de Oxford (2026), cohorte a gran escala:

| Modelo | AUROC |
|---|---|
| NEWS2 solo (baseline) | 0.908 |
| **XGBoost (solo última observación)** | **0.925** |
| LSTM (series 12–48 h) | 0.924 |
| Transformer | 0.921 |

**Dos conclusiones incómodas:**
1. La LSTM **no** le gana a XGBoost. Peor: XGBoost sin serie temporal, usando solo el
   snapshot actual, iguala a redes que procesan 48 h de historia ("Less is More", medRxiv 2026).
2. El margen de mejora sobre NEWS2 es de **~1.7 puntos de AUROC**. Una tesis basada en
   "mi IA le gana a NEWS2 en AUROC" produciría un resultado marginal e indefendible.

### Decisión
**El objetivo de Zaha deja de ser la precisión y pasa a ser la carga de alertas:**

> **Igualar la sensibilidad de NEWS2 reduciendo sustancialmente la tasa de alertas.**

**Métrica principal:** tasa de alertas por 100 pacientes-día, a sensibilidad igualada
con NEWS2 ≥ 5. Secundarias: AUPRC, número necesario a alertar (NNA).

### Razón
La literatura documenta que el problema real no es la precisión sino el ruido:
NEWS2 con umbral ≥5 genera **37.6 alertas por 100 pacientes-día**, afecta al **12.3%
de los pacientes diariamente**, y el **83.7% de los clínicos considera inútiles las
alertas actuales**. Detectar lo mismo molestando menos es clínicamente más valioso
que 1.7 puntos de AUROC, y conecta directo con la justificación de sobrecarga
cognitiva y burnout del documento original del proyecto.

### Consecuencia sobre el rol de la LSTM
La LSTM deja de ser la protagonista y pasa a ser **la hipótesis bajo prueba**:
*"¿aporta algo la tendencia temporal, o alcanza el snapshot?"*

Si la respuesta resulta ser "no aporta", **eso también es un hallazgo válido y
reportable**. El proyecto deja de depender de que la LSTM funcione.

**Orden de trabajo revisado:**
1. Baseline NEWS2 crudo.
2. **XGBoost sobre snapshot** (última observación + estáticas) ← modelo principal.
3. XGBoost sobre features de ventana (24 h) → mide cuánto aporta la tendencia.
4. LSTM sobre secuencia cruda → contrasta la hipótesis temporal.
5. Ensemble solo si 3 o 4 muestran ganancia real sobre 2.

---

## ADR-006 — Caveat sobre MIMIC-IV-ED (refina ADR-002)
**Fecha:** 2026-08-25 · **Estado:** ✅ Aceptada

### Contexto
La literatura documenta que NEWS2 **cae significativamente en urgencias** para
subgrupos específicos: sepsis (AUROC 0.66) y COVID-19 (AUROC 0.59), por hipoxemia
silenciosa e hiperlactatemia no integrada en la escala. NEWS2 fue diseñado para
**sala general**, no para guardia.

### Decisión
**Se mantiene MIMIC-IV-ED** como fuente principal, pero:
- La limitación se **declara explícitamente** en la tesis.
- Los subgrupos de sepsis y patología respiratoria se **analizan por separado**.

### Razón
Es un compromiso consciente, no un descuido. La alternativa (datos de sala general)
no está disponible de forma accesible: en MIMIC los vitales de sala viven en el módulo
de UCI. Además, sala general tiene registros muy espaciados (~4.5 por paciente-día),
lo que dificultaría el modelado temporal — aunque, dado ADR-005 (el snapshot alcanza),
esto pesa menos de lo que parecería.

Declarar la limitación de frente es mejor metodología que ocultarla.

---

## ADR-007 — ACVPU y oxígeno suplementario no existen en MIMIC-IV-ED
**Fecha:** 2026-09-09 · **Estado:** ✅ Aceptada

### Contexto
Verificado sobre los archivos y sobre la documentación oficial de PhysioNet: las tablas
`vitalsign` y `triage` de MIMIC-IV-ED tienen `temperature, heartrate, resprate, o2sat,
sbp, dbp` (más `rhythm`, `pain`, `acuity`, `chiefcomplaint`) y **nada más**. No hay nivel
de consciencia (ACVPU / AVPU / GCS) ni oxígeno suplementario.

No es una limitación del demo: es así también en la base completa. Son **2 de los 7
parámetros** de NEWS2, y son los dos que más pesan — el oxígeno suplementario suma 2 puntos
fijos y la "C" de confusión nueva suma 3.

Esto se descubrió el 2026-09-09 y **contradice el supuesto del ADR-002**, que decía que
MIMIC-IV-ED tiene "mediciones repetidas de casi exactamente los parámetros NEWS2". Tiene 5
de 7. Además implica que la aprobación de PhysioNet (`SCRUM-48`) **no resuelve este
problema**: llega con el mismo hueco.

### Decisión
Se imputa el valor de menor riesgo en los dos parámetros ausentes:

- Nivel de consciencia = **A (Alerta)** → 0 puntos.
- Oxígeno suplementario = **aire ambiente** → 0 puntos.

Y se registra por fila una marca `news2_imputado` (booleana) más `news2_puntos_imputados`
(cuántos puntos NO se pudieron evaluar), para poder medir el efecto en el análisis.

La limitación se declara explícitamente en la tesis, junto al caveat del ADR-006.

### Razón
Es lo que hacen los trabajos publicados que calculan NEWS2 sobre MIMIC, y tiene una
propiedad que lo vuelve defendible: **el sesgo es conocido y va en una sola dirección**.
Imputando el valor de menor riesgo, el score resultante **nunca sobreestima** el riesgo del
paciente; como mucho lo subestima, hasta 5 puntos. Para un trabajo cuya tesis es *"mi modelo
produce menos alertas que NEWS2 a igual sensibilidad"*, un baseline conservador que
subestima juega **en contra** de la hipótesis, no a favor. Si el modelo igual le gana, el
resultado es más fuerte, no más débil.

Las alternativas se evaluaron y se descartaron:
- **Redefinir el objetivo como un "NEWS-5"** de cinco parámetros: más honesto en el papel,
  pero rompe la comparabilidad con la literatura y desarma la tesis, porque ya no se estaría
  comparando contra NEWS2.
- **Buscar GCS y dispositivo de oxígeno en `chartevents` de MIMIC-IV**: existen, y los
  `subject_id` enlazan, pero `chartevents` está poblado sobre todo para estadías de UCI —
  justo la población que el ADR-006 excluye por perder poder discriminativo.

### Consecuencias
- **`SCRUM-80` hay que reescribirlo**: "reproducir NEWS2 sobre MIMIC-IV-ED" no es ejecutable
  tal como está. El alcance real es "reproducir NEWS2 con ACVPU y O2 imputados, y medir el
  efecto de la imputación".
- El motor NEWS2 de Python (tubería de datos) y el de PostgreSQL (producción) tienen que dar
  el **mismo** resultado ante la misma entrada. Se testean contra los mismos casos clínicos.
- En la app real **no se imputa nada**: los 7 parámetros son obligatorios y sin ellos no se
  guarda. La imputación vive solo en la tubería de datos históricos, y esa asimetría es
  deliberada — al pie de la cama el dato se pide, en un dataset de 2011-2019 no se puede.

---

## ADR-009 — Segunda cohorte: el dataset TRIAGE (Zenodo) junto a MIMIC-IV-ED
**Fecha:** 2026-09-30 · **Estado:** ✅ Aceptada

### Contexto
Al 2026-09-30 la credencial de PhysioNet (`SCRUM-48`) sigue sin llegar. La causa se
identificó ese día y **no era demora de PhysioNet**: la solicitud del 21/09 quedó en
*"Awaiting a response from reference"* porque el correo al referente se envió a un dominio
mal tipeado (`.com` en lugar de `.net`), así que nunca llegó. Se está corrigiendo, pero la
fecha de aprobación es incierta y el recuadro del **19/10** —comparativa del modelo contra
NEWS2— depende de tener una cohorte donde la comparación sea *medible*.

Sobre el demo abierto de MIMIC-IV-ED **no lo es**, y está documentado: el horizonte de 24 h
de la etiqueta v2 no discrimina (estadía mediana 5,8 h), la prevalencia resultante es del
66,8 % y colapsa a "el episodio terminó en internación". Se puede medir la **tasa de
alertas** de NEWS2 (`SCRUM-80`, hecho) pero **no su sensibilidad**, y sin sensibilidad no
hay "comparativa a sensibilidad igualada".

### Decisión
Se adopta como **segunda cohorte** el dataset del estudio TRIAGE
(`zenodo.org/records/4963759`, CC0, sin registro ni DUA): 1.303 pacientes adultos de
guardia de tres centros terciarios (EE.UU. 940, Francia 355, Suiza 8), con los componentes
de NEWS al ingreso, mortalidad a 30 días e ingreso a UCI.

**No reemplaza a MIMIC-IV-ED: lo complementa.** El reparto queda así:

| Pregunta | Cohorte |
|---|---|
| Tasa de alertas de referencia de NEWS2 | ambas |
| Sensibilidad de NEWS2 y comparativa a sensibilidad igualada (`SCRUM-58`) | **TRIAGE** |
| Baseline XGBoost sobre snapshot (`SCRUM-56`) | **TRIAGE** |
| Etiqueta v2 con ventana `(t+1h, t+24h]` (`SCRUM-53`) | **MIMIC** |
| Hipótesis de series de 48 h / LSTM (`SCRUM-57`) | **MIMIC**, sigue bloqueada |

### Razón
Verificado corriendo el motor NEWS2 del proyecto sobre el archivo, sin modificarlo:

- **1.300 de 1.303 filas puntuables.** Sólo 3 valores caen fuera de `RANGOS_PLAUSIBLES`,
  los mismos rangos que los CHECK de la base.
- **Tasa de alertas 25,7 %**, sensibilidad **53,7 %** para mortalidad a 30 días (29 de 54) y
  **47,3 %** para ingreso a UCI (80 de 169).

Esos números son la tesis del proyecto vuelta medible: NEWS2 alerta en una de cada cuatro
tomas y **se pierde casi la mitad de los eventos**. Sobre esa base sí se puede entrenar un
modelo, igualar la sensibilidad y comparar tasas de alerta.

Tres razones más:

1. **La prevalencia es real.** 4,2 % de mortalidad a 30 días, dentro de la banda 0,22–5 %
   del problema, contra el 66,8 % no interpretable del demo de MIMIC.
2. **Tiene el parámetro de consciencia.** La columna `confusion` (44 casos) es la "C" de
   NEWS2. Acá se imputa **un solo** parámetro —oxígeno suplementario— contra **dos** en
   MIMIC: el ADR-007 pesa la mitad.
3. **Es guardia, no UCI ni sala.** Es el encuadre del ADR-006, que excluye cohortes de UCI
   justamente porque NEWS2 pierde poder discriminativo ahí.

### Límites que se declaran en la tesis
- **No sirve para la LSTM.** Una toma por paciente: no hay serie temporal. `SCRUM-57` sigue
  dependiendo de la base completa de MIMIC, y eso NO cambia por este ADR.
- **El desenlace es otro.** Mortalidad a 30 días e ingreso a UCI desde el snapshot de
  admisión, no la ventana `(t+1h, t+24h]` de la etiqueta v2. Es el encuadre *snapshot* del
  ADR-005. Las dos definiciones conviven y **no se mezclan en una misma métrica**.
- **La población es otra.** 72 % de un único hospital de EE.UU. Generalizar a una guardia
  argentina es una limitación, no un resultado.
- **No hay validación externa fila por fila del motor.** El archivo trae los componentes de
  NEWS pero **no** la columna del score calculado, así que sólo se puede comparar contra los
  estadísticos que publica el estudio, no puntaje contra puntaje.
- **Es NEWS, no NEWS2.** Difieren en la escala 2 de SpO₂ para pacientes hipercápnicos y en
  el tratamiento de la confusión. La comparación se acota a los componentes compartidos.

### Consecuencias
- Nuevo módulo `ml_engine/src/data/triage.py` con el mismo tratamiento que `mimic_ed.py`:
  validación de esquema, rangos plausibles compartidos y pruebas.
- `xlrd` se suma a `requirements-dev.txt` (el archivo es `.xls` legacy).
- El ADR-002 queda **más** desactualizado: ya no hay "un dataset principal", hay dos
  cohortes con roles distintos. Reescribirlo es deuda pendiente.
- La licencia CC0 no exige atribución legal, pero el estudio **se cita igual** en la tesis.
