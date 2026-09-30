# 🩺 Épica 4 — Paso 1: El rendimiento de NEWS2 en urgencias (SCRUM-60)

> **v1 — 2026-09-30.** Desarrolla el caveat que el **ADR-006** dejó enunciado. La novedad
> respecto de ese ADR es que ahora **hay mediciones propias**: hasta hoy la afirmación
> descansaba en literatura sobre otras poblaciones; ahora está medida sobre una cohorte de
> guardia con el mismo motor que corre en producción.
>
> **Es el supuesto que justifica el proyecto entero.** Si NEWS2 rindiera bien en guardia, no
> habría nada que mejorar y Zaha no tendría razón de ser.

---

## La afirmación, en una oración

**NEWS2 fue diseñado y validado para sala general, y en guardia rinde peor: alerta mucho y
se pierde alrededor de la mitad de los eventos.**

---

## Por qué era esperable antes de medirlo

NEWS2 es una escala de *track and trigger* pensada para un paciente **ya internado**, al que
se controla cada 4–12 h y cuyo estado basal se conoce. La guardia rompe los tres supuestos:

1. **No hay basal.** El paciente llega por primera vez; una taquicardia de 110 puede ser su
   normal o el inicio de un shock, y la escala no puede distinguirlas.
2. **La ventana es corta.** La estadía mediana en la cohorte de MIMIC-IV-ED medida por este
   proyecto es de **5,8 h**. Una escala pensada para detectar una tendencia a lo largo de
   días tiene poco margen.
3. **La población es otra.** En guardia conviven el paciente que se va de alta en dos horas
   y el que entra en shock séptico. En sala, la mezcla es mucho más homogénea.

El **ADR-006** ya registraba, desde la literatura, que NEWS2 cae en subgrupos específicos de
urgencias —sepsis y COVID-19— por hipoxemia silenciosa e hiperlactatemia que la escala no
integra.

> ⚠️ **Pendiente de la tesis:** las cifras de literatura que arrastra el ADR-006 (AUROC 0,66
> en sepsis, 0,59 en COVID-19, y las 37,6 alertas por 100 pacientes-día de referencia) están
> anotadas sin su fuente. **Hay que recuperar las citas exactas antes de la entrega final**:
> un número sin referencia no se puede defender, y estos tres sostienen el encuadre.

---

## Lo que medimos nosotros

Todo lo que sigue sale de correr **el mismo motor NEWS2 que usa la app** sobre la cohorte
TRIAGE (ADR-009): 1.300 pacientes adultos de guardia, con desenlaces reales.

### Discriminación

| Desenlace | AUROC de NEWS2 |
|---|---|
| Mortalidad a 30 días | **0,728** |
| Ingreso a UCI | **0,650** |

No es un motor mal implementado: pasa sus 21 casos clínicos. Es la escala, que rinde así en
este entorno.

### El punto de operación real del sistema

Aplicando la regla que **efectivamente dispara** en producción (`risk_level != 'Bajo'`, que
incluye el rojo aislado — ver `SCRUM-80`):

| | Valor |
|---|---|
| Tasa de alertas | **25,7 %** de las admisiones |
| Sensibilidad — muerte a 30 días | **53,7 %** (29 de 54) |
| Sensibilidad — ingreso a UCI | **47,3 %** (80 de 169) |
| Especificidad | 75,5 % / 77,5 % |

**Leído en una línea: NEWS2 grita en una de cada cuatro admisiones y aun así se pierde casi
la mitad de las muertes.** Ése es el hueco que el proyecto quiere llenar, y ahora es un
número propio en lugar de una cita.

### Sobre la tasa de alertas, una trampa que hay que desactivar

Sobre la cohorte de MIMIC-IV-ED la tasa por paciente-día da **82,8**, contra las 37,6 de la
referencia de sala. Es tentador titular *"NEWS2 alerta el doble en guardia"* y **sería un
error**: en esa cohorte se mide **7,4 veces por paciente-día**, contra 2–4 en una sala con
control cada 6 o 12 h. Buena parte de la diferencia es **diseño de la medición**, no
comportamiento de la escala.

Por eso la comparativa de `SCRUM-58` usa el denominador **por toma**, donde la frecuencia se
cancela de los dos lados.

### El número es un piso, no una estimación

MIMIC-IV-ED no registra consciencia ni oxígeno suplementario en ninguna fila, así que el
ADR-007 los imputa al valor de menor riesgo. El NEWS2 calculado **nunca sobreestima**: el
techo del escenario con oxígeno en todas las tomas es 20,4 % contra el 11,2 % reportado.

Sobre TRIAGE el hueco es menor —esa cohorte **sí** tiene la "C" de confusión— así que allí se
imputa un solo parámetro en lugar de dos.

**Y esto juega a favor de la honestidad del trabajo:** si la tasa real de NEWS2 fuera más
alta que la reportada, superarla sería *más fácil*. Reportar el piso pone la vara más alta.

---

## Qué se sigue de esto

### 1. Justifica el reencuadre del ADR-005

Con una sensibilidad del 53,7 % y una tasa de alertas del 25,7 %, el problema clínico no es
*"discriminar mejor"* en abstracto sino **el costo de la fatiga de alertas**. Por eso la
métrica principal del proyecto es la tasa de alertas a sensibilidad igualada y no el AUROC.

### 2. Justifica conservar el rojo aislado

Medido sobre TRIAGE, el rojo aislado **corta para los dos lados**: para mortalidad a 30 días
la regla desplegada queda por dentro de la curva del score puro, pero para **ingreso a UCI
gana con claridad** (25,7 % de alertas contra 36,6 % del mejor umbral, a igual sensibilidad).

Es coherente con su razón clínica: detecta deterioro que exige atención **ahora**, que se
parece a "termina en UCI" y no a "muere dentro de 30 días". **No hay evidencia para
removerlo**, y juzgarlo sólo por mortalidad a 30 días sería juzgarlo por algo que no se
propone predecir.

### 3. Lo que todavía NO está demostrado — y hay que decirlo así

Que NEWS2 rinda modestamente **no implica** que este proyecto ya lo haya superado. Con el
baseline de `SCRUM-56`, a la sensibilidad en que opera el sistema:

```
NEWS2, mejor umbral :  22,6 % de alertas
modelo              :  22,0 % de alertas
reducción           :  +2,7 %   IC 95 % [-21,1 %, +54,8 %]
```

**El intervalo cruza el cero.** El modelo discrimina mejor (AUROC 0,771 contra 0,728, con
validación cruzada anidada), pero la reducción de alertas **no está demostrada** con 54
eventos. La limitación es de **volumen de datos**, no de capacidad del modelo, y es el
argumento medido para necesitar la base completa de MIMIC (`SCRUM-48`).

---

## Limitaciones de esta medición, para declarar en la tesis

- **Una sola cohorte y chica.** 1.300 pacientes, 54 muertes. Los intervalos son anchos.
- **La población no es argentina.** 72 % de un único hospital de EE.UU., 27 % de la
  Salpêtrière. Generalizar a una guardia local es una limitación, no un resultado.
- **Es NEWS, no NEWS2.** La cohorte TRIAGE trae los componentes de NEWS; NEWS2 difiere en la
  escala 2 de SpO₂ para hipercápnicos y en el tratamiento de la confusión.
- **Sin validación externa fila por fila** del motor. El archivo no trae la columna del score
  calculado, así que sólo se comparan distribuciones. Candidato para cerrarlo: usar los
  estadísticos publicados del propio estudio TRIAGE.
- **Los subgrupos de sepsis y respiratorio no se analizaron por separado**, como pedía el
  ADR-006. La cohorte no trae diagnóstico, así que queda pendiente para MIMIC.

---

## Dónde vive cada número

| Resultado | Fuente reproducible |
|---|---|
| Tasa de alertas sobre MIMIC-IV-ED | `notebooks/06_baseline_news2.ipynb`, `data/interim/tasa_alertas_referencia.parquet` |
| AUROC, sensibilidad y curva sobre TRIAGE | `notebooks/07_news2_en_triage.ipynb`, `data/interim/curva_operacion_news2.parquet` |
| Comparación contra el baseline | `python -m src.models.baseline` |
| La regla de alerta | `src/data/alertas.py` (espejo del trigger `emit_news2_alert`) |

Ver también: **ADR-005** (reencuadre a tasa de alertas), **ADR-006** (el caveat original),
**ADR-007** (imputación) y **ADR-009** (segunda cohorte).
