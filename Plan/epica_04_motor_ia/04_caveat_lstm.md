# 🩺 Épica 4 — Paso 4: Por qué la LSTM no se entrenó (SCRUM-57)

> **v1 — 2026-10-19.** Cierra `SCRUM-57`. El recuadro de la entrega del 19/10 pedía el
> *caveat de la LSTM*, no la LSTM: este documento es ese caveat. Todas las cifras están
> medidas por el proyecto sobre los datos que tiene en disco, no tomadas de memoria.
>
> **No dice que la LSTM no sirva.** Dice que con los datos accesibles la pregunta no se
> puede contestar, por qué, y qué haría falta para contestarla.

---

## La afirmación, en una oración

**La hipótesis de la LSTM —que la tendencia de los signos vitales aporta algo que la última
toma no tiene— no se puede probar con ninguno de los datos accesibles al proyecto: ninguno
tiene series temporales de la longitud que la hipótesis necesita.**

---

## Qué era la LSTM dentro del proyecto

El **ADR-005** le quitó el protagonismo antes de que existiera una línea de código. La
literatura que lo motivó reporta que, sobre una misma cohorte grande, una LSTM con series de
12 a 48 h y un XGBoost con **sólo la última observación** rinden prácticamente igual (AUROC
0,924 contra 0,925). Desde ese ADR la LSTM es **la hipótesis bajo prueba**: *¿aporta algo la
tendencia, o alcanza el snapshot?* Y el mismo ADR deja escrito que "no aporta" también es un
resultado válido.

O sea que el proyecto **nunca dependió de la LSTM**. Lo que este documento cierra es la
prueba de esa hipótesis, no una pieza del sistema.

---

## Lo que la prueba necesita

1. **Series**: varias tomas de los siete parámetros por paciente, a lo largo de 12 a 48 h.
2. **Un desenlace posterior** a la serie, con una ventana definida (la etiqueta v2 de
   `01_definicion_etiqueta.md`: el evento en `(t+1h, t+24h]`).
3. **Suficientes eventos** para que una red con memoria no aprenda ruido. Con la regresión
   logística, que tiene ocho coeficientes, ya hizo falta discutir el tamaño de muestra
   (**ADR-010**); una LSTM tiene miles de parámetros.

---

## Por qué no se puede, fuente por fuente

| Fuente | Qué tiene | Series para la LSTM |
|---|---|---|
| **TRIAGE** (Zenodo, CC0) — entrena el modelo en producción | 1.303 pacientes, **una fila por paciente**: los signos vitales al ingreso | **Ninguna** |
| **MIMIC-IV-ED Demo 2.2** (ODbL) | 222 episodios de 64 pacientes, mediana de **4 tomas** por episodio | Cortas: ver abajo |
| **MIMIC-IV-ED completo** | ~425.000 episodios, el mismo esquema que el demo | **Sin acceso**: PhysioNet rechazó la solicitud el 04/10/2026 |
| Dataset de Kaggle (descartado en septiembre) | 200.020 filas de 200.020 pacientes, desenlace sintético | **Ninguna** |

### TRIAGE: no hay tiempo

Es la cohorte que destrabó la tesis (**ADR-009**) justamente porque trae desenlaces reales
—mortalidad a 30 días e ingreso a UCI—, y es con la que se entrenó el modelo publicado. Pero
cada paciente es **una sola medición, al ingreso**. No hay ningún "antes" contra el cual
calcular una tendencia. El propio módulo de ingesta (`ml_engine/src/data/triage.py`) lo
declara en su encabezado.

### MIMIC-IV-ED: hay tiempo, pero es de guardia

Medido sobre el demo con la misma tubería del proyecto:

| | Valor |
|---|---|
| Estadía mediana en guardia | **5,8 h** |
| Percentil 90 de la estadía | 15,7 h |
| Episodios de 24 h o más | **6 de 222** |
| Episodios de 48 h o más | **2 de 222** |
| Tomas por episodio | mediana 4, máximo 22 |

El título del ítem habla de **series de 48 h**, y en una guardia esas series casi no
existen: el paciente se interna o se va de alta en horas. Esto **no lo arregla la base
completa**: es la misma población con el mismo esquema, así que tendrá más episodios, pero
con la misma duración. Lo que cambia con 425.000 episodios es que habría muchas series
cortas —de 4 a 8 tomas en unas horas— sobre las cuales sí podría probarse una versión
**corta** de la hipótesis.

Y aun así queda el problema del desenlace, ya documentado en la etiqueta v2: con estadías
de 5,8 h, la ventana de 24 h no discrimina y la etiqueta colapsa a "el episodio terminó en
internación".

### Por qué no se entrenó igual, "para mostrar algo"

Con dos episodios de más de 48 h, una LSTM aprendería esos dos pacientes. Cualquier número
que saliera de ahí sería ruido con forma de resultado, y reportarlo sería peor que no
reportar nada: el proyecto entero se apoya en no atribuirse lo que no demuestra.

---

## Qué se hizo en su lugar

El orden del **ADR-005** ya ponía primero el modelo sobre snapshot, y eso es lo que está en
producción: una regresión logística sobre los parámetros de cabecera (**ADR-010**), que sobre
TRIAGE discrimina mejor que NEWS2 (AUROC 0,771 contra 0,728, validación cruzada anidada) y
reduce la tasa de alertas un 29,8 % sobre el rango de sensibilidades de 50 a 80 % — con un
intervalo de confianza que **todavía incluye el cero**.

Ese resultado **no depende de la LSTM**. La pregunta que queda abierta es la otra: si la
tendencia agregaría algo encima del snapshot.

---

## Qué haría falta para contestarla

En orden, del más barato al más caro:

1. **Features de ventana sobre MIMIC-IV-ED completo** (paso 3 del ADR-005): pendiente,
   tasa de cambio y variabilidad de cada parámetro en las últimas horas, agregadas al mismo
   modelo de snapshot. Mide si la tendencia aporta **sin** red neuronal. Si no aporta acá, es
   improbable que una LSTM lo haga. Requiere reaplicar a PhysioNet, corrigiendo los defectos
   del formulario rechazado.
2. **Datos de sala**, no de guardia: series de días, donde la ventana de 24 h sí discrimina
   y donde NEWS2 fue diseñado. En MIMIC-IV corresponden a otra base (hospitalización y
   terapia intensiva), con la misma credencial. La alternativa local sería un convenio con
   un hospital, con aprobación de un comité de ética.
3. **Recién ahí, la LSTM** (paso 4 del ADR-005), contrastada contra el paso 1.

El código no tiene que cambiar para el paso 1: la tubería, las particiones por paciente y la
etiqueta v2 corren sobre la base completa con `--origen`. Es exactamente el escenario para
el que se construyeron sobre el demo.

---

## Lo que esto deja dicho para la tesis

- La hipótesis temporal queda **declarada y sin probar**, no descartada.
- El resultado central del proyecto —snapshot contra NEWS2 a sensibilidad igualada— no
  depende de ella.
- La razón es de datos, no de método, y está medida: ninguna fuente accesible tiene las
  series que la hipótesis necesita.
