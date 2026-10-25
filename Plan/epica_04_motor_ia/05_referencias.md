# Referencias del encuadre

`SCRUM-83` · Épica 4 · Verificado el 25/10/2026

> **Qué es este documento.** Las fuentes de las cifras de literatura que sostienen el
> proyecto, cada una **verificada contra el texto original** (no contra un resumen) el
> 25/10/2026. Al verificarlas se encontró que una cifra no existía y que otras dos se
> citaban sin su alcance real; las correcciones están abajo y ya se aplicaron a los ADR y
> a los documentos de la épica.

---

## El trasfondo: la revisión de literatura

El encuadre salió de una revisión hecha con **NotebookLM** sobre un cuaderno de **141
fuentes**. Clasificadas por título, son aproximadamente:

| Tipo | Cantidad aprox. |
|---|---|
| Artículos científicos y bases de datos de investigación (PMC, BMJ, PLOS, medRxiv, PhysioNet…) | 45 |
| Normativa argentina (leyes 25.326 y 27.706, ANMAT) | 5 |
| Documentación técnica (HL7 FHIR, repositorios de datasets) | 9 |
| Sitios web y material de contexto (enfermería, burnout, mercado, apps) | el resto |

La clasificación es por título y no es exacta; sirve para dar una idea de la mezcla.

**Lo que aprendimos al verificar:** NotebookLM también es un modelo y no se le cree a
ciegas. Para cada cifra se le pidió la fuente y la frase textual, y después esa frase se
buscó **en el artículo original**. Una de las cuatro cifras ("el 83,7 % de los clínicos
considera inútiles las alertas") **no aparece en ninguna fuente**: era la resta de otro dato,
tomada de un informe generado dentro del propio cuaderno.

---

## Las cifras, verificadas

### 1. NEWS2 rinde peor en sepsis y COVID-19 en guardia

> Mhd Yunin NS, Tan TL. **National Early Warning Score 2 (NEWS2) as a prognostic tool for
> adult patients in emergency department: A retrospective observational study.** *PLoS ONE*.
> 2025;20(6):e0326058. doi:10.1371/journal.pone.0326058

- **Población:** 1.906 adultos en la guardia del Hospital Canselor Tuanku Muhriz (Malasia),
  un solo centro, retrospectivo.
- **En toda la cohorte** NEWS2 rinde bien (umbral ≥ 5): AUROC 0,71 para internación, 0,75
  para cuidados críticos y **0,86 para mortalidad**.
- **Sepsis** (159 pacientes, 8,3 %): *"However, the predictive capability for mortality was
  lower, with an AUROC of 0.66 (95% CI: 0.54–0.77)."*
- **COVID-19** (40 pacientes, 2,1 %): AUROC **0,59 (IC 95 %: 0,28–0,89) para mortalidad**
  intrahospitalaria.

**Corrección.** Los ADR decían "AUROC 0,66 en sepsis" como si fuera el rendimiento general
en ese subgrupo. Es el AUROC **para mortalidad**: para predecir internación en sepsis el
mismo estudio da 0,97. Y el 0,59 de COVID-19 sale de **40 pacientes**, con un intervalo de
0,28 a 0,89: es compatible con casi cualquier valor y no alcanza para afirmar nada fuerte.

### 2. La carga de alertas de NEWS2

> Pankhurst T, Sapey E, Gyves H, Evison F, Gallier S, Gkoutos G, Ball S. **Evaluation of
> NEWS2 response thresholds in a retrospective observational study from a UK acute
> hospital.** *BMJ Open*. 2022;12(2):e054027. doi:10.1136/bmjopen-2021-054027

- **Población:** 100.362 internaciones consecutivas de adultos, noviembre 2018 – julio 2019,
  en un hospital de agudos de Inglaterra (Birmingham).
- *"The sensitivity of outcome prediction at Index-NEWS2 ≥5=0.46, and number needed to
  evaluate (NNE)=52. At this threshold, a mean of 37.6 alerts/100 patient-days would be
  generated, occurring in 12.3% of patients on any single day."*
- El desenlace es muerte o ingreso a terapia intensiva dentro de las 24 h de un puntaje.

**Bien citada.** Vale agregar el contexto que no se estaba diciendo: a ese umbral NEWS2
detecta **menos de la mitad** de los desenlaces (sensibilidad 0,46), y hay que evaluar a 52
pacientes por cada uno que realmente lo tiene.

### 3. Cómo perciben los clínicos las alertas de sepsis

> Hijjawi S, Ssentongo P. **Evaluation of sepsis CDS tool knowledge and utilization among
> graduate medical trainees: insights to inform redesign in an academic health system.**
> *Frontiers in Medicine*. 2026;12:1660390. doi:10.3389/fmed.2025.1660390
> (el artículo tiene una corrección publicada: *Front Med*. 2026;13:1788147).

- **Población:** encuesta a residentes y fellows de un solo centro académico (Penn State,
  EE.UU.), marzo de 2022. Respondieron 92 de 673 (13,7 %).
- *"Only 16.3% felt both tools were helpful, while 52.5% found them unhelpful."* El 16,3 %
  es sobre los 80 que conocían la alerta, y se refiere a **las dos herramientas juntas**
  (la alerta y el asistente de sepsis). La alerta sola fue considerada inútil por el 77,5 %.
- La fatiga de alertas fue la queja principal: 62,5 %.

**Corrección.** El "83,7 % de los clínicos considera inútiles las alertas actuales" **no
existe en ninguna fuente**: era 100 − 16,3. Y aun como resta estaba mal, porque mezclaba "no
encontró útiles las dos herramientas" con "las encontró inútiles", y generalizaba a todos
los clínicos y a todas las alertas lo que es una encuesta de 80 residentes sobre alertas de
sepsis en un hospital. Lo que sí se puede decir es lo de arriba, con su alcance.

### 4. El snapshot alcanza (ADR-005)

> Zhang Z, Wei J, Xu J, Li Y, Luk A, Bhalla S, Cui H, Clifton DA, Walker AS, Eyre DW.
> **Less is More: last observations of vital signs can outperform time series for hospital
> mortality prediction.** *medRxiv* (preprint, sin revisión por pares). 2026.
> doi:10.64898/2026.05.05.26352366

- **Población:** 443.807 internaciones de 226.986 adultos en los 4 hospitales de Oxford
  University Hospitals, 2016–2024. Desenlace: muerte dentro de las 24 h.
- AUROC con signos vitales solos: **NEWS2 0,908**, **XGBoost con la última observación
  0,925**, LSTM con 48 h de historia 0,924, Transformer 0,921.

**Bien citada.** Falta aclarar que es un **preprint**: no pasó revisión por pares.

---

## Las otras fuentes que usa el proyecto

- **NEWS2.** Royal College of Physicians. *National Early Warning Score (NEWS) 2:
  Standardising the assessment of acute-illness severity in the NHS.* Updated report of a
  working party. London: RCP; 2017.
- **Cohorte TRIAGE** (el modelo en producción). Eckart A, Hauser S, Kutz A, Haubitz S,
  Hausfater P, Amin D, Amin A, Huber A, Mueller B, Schuetz P. *Data from: Combination of the
  National Early Warning Score (NEWS) and inflammatory biomarkers for early risk
  stratification in emergency department patients: results of a multi-national,
  observational study.* Dryad / Zenodo; 2018. doi:10.5061/dryad.d22q6vh. Licencia CC0.
  1.303 pacientes de guardia de tres centros (EE.UU., Francia, Suiza), 54 muertes a 30 días.
- **MIMIC-IV-ED Demo** (tubería de datos y tasa de alertas de referencia). Johnson A,
  Bulgarelli L, Pollard T, Celi LA, Mark R, Horng S. *MIMIC-IV-ED Demo* (version 2.2).
  PhysioNet; 2023. Licencia ODbL, que exige esta atribución.

---

## Dónde se corrigió

| Archivo | Qué cambió |
|---|---|
| `Plan/02_DECISIONES_TECNICAS.md` | ADR-005: se reemplaza el 83,7 % y se citan Pankhurst, Hijjawi y "Less is More" (preprint). ADR-006: el 0,66 y el 0,59 son para mortalidad, con el tamaño de cada subgrupo |
| `Plan/epica_04_motor_ia/03_marco_teorico.md` | Las dos marcas `[FUENTE PENDIENTE]` reemplazadas por la cita |
| `Plan/epica_04_motor_ia/01_definicion_etiqueta.md` | Alcance del 0,66 y el 0,59 |
| `Plan/epica_04_motor_ia/02_caveat_news2_urgencias.md` | El aviso de "pendiente" pasa a resuelto |
| `ml_engine/src/data/alertas.py` | La constante del 37,6 lleva su cita |
