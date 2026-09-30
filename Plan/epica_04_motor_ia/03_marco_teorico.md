# 📚 Épica 4 — Marco teórico de la tesis (SCRUM-76)

> **v1 — 2026-09-30.** Primer borrador completo. Integra la revisión de literatura que
> fundó los ADR con las mediciones propias obtenidas entre el 21 y el 30 de septiembre.
>
> **Estado de las citas:** las afirmaciones respaldadas por mediciones propias llevan al
> lado el archivo que las reproduce. Las que vienen de literatura están marcadas con
> **[FUENTE PENDIENTE]** y son trabajo de `SCRUM-83`. **No se completó ninguna referencia
> de memoria**: un número con una cita inventada es peor que un número sin cita.

---

## 1 · El problema clínico

El deterioro fisiológico de un paciente internado rara vez es súbito. En las horas previas
a un paro cardiorrespiratorio, un ingreso no planificado a terapia intensiva o la muerte,
los signos vitales suelen mostrar alteraciones detectables. Esa ventana —entre el momento
en que el deterioro se vuelve medible y el momento en que se vuelve crítico— es la
oportunidad sobre la que opera cualquier sistema de alerta temprana.

El problema no es que la información no exista: está en la planilla de signos vitales. El
problema es **reconocerla a tiempo y actuar**, en un entorno donde el personal de enfermería
atiende a muchos pacientes simultáneamente y donde la señal está mezclada con ruido.

De ahí nacen los *early warning scores*: convertir varios parámetros fisiológicos en un
número único que dispare una respuesta escalonada.

---

## 2 · NEWS2 como estándar de referencia

### Qué es

El **National Early Warning Score 2** (Royal College of Physicians) agrega **siete
parámetros** en un puntaje de 0 a 20:

| Parámetro | Rango de puntaje |
|---|---|
| Frecuencia respiratoria | 0–3 |
| Saturación de oxígeno (SpO₂) | 0–3 |
| Oxígeno suplementario | 0 o 2 |
| Temperatura | 0–2 |
| Presión arterial sistólica | 0–3 |
| Frecuencia cardíaca | 0–3 |
| Nivel de consciencia (ACVPU) | 0 o 3 |

Dos detalles de la escala importan para este trabajo y suelen pasarse por alto:

- **La "C" de confusión nueva puntúa 3**, igual que las tres peores respuestas de la escala.
  Es la diferencia entre ACVPU y el AVDI clásico.
- **La escala 2 de SpO₂** aplica a pacientes con hipercapnia crónica y **es una prescripción
  médica**, no una inferencia a partir del oxígeno suplementario. En Zaha vive en
  `encounters` y se copia a cada toma para reproducibilidad histórica (ADR-001).

### La regla de alerta no es un umbral simple

Éste es el punto que más trabajo costó y el que más condiciona toda comparación posterior.
NEWS2 no alerta sólo por puntaje total: **un solo parámetro en 3 puntos dispara respuesta
aunque el total sea bajo** — el llamado *rojo aislado*. Un paciente con frecuencia
respiratoria de 6 necesita atención inmediata, sume lo que sume el resto.

Zaha implementa esa regla en el trigger `emit_news2_alert`: alerta cuando el nivel de riesgo
es distinto de *Bajo*. Medido sobre la cohorte de MIMIC-IV-ED, la diferencia frente a usar
`score ≥ 5` **no es menor**:

| Regla | Tomas que alertan |
|---|---|
| Real del sistema (`riesgo ≠ Bajo`) | **11,2 %** (62 de 553) |
| `score ≥ 5` | 5,2 % (29 de 553) |

*Más del doble.* → `notebooks/06_baseline_news2.ipynb`

Cualquier trabajo que compare un modelo contra "NEWS2" sin especificar cuál de las dos
reglas usó está comparando contra un objeto mal definido.

---

## 3 · Los tres límites de NEWS2 que fundan este trabajo

### 3.1 · Fue diseñado para sala general, no para guardia

NEWS2 asume un paciente **ya internado**, con basal conocido y controles cada 4–12 h. La
guardia rompe los tres supuestos: no hay basal, la estadía mediana es de horas y la
población mezcla al paciente que se va de alta en dos horas con el que entra en shock.

La literatura documenta caídas en subgrupos de urgencias —AUROC 0,66 en sepsis y 0,59 en
COVID-19— atribuidas a hipoxemia silenciosa e hiperlactatemia que la escala no integra
**[FUENTE PENDIENTE — `SCRUM-83`]**.

**Medición propia**, con el mismo motor que corre en producción, sobre 1.300 pacientes de
guardia de tres centros terciarios (cohorte TRIAGE, ADR-009):

| | Valor |
|---|---|
| AUROC — mortalidad a 30 días | **0,728** |
| AUROC — ingreso a UCI | **0,650** |
| Sensibilidad — mortalidad a 30 días | **53,7 %** (29 de 54) |
| Sensibilidad — ingreso a UCI | **47,3 %** (80 de 169) |
| Tasa de alertas | **25,7 %** de las admisiones |

→ `notebooks/07_news2_en_triage.ipynb`

**En una línea: NEWS2 alerta en una de cada cuatro admisiones y aun así se pierde casi la
mitad de las muertes.** Ése es el hueco que este trabajo intenta llenar.

### 3.2 · La fatiga de alertas

El costo de un sistema de alerta no es sólo lo que no detecta, sino lo que interrumpe sin
motivo. La literatura del proyecto reporta que NEWS2 con umbral ≥ 5 genera **37,6 alertas
por 100 pacientes-día**, afecta al **12,3 % de los pacientes diariamente**, y que el
**83,7 % de los clínicos considera inútiles las alertas actuales**
**[FUENTE PENDIENTE — `SCRUM-83`]**.

**Advertencia metodológica que este trabajo aporta.** La tasa por paciente-día **depende de
cada cuánto se mide**, no sólo de cuánto alerta la escala. Sobre MIMIC-IV-ED la medición
propia da 82,8 por 100 pacientes-día —2,2 veces la referencia de sala— pero allí se toman
**7,4 mediciones puntuables por paciente-día** contra 2–4 en una sala con control cada 6 o
12 h. Buena parte de la diferencia es **diseño de la medición**, no comportamiento de la
escala.

Por eso la comparativa de este trabajo usa el denominador **por toma**, donde la frecuencia
se cancela de los dos lados. → `src/data/alertas.py`

### 3.3 · El margen de precisión es marginal

Un estudio de cohorte a gran escala reporta **[FUENTE PENDIENTE — `SCRUM-83`]**:

| Modelo | AUROC |
|---|---|
| NEWS2 solo | 0,908 |
| XGBoost (sólo última observación) | **0,925** |
| LSTM (series 12–48 h) | 0,924 |
| Transformer | 0,921 |

Dos lecturas, y las dos incomodan:

1. **El margen sobre NEWS2 es de ~1,7 puntos de AUROC.** Una tesis cuya afirmación central
   fuera "mi modelo le gana a NEWS2 en AUROC" produciría un resultado marginal.
2. **La arquitectura temporal no aporta.** XGBoost sobre el *snapshot* iguala a redes que
   procesan 48 h de historia.

---

## 4 · Estado del arte en aprendizaje automático sobre deterioro

### El consenso: la complejidad no paga

La evidencia converge en que, para este problema, los modelos de árboles sobre el snapshot
actual igualan a las arquitecturas secuenciales. La explicación razonable es que **el estado
fisiológico presente ya contiene casi toda la información predictiva**, y la trayectoria
agrega poco por encima de eso.

Este trabajo trata esa afirmación como **hipótesis bajo prueba** y no como premisa: si la
LSTM no aporta, *eso también es un resultado reportable* (ADR-005). Al 30/09/2026 la
hipótesis sigue sin poder contrastarse por falta de datos con serie temporal y desenlace
real.

### Un matiz propio: a muestra chica, gana el modelo simple

La literatura citada se midió sobre cohortes de decenas de miles de episodios. Sobre 1.300
pacientes con 54 eventos, el orden se invierte:

| Modelo | AUROC fuera de fold |
|---|---|
| XGBoost, 300 árboles, profundidad 3 | 0,613 |
| XGBoost, 60 árboles, profundidad 2 | 0,728 |
| XGBoost, 30 árboles, profundidad 1 | 0,733 |
| **Regresión logística, sin ajustar** | **0,759** |
| NEWS2 | 0,728 |

→ `src/models/baseline.py`, ADR-010

Hay que bajarle la capacidad a XGBoost hasta casi nada para que *empate* con NEWS2,
mientras que una regresión logística sin ningún ajuste le gana. **Con 54 eventos y 7
features, la capacidad de un ensamble de árboles se gasta en sobreajustar.**

No contradice a la literatura: la matiza. "El snapshot alcanza" no implica "XGBoost siempre
gana"; implica que la arquitectura importa menos que los datos.

---

## 5 · El reencuadre: de la precisión a la carga de alertas

De las tres secciones anteriores se sigue el reencuadre del **ADR-005**:

> **Igualar la sensibilidad de NEWS2 reduciendo sustancialmente la tasa de alertas.**

Detectar lo mismo molestando menos es clínicamente más valioso que 1,7 puntos de AUROC, y
conecta directo con la sobrecarga cognitiva del personal, que es la justificación original
del proyecto.

### Cómo se mide una comparación así, sin hacer trampa

Cuatro decisiones, cada una porque la alternativa ingenua produce un número inflado:

**a. Contra el rival correcto.** Hay dos formas de usar NEWS2 —la regla desplegada y el
mejor umbral de score— y **no son equivalentes**. Sobre mortalidad a 30 días el mejor umbral
le gana a la regla desplegada, así que compararse contra la regla daría una ventaja
prestada. Se compara contra el rival más fuerte.

**b. Sobre un rango, no sobre un punto.** El score de NEWS2 es entero y su curva de
operación avanza a escalones grandes. Una sensibilidad única cae, según la suerte, justo
antes o justo después de un escalón:

| Dónde se mide | Reducción de alertas |
|---|---|
| En el punto donde opera el sistema (53,7 %) | **+2,7 %** |
| Promedio sobre el rango 50–80 % | **+29,8 %** |

Sin que nada del modelo haya cambiado. El punto único **no es un estimador estable** cuando
el rival es discreto. → `notebooks/08_comparativa_tasa_alertas.ipynb`

**c. Con un estimador insesgado.** NEWS2 no se ajusta sobre estos datos, así que su AUROC es
insesgado; cualquier configuración propia elegida mirando el CV está inflada. Por eso la
selección de familia ocurre **dentro** del bucle de evaluación (validación cruzada anidada).

**d. Con intervalo de confianza.** Un porcentaje sin intervalo, sobre 54 eventos, es
precisión falsa.

---

## 6 · Decisiones metodológicas que condicionan la validez

Las cuatro que más pesan, todas documentadas en sus propios ADR y con código verificable:

**La etiqueta no mira el NEWS2.** `y = 1` si el desenlace adverso ocurre en `(t+1h, t+24h]`,
construida sólo con el desenlace y los tiempos. Usar "NEWS2 ≥ 7" como etiqueta sería
circular: el modelo aprendería a reproducir la escala que se quiere superar.
→ `01_definicion_etiqueta.md`

**Hay ventana ciega, y las tomas que caen ahí se descartan, no se ponen en 0.** Una toma
veinte minutos antes del ingreso a UCI es trivial de clasificar y sólo inflaría métricas.
Marcarla como 0 sería peor: enseñarle al modelo que un paciente que se descompensa está
sano.

**La partición es por paciente, nunca por fila.** Un mismo paciente aparece en varias tomas
y varios episodios; en el demo de MIMIC hay 222 episodios de apenas 64 pacientes, y uno
solo aporta 23. → `src/data/particiones.py`

**La imputación sesga hacia abajo, a propósito.** MIMIC-IV-ED no registra consciencia ni
oxígeno suplementario en ninguna fila; se imputan al valor de menor riesgo (ADR-007), así
que el NEWS2 calculado **nunca sobreestima**. El sesgo juega **en contra** de la hipótesis
del proyecto: si la tasa real del rival fuera más alta, superarlo sería más fácil. Reportar
el piso pone la vara más alta.

---

## 7 · El vacío que este trabajo aborda, y lo que todavía no puede afirmar

### La hipótesis

> Un modelo entrenado únicamente con los parámetros disponibles al pie de la cama puede
> igualar la sensibilidad de NEWS2 reduciendo sustancialmente su tasa de alertas.

La restricción a parámetros de cabecera es parte de la hipótesis, no una limitación: un
modelo que necesitara biomarcadores de laboratorio sería indesplegable en el flujo de
trabajo que Zaha implementa, y compararlo contra NEWS2 —que sólo usa signos vitales— sería
tramposo.

### El estado al 30/09/2026

| | Resultado |
|---|---|
| Discriminación del modelo | **AUROC 0,771** vs 0,728 de NEWS2 (CV anidada) |
| Reducción de alertas (rango 50–80 %) | **29,8 %** |
| Intervalo de confianza 95 % | **[−8,5 %, +44,7 %]** |

**El intervalo incluye el cero.** La reducción es consistente pero **no está demostrada**.
Afirmar "reduce un 30 % las alertas" sin el intervalo sería sobrevender el trabajo.

### Por qué, y cuánto falta

El límite no es la capacidad del modelo sino **cuántos eventos tiene la cohorte**. Una
simulación por remuestreo indica que el intervalo dejaría de cruzar el cero con
aproximadamente **el doble** de la cohorte actual —unos 108 eventos, del orden de 2.600
pacientes—. La base completa de MIMIC-IV-ED tiene ~425.000 episodios, así que sobra
holgadamente.

> **El acceso a los datos deja de ser un trámite administrativo y pasa a ser la condición
> para que la afirmación central de la tesis pase de "consistente" a "demostrada".**

### Limitaciones a declarar

- **Una sola cohorte y chica.** 1.300 pacientes, 54 muertes. Los intervalos son anchos.
- **La población no es argentina.** 72 % de un único hospital de EE.UU., 27 % de París.
- **Es NEWS, no NEWS2** en la cohorte donde se mide la sensibilidad: difieren en la escala 2
  de SpO₂ y en el tratamiento de la confusión.
- **Sin validación externa del motor.** Los 21 casos clínicos son de construcción propia,
  derivados de la especificación. Nadie comparó este motor contra puntajes publicados por un
  tercero.
- **Los subgrupos de sepsis y respiratorio no se analizaron por separado**, como pedía el
  ADR-006: la cohorte no trae diagnóstico.
- **La hipótesis temporal sigue sin contrastarse.** Ninguna cohorte disponible tiene serie
  temporal *y* desenlace real con prevalencia interpretable.

---

## 8 · Deuda de este documento

1. **`SCRUM-83` — completar las citas.** Las cinco cifras marcadas **[FUENTE PENDIENTE]**
   sostienen el encuadre entero. Los ADR salieron de una revisión con NotebookLM sobre 300+
   fuentes, así que las referencias deberían poder recuperarse de ahí. **Ninguna se completó
   de memoria a propósito.**
2. **Validación externa del motor NEWS2.** Candidato concreto: los estadísticos publicados
   del propio estudio TRIAGE.
3. **El encuadre regulatorio** (SaMD, disposición ANMAT 9688/19) es `SCRUM-73` y va en su
   propio capítulo; acá sólo se lo menciona.
4. **Actualizar la §7 cuando llegue MIMIC completo.** Es la sección que cambia de "no
   demostrado" a un resultado, en un sentido o en el otro.

---

## Dónde se reproduce cada número

| Afirmación | Fuente reproducible |
|---|---|
| Regla de alerta y su diferencia contra `score ≥ 5` | `notebooks/06_baseline_news2.ipynb` |
| AUROC y sensibilidad de NEWS2 en guardia | `notebooks/07_news2_en_triage.ipynb` |
| Comparativa e intervalo de confianza | `notebooks/08_comparativa_tasa_alertas.ipynb` |
| Tabla de familias de modelo | `src/models/baseline.py`, ADR-010 |
| Caveat de NEWS2 en urgencias, ampliado | `02_caveat_news2_urgencias.md` |
| Definición de la etiqueta | `01_definicion_etiqueta.md` |

ADR relacionados: **002** (datasets, desactualizado), **005** (el reencuadre), **006**
(caveat de guardia), **007** (imputación), **009** (segunda cohorte), **010** (qué modelo es
el principal).
