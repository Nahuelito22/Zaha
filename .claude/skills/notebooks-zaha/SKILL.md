---
name: notebooks-zaha
description: Convenciones para los notebooks de investigación de Zaha (ml_engine/notebooks/) y reglas de manejo de datos clínicos restringidos de PhysioNet/MIMIC. Usar al crear, editar o revisar cualquier .ipynb del proyecto, al trabajar con MIMIC-IV-ED o datos sintéticos de signos vitales, y antes de commitear notebooks.
---

# Notebooks de Zaha

Los notebooks de este proyecto no son borradores: **son la evidencia de la tesis**. La
afirmación central —"igualo la sensibilidad de NEWS2 reduciendo la tasa de alertas"— se
defiende mostrando cómo se llegó al número. Un notebook que no se puede volver a correr y
obtener lo mismo no sirve.

## 🚨 Datos restringidos — antes que cualquier otra cosa

MIMIC-IV-ED viene de PhysioNet bajo un DUA que **prohíbe redistribuirlo**. El repositorio
`Nahuelito22/Zaha` es público (verificar si sigue siéndolo antes de asumir lo contrario).

- **Nunca commitear salidas de celdas que muestren filas de datos reales.** Un `df.head()`,
  un `describe()` con conteos por paciente o un gráfico con detalle individual publicado en
  un repo abierto es una violación del DUA y causal de revocación de la credencial.
- `nbstripout` está instalado como filtro de git (`.gitattributes`) y limpia las salidas al
  commitear. **Es una red, no un permiso**: si se clona el repo en otra máquina hay que
  reinstalarlo con `pip install nbstripout && nbstripout --install --attributes .gitattributes`.
- **Agregados sí, filas no.** Prevalencias, distribuciones, métricas y curvas son publicables.
  Registros individuales no.
- Los datos viven en `ml_engine/data/`, que está entero en `.gitignore`. Nunca mover un
  archivo de datos fuera de ahí "por comodidad".
- **Colab:** subir únicamente la matriz de features derivada que el modelo necesita —tensores
  numéricos y etiqueta—, nunca el dataset crudo, nunca texto libre, nunca identificadores.
  Drive privado, y borrar al terminar. Anotar en el notebook qué se subió y por qué.

## Convención de archivos

`ml_engine/notebooks/NN_descripcion_en_snake_case.ipynb`, numerados en orden de ejecución.
Español, como en el resto del proyecto.

La secuencia planificada está en `Plan/05_PREPARACION.md`. Un notebook nuevo se inserta con
el número que le corresponde en el flujo, no al final.

## Estructura de cada notebook

**Primera celda, siempre markdown**, con:

- Qué pregunta responde este notebook, en una oración.
- Issue de Jira asociado (`SCRUM-NN`).
- Qué notebook lo precede y qué archivo de entrada consume.
- Versión del dataset y fecha de descarga.
- Semilla aleatoria.

**Segunda celda**, imports y configuración reproducible: semilla fija, opciones de pandas,
estilo de figuras.

Después, la secuencia del método científico, con markdown entre bloques que diga **qué se
espera encontrar antes de correr la celda**. Una hipótesis escrita después de ver el resultado
no es una hipótesis.

**Última celda**, markdown: qué se concluyó, qué se guardó y en qué archivo, y qué queda
abierto para el siguiente notebook.

## Las dos reglas que evitan el problema clásico

1. **El notebook explora; `ml_engine/src/` ejecuta.** Toda función que se use más de una vez
   se muda a `src/` y el notebook la importa. Nunca copiar y pegar entre notebooks. Si el
   cálculo de features vive en dos lugares, el modelo servido y el del notebook divergen y
   ninguno de los dos es reproducible.
2. **Cada notebook guarda su salida en `ml_engine/data/interim/` o `processed/`** y el
   siguiente la lee de ahí. No se encadenan por variables en memoria: cada uno tiene que
   poder correrse solo, desde cero.

## Reglas de modelado que no se negocian

Vienen de los ADR y están cerradas. Si un notebook las contradice, el notebook está mal.

- **Etiqueta**: `y=1` si ocurre UCI o muerte en `(t+1h, t+24h]`. Lookback de 24 h, ventana
  ciega de 1 h. Definición completa en `Plan/epica_04_motor_ia/01_definicion_etiqueta.md`.
- **Nunca usar "NEWS2 ≥ 7" como etiqueta.** Sería circular: se estaría entrenando un modelo
  para predecir la fórmula que ya se tiene.
- **Split por paciente, jamás por fila.** Un mismo paciente en train y test es fuga y anula
  el resultado.
- **Nunca reportar accuracy.** La prevalencia está entre 0,22% y 5%: un modelo que dice
  siempre "no" acierta el 99%.
- **Métrica principal: tasa de alertas a sensibilidad igualada**, no AUROC. La comparación es
  contra NEWS2 calculado sobre la misma cohorte (`SCRUM-80`), no contra un número de la
  literatura.

## Figuras

Cargar la skill `dataviz` antes de escribir la primera celda de gráficos. Todas las figuras
de la tesis tienen que leerse como un sistema: misma paleta, mismos ejes, misma tipografía.
Codificar siempre con color **más** forma o texto, nunca solo color — es la misma regla de
accesibilidad que rige la interfaz clínica.

## Antes de commitear

- ¿Corre de arriba abajo en un kernel limpio? Si no, no está terminado.
- ¿Las salidas se limpiaron? (`nbstripout` lo hace, pero verificar en el diff.)
- ¿Algún dato real quedó pegado en una celda de markdown? El filtro no las toca.
