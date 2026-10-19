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

## ADR-002 — Datasets: de qué datos aprende el motor
**Fecha:** 2026-08-25 · **Revisada:** 2026-10-19 · **Estado:** 🔄 Superada en lo principal
por el ADR-009. Se conserva como historia de la decisión: qué se planeó, qué se encontró y
dónde quedó.

### Lo que se decidió el 25/08
- **Principal:** `MIMIC-IV-ED` (módulo de guardia), tabla `vitalsign`.
- **Andamio:** un dataset de Kaggle, para construir la tubería mientras llegaba el acceso.
- **Descartado:** MIMIC-IV completo (`chartevents`), porque es terapia intensiva: ahí casi
  todos puntúan alto en NEWS2 y la escala pierde poder discriminativo.

La razón era que MIMIC-IV-ED tenía la población correcta (guardia), "mediciones repetidas de
casi exactamente los parámetros NEWS2" y desenlaces limpios. Esa frase resultó falsa.

### Lo que se encontró
1. **El Kaggle no servía ni de andamio** (09/09): 200.020 filas de 200.020 pacientes, una
   toma cada uno, sin ACVPU ni oxígeno suplementario y con un desenlace sintético. Se
   reemplazó por el **demo abierto de MIMIC-IV-ED** (ODbL, sin credencial), que tiene el
   mismo esquema que la base completa.
2. **MIMIC-IV-ED tiene 5 de los 7 parámetros de NEWS2** (09/09, ADR-007): no registra
   consciencia ni oxígeno suplementario, ni en el demo ni en la base completa. Se imputan
   con el valor de menor riesgo, y el sesgo queda siempre en contra de la hipótesis.
3. **Sobre el demo, la tesis no es medible** (15/09): con una estadía mediana de 5,8 h, la
   etiqueta de 24 h no discrimina y colapsa a "el episodio terminó en internación". Se
   puede medir la tasa de alertas de NEWS2, pero no su sensibilidad.
4. **PhysioNet rechazó la credencial** (04/10). Antes, una solicitud quedó trabada porque el
   correo al referente se mandó a un dominio mal tipeado.

### Dónde quedó
| Uso | Fuente |
|---|---|
| El modelo en producción y la comparativa contra NEWS2 | **TRIAGE** (Zenodo, CC0), ADR-009 |
| La tubería de datos, la tasa de alertas de referencia y las pruebas | **Demo de MIMIC-IV-ED** |
| La base completa de MIMIC-IV-ED | Sin acceso. La tubería corre sobre ella con `--origen` el día que llegue |

**Lo que sigue valiendo de la decisión original:** que el dato tiene que ser de guardia o
sala, no de terapia intensiva. TRIAGE cumple: son pacientes de guardia de tres centros.

**Lo que se perdió:** las series temporales. TRIAGE tiene una sola toma por paciente, así
que la hipótesis de la LSTM no se puede probar
(`Plan/epica_04_motor_ia/04_caveat_lstm.md`).

### Lección
La frase que sostuvo la decisión —"casi exactamente los parámetros NEWS2"— se escribió sin
abrir los archivos. Las tres decisiones siguientes (ADR-006, 007 y 009) salieron de
verificar sobre los datos lo que esta daba por supuesto.

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

## ADR-008 — Bitácora de auditoría en dos capas: prevención y detección
**Fecha:** 2026-09-10 (implementada en `SCRUM-72`) · **Escrita:** 2026-10-19 ·
**Estado:** ✅ Aceptada

### Contexto
`vital_records` es append-only desde la Épica 2, pero `alerts` **sí se actualiza**: guarda
el estado final de cada alerta, no su historia. Eso dejaba tres agujeros:

1. Una alerta reconocida queda con quién y cuándo, pero no con que antes estuvo pendiente
   ni con cuánto tardó en atenderse, que es lo primero que mira una auditoría clínica.
2. La protección de `alerts` arrancaba con `IF auth.uid() IS NULL THEN RETURN NEW`: con la
   clave de servicio se podía reescribir cualquier alerta, y la fila resultante era
   indistinguible de una legítima.
3. Nada permitía detectar que una fila se hubiera alterado por fuera de la aplicación.

La Ley 25.326 (art. 9) exige medidas contra la adulteración de datos de salud, y "es
inalterable porque la app no tiene un botón para alterarlo" no es una medida.

### Decisión
Una tabla aparte, `alert_audit_log`, que registra cada evento de cada alerta —emitida,
reconocida, descartada, pospuesta— con **dos capas**, porque en una base de datos la
prevención absoluta no existe: quien tiene privilegios de dueño puede desactivar un trigger.

**Prevención: append-only de verdad.**
- Sin permiso de `UPDATE` ni `DELETE` para ningún rol, ni por `GRANT` ni por política RLS.
- Un trigger rechaza `UPDATE` y `DELETE` **sin** la excepción de `auth.uid()`: tampoco la
  clave de servicio puede.
- La escribe **la base, no la aplicación**: un trigger sobre `alerts` registra el evento. Si
  dependiera de que el cliente se acuerde, el log valdría lo que la buena fe del cliente.
- La función que escribe el log no está expuesta en la API para nadie.

**Detección: cadena de hashes.**
- Cada fila guarda `hash = sha256(hash_previo | contenido canónico)`. Borrar una fila,
  insertar una en el medio o modificar una rompe la cadena de ahí en adelante.
- `verificar_cadena_auditoria()` recalcula cada eslabón y devuelve el primero que no cierra.
  No impide la manipulación: **la vuelve evidente**, que es lo que necesita un registro con
  valor probatorio.
- Un lock de transacción serializa las inserciones: sin él, dos eventos simultáneos se
  encadenarían al mismo eslabón y la verificación fallaría sobre datos legítimos.

**Lo que guarda cada evento:** quién (o `actor_es_sistema`, que no es lo mismo que "no se
sabe quién"), el estado anterior y el nuevo, la nota, una **copia congelada** de la alerta
en ese momento, y si la fila es *backfill*. Las alertas anteriores al log se cargaron
marcadas como tales: afirmar que se observó lo que no se observó invalida un registro de
auditoría.

### Estado verificado
El 19/10/2026, en producción: `verificar_cadena_auditoria()` devuelve **cadena íntegra, 22
eventos** (17 emitidas, 3 pospuestas, 1 reconocida, 1 descartada; 13 de backfill).

### Límites, dichos
- **La cadena se puede rehacer entera.** Quien tenga privilegios de dueño puede desactivar
  el trigger, alterar filas y **recalcular todos los hashes desde el principio**: la
  verificación no lo notaría, porque no hay contra qué comparar. La mitigación conocida es
  anclar el último hash afuera —publicarlo periódicamente en un lugar que la base no
  controla— y **no está implementada**. Va a la gestión de riesgos (`SCRUM-75`).
- **No cubre `vital_records`**, que es append-only por su propio diseño pero no está
  encadenada.
- La verificación la puede correr cualquier usuario con sesión, a propósito: es lo que la
  hace auditable. Devuelve un resumen, nunca filas (ver
  `Plan/epica_06_regulatorio/02_seguridad_supabase.md`).

### Trampa pagada
Al crear una función, Postgres le da `EXECUTE` a `PUBLIC`. `GRANT EXECUTE ... TO
authenticated` no restringe nada: solo repite lo que ya estaba, y la función quedaba
expuesta en la API **incluso para un anónimo**. Lo marcó el linter de Supabase y se corrigió
con `REVOKE ... FROM PUBLIC, anon` en la migración `20260910193000`.

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

---

## ADR-010 — Qué modelo es el principal depende del tamaño de muestra (refina ADR-005)
**Fecha:** 2026-09-30 · **Estado:** ✅ Aceptada

### Contexto
El **ADR-005** fija la progresión de modelado y declara: *"XGBoost sobre snapshot (última
observación + estáticas) ← modelo principal"*. Se apoyaba en literatura —"Less is More"—
que muestra que XGBoost sobre el snapshot iguala a redes que procesan 48 h de historia.

Al entrenar de verdad sobre la cohorte TRIAGE (`SCRUM-56`), con **54 eventos**, eso no se
sostuvo. Medido con validación cruzada repetida:

| Modelo | AUROC fuera de fold |
|---|---|
| XGBoost, 300 árboles, profundidad 3 | 0,613 |
| XGBoost, 60 árboles, profundidad 2 | 0,728 |
| XGBoost, 30 árboles, profundidad 1 | 0,733 |
| **Regresión logística, sin ajustar** | **0,759** |
| NEWS2 (el rival) | 0,728 |

Hay que bajarle la capacidad a XGBoost hasta casi nada para que **empate** con NEWS2,
mientras que una regresión logística sin ningún ajuste le gana. Con validación cruzada
**anidada** —la selección de familia ocurre dentro del bucle de evaluación— el resultado se
confirma: **AUROC 0,771**, y los **5 folds externos eligen la logística sin excepción**.

### Decisión
**El modelo principal no se fija por ADR: lo elige la validación cruzada anidada entre un
catálogo de familias.** El catálogo vive en `ml_engine/src/models/baseline.py` (`MODELOS`) e
incluye la regresión logística junto a tres configuraciones de XGBoost.

A la escala actual (1.300 pacientes, 54 eventos) el modelo elegido es la **regresión
logística**, y es la que se exporta a ONNX en `SCRUM-59`.

### Razón
No es que XGBoost sea peor en general: la literatura del ADR-005 se midió sobre cohortes de
decenas de miles de episodios. Es que **con 54 eventos y 7 features, la capacidad de un
ensamble de árboles se gasta en sobreajustar**. La lectura correcta del ADR-005 es "a escala
suficiente el snapshot alcanza", no "XGBoost siempre gana".

Fijar la familia por decreto tenía además un problema de método: si el ADR dice XGBoost, la
regresión logística nunca compite y el resultado —que el modelo simple gana— no se descubre.
Dejarlas competir dentro del bucle es lo que permitió encontrarlo.

Y hay una asimetría que obliga a la CV anidada: **NEWS2 no se ajusta sobre estos datos**, así
que su AUROC es insesgado. Cualquier configuración elegida mirando el CV está inflada, de
modo que un modelo que sólo *empata* con NEWS2 tras ajustarlo es en realidad **peor**.

### Consecuencias
- **El ADR-004 también queda desactualizado en su detalle**: planeaba "PyTorch → ONNX" y el
  artefacto real es `scikit-learn → ONNX` vía `skl2onnx`. La decisión de fondo —servir ONNX
  y no el framework de entrenamiento— sigue intacta y es la que importaba.
- **Se exporta el pipeline completo**, no sólo el clasificador: imputación, escalado y
  regresión en un solo grafo. Si la API reimplementara el escalado, cualquier diferencia
  produciría predicciones distintas sin que nada falle.
- **Esto puede volver a cambiar.** Cuando llegue la base completa de MIMIC (`SCRUM-48`), con
  varios órdenes de magnitud más eventos, es esperable que XGBoost vuelva a ganar. El
  catálogo está armado para que ese cambio sea un resultado de la CV y no una edición
  manual: no hay que tocar nada, sólo volver a correr.
- La elección quedó registrada en el sidecar de metadatos que viaja con el `.onnx`.
