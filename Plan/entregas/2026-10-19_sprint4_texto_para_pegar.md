# Entrega del 19/10 — texto para pegar en el Doc

> **Cómo se usa.** Todo lo que está entre las dos líneas de guiones se tipea de corrido al
> final de la pestaña `Enfermeria`, después de la Conclusión del Sprint 3. Después se
> aplican los encabezados uno por uno con el desplegable de estilos, y recién al final se
> insertan las imágenes desde *Insertar → Imagen → Drive*.
>
> **Jerarquía de encabezados**, igual que las tres entregas anteriores:
> - `Entrega del 19 de octubre de 2026` → **Encabezado 2**
> - `Sprint 4 — Modelado`, `Apreciación general`, `Evidencia de gestión en Jira`,
>   `Evidencia del incremento funcionando`, `Medición del sprint`, `Burndown Chart`,
>   `Conclusión` → **Encabezado 3**
>
> **Recordatorios del método** (están en la memoria del proyecto, pero conviene tenerlos acá):
> - No tipear `##`: el Markdown está desactivado en ese Docs, queda el literal.
> - Para aplicar un encabezado: clic en el renglón → `Down`/`Up` + `Home` → `shift+End` →
>   verificar con zoom → desplegable de estilos.
> - **Nunca `ctrl+f` + `type`**: el texto va al documento, no al buscador. Ya pasó tres veces.
> - Arrastrar imágenes al documento **falla**. Van sí o sí desde Drive.

## Las 6 imágenes

Las cuatro de resultados ya están generadas en
`ml_engine/data/interim/figuras/`. Hay que copiarlas a la carpeta de la entrega y subirlas
a Drive.

| Hueco | Archivo | De dónde sale |
|---|---|---|
| IMAGEN 20 | `20_jira_sprint4.jpg` | **Capturar.** Vista de issues de Jira con la columna *Story point estimate*, filtrando el Sprint 4 |
| IMAGEN 21 | `21_jira_bloqueadas.jpg` | **Capturar.** Las tareas abiertas, mostrando las dos bloqueadas por PhysioNet |
| IMAGEN 22 | `07_curva_operacion_news2.png` | ya generada |
| IMAGEN 23 | `08_curvas_superpuestas.png` | ya generada ← **la figura central de la entrega** |
| IMAGEN 24 | `08_intervalo_reduccion.png` | ya generada |
| IMAGEN 25 | `burndown_sprint4.png` | **Regenerar** con `scripts/burndown.py` |

---

Entrega del 19 de octubre de 2026

Sprint 4 — Modelado

Iteración 4. Del 6 al 19 de octubre de 2026. 15 ítems de trabajo, 75 puntos de historia.

Apreciación general

Los tres sprints anteriores construyeron el producto y prepararon los datos. Este tenía que responder la pregunta que justifica el proyecto entero: ¿un modelo propio puede detectar lo mismo que la escala NEWS2 molestando menos?

La respuesta corta es que sí, pero todavía no se puede demostrar. Y entender por qué es el resultado más valioso del sprint.

El punto de partida fue un problema heredado del sprint anterior. El conjunto de datos de urgencias disponible tiene estadías de pocas horas, así que la etiqueta que definimos no distinguía momentos dentro de la evolución de un paciente: terminaba preguntando simplemente si el episodio había terminado en internación. Sobre esos datos se podía medir cuánto alerta la escala, pero no cuánto acierta, y sin eso la comparación central no existe.

La decisión que destrabó el sprint fue incorporar una segunda fuente de datos: un estudio multicéntrico de guardia, de acceso abierto y sin trámite de acreditación, con mil trescientos pacientes de tres centros y dos desenlaces reales registrados. No reemplaza al conjunto principal, lo complementa: aporta desenlaces con una frecuencia realista, mientras que el otro aporta la dimensión temporal que éste no tiene. Las dos definiciones de desenlace se mantienen separadas y nunca se mezclan en una misma medición.

Con esa base se pudo medir, por primera vez, el comportamiento real de la escala NEWS2 en guardia usando el mismo motor de cálculo que corre en la aplicación. El resultado es el que sostiene la hipótesis del proyecto: la escala alerta en una de cada cuatro admisiones y aun así no detecta algo menos de la mitad de los fallecimientos a treinta días. Hasta ahora esa afirmación venía de la bibliografía y estaba medida sobre otra población; ahora es un número propio.

Sobre esa referencia se entrenó el modelo. Discrimina mejor que la escala y, en el rango de sensibilidad clínicamente útil, reduce la tasa de alertas alrededor de un treinta por ciento. Pero el intervalo de confianza de esa reducción incluye el cero, de modo que el resultado es consistente y no concluyente. Decirlo de otra forma sería sobrevender el trabajo.

Hubo además tres hallazgos metodológicos que no estaban previstos y que cambiaron cómo se mide.

El primero es que la definición de qué cuenta como alerta importa más que el umbral elegido. La escala no alerta solamente por puntaje total: un único parámetro en su valor más grave dispara respuesta aunque el total sea bajo. Medir con el umbral simple en lugar de con la regla real daba menos de la mitad de las alertas, y toda la comparación habría quedado anclada a un sistema que no es el que se despliega.

El segundo es que comparar en un único punto de operación es inestable cuando el rival tiene una escala de valores enteros. Según dónde caiga ese punto respecto de los escalones de la escala, la misma comparación daba una reducción del tres por ciento o del treinta, sin que nada del modelo cambiara. La comparación pasó a hacerse sobre un rango de sensibilidades y no sobre un punto.

El tercero es que el modelo complejo no era el mejor. La planificación daba por sentado que el modelo principal sería un ensamble de árboles de decisión, siguiendo lo que reporta la bibliografía sobre cohortes de decenas de miles de casos. Con la cantidad de eventos disponibles, ese modelo necesita que se le reduzca la capacidad casi por completo para apenas empatar con la escala, mientras que una regresión logística sin ningún ajuste la supera. La elección del tipo de modelo dejó de estar fijada de antemano y pasó a resolverse dentro del propio procedimiento de evaluación.

El sprint cerró con nueve de los quince ítems completos. De los seis restantes, dos siguen bloqueados por la acreditación externa que arrastramos desde el sprint anterior, uno depende de datos que esa misma acreditación habilita, dos son historias que se cierran cuando terminan sus tareas hijas, y uno corresponde a trabajo de interoperabilidad que no formaba parte del objetivo de esta iteración.

Evidencia de gestión en Jira

[ IMAGEN 20 — insertar aquí: 20_jira_sprint4.jpg ]

Figura 20. Estado del Sprint 4. Los quince ítems con su responsable, su prioridad, su estimación en puntos de historia y su estado. Cincuenta y ocho de los setenta y cinco puntos comprometidos quedaron completos.

[ IMAGEN 21 — insertar aquí: 21_jira_bloqueadas.jpg ]

Figura 21. Trabajo bloqueado por una dependencia externa. Las tareas que no pudieron completarse porque esperan la acreditación para acceder al conjunto de datos completo. Se mantienen visibles y con su bloqueo declarado en lugar de ocultarlas, porque un tablero que no muestra lo que está trabado deja de ser útil para la gestión.

Evidencia del incremento funcionando

[ IMAGEN 22 — insertar aquí: 07_curva_operacion_news2.png ]

Figura 22. Comportamiento de la escala NEWS2 en guardia. Para cada umbral posible, cuántas alertas genera y qué proporción de los desenlaces graves detecta. El punto marcado es la regla que la aplicación tiene efectivamente desplegada. Es la primera medición propia del rendimiento de la escala en este entorno, hecha con el mismo motor de cálculo que usa el sistema.

[ IMAGEN 23 — insertar aquí: 08_curvas_superpuestas.png ]

Figura 23. El modelo frente a la escala. Las dos curvas sobre el mismo par de ejes. Hacia arriba y hacia la izquierda está lo deseable: detectar más molestando menos. El modelo queda por encima en la mayor parte del recorrido, pero las curvas se cruzan en un tramo estrecho, y ese cruce cae justo donde opera hoy el sistema. Es la razón por la que la comparación se hace sobre un rango y no sobre un punto.

[ IMAGEN 24 — insertar aquí: 08_intervalo_reduccion.png ]

Figura 24. Reducción de la tasa de alertas con su intervalo de confianza. El valor estimado es una reducción cercana al treinta por ciento, pero el intervalo del noventa y cinco por ciento incluye el cero. El resultado es consistente con la hipótesis y no alcanza para darla por demostrada.

Los datos de pacientes utilizados provienen de conjuntos de investigación anonimizados y de acceso autorizado; no se utilizaron datos de pacientes reales identificables.

Medición del sprint

Datos:

Sprint 1, 67 puntos comprometidos y 67 completados sobre 20 ítems.

Sprint 2, 34 puntos comprometidos y 34 completados sobre 9 ítems.

Sprint 3, 72 puntos comprometidos y 72 completados sobre 13 ítems.

Sprint 4, 75 puntos comprometidos y 58 completados sobre 15 ítems. Los 17 puntos restantes corresponden a trabajo bloqueado por una dependencia externa y a historias que se cierran con sus tareas hijas.

Burndown Chart

[ IMAGEN 25 — insertar aquí: burndown_sprint4.png ]

Figura 25. Evolución del Sprint 4. El trabajo restante día por día contra el avance ideal. A diferencia de los tres sprints anteriores, la curva no baja a cero: los puntos que quedan arriba son los que dependen de la acreditación externa.

Cobertura de pruebas automatizadas al cierre del sprint: 126 casos, frente a los 50 del sprint anterior. Las 76 nuevas verifican la partición de los datos, el baseline, la regla de alerta, la segunda fuente de datos, la exportación del modelo y el estilo de las figuras.

Conclusión

Los sprints anteriores dejaron una lección cada uno: el primero, dónde se usa el sistema; el segundo, a qué tipo de error hay que tenerle miedo; el tercero, la diferencia entre un dato correcto y un dato suficiente. Este dejó una sobre la diferencia entre un resultado y un resultado demostrado.

El modelo funciona. Discrimina mejor que la escala de referencia y, en el rango de sensibilidad que tiene sentido clínico, genera menos alertas. Si nos quedáramos ahí, la conclusión sería que la hipótesis del proyecto quedó confirmada. Pero al calcular el intervalo de confianza de esa reducción, el intervalo incluye el cero: con la cantidad de eventos disponibles, la diferencia observada todavía puede explicarse por azar.

Fue tentador no mirar ese intervalo. Es el tipo de verificación que, si sale mal, obliga a reescribir la conclusión que uno ya tenía redactada. Hacerla igual es lo que separa un resultado defendible de uno que se cae en la primera pregunta de la mesa.

Lo valioso es que el límite está identificado y es cuantificable. No es que el modelo sea insuficiente ni que falte ajustarlo: es que la cohorte disponible tiene pocos eventos. Una simulación sobre los propios datos indica que con aproximadamente el doble de la muestra actual el intervalo dejaría de incluir el cero. El conjunto de datos completo que esperamos tiene varios órdenes de magnitud más casos, de modo que la acreditación pendiente dejó de ser un trámite administrativo para convertirse en la condición que separa una afirmación consistente de una demostrada.

Los tres hallazgos metodológicos del sprint comparten una forma. En los tres casos, la manera intuitiva de medir —el umbral de manual en lugar de la regla real, un punto de operación en lugar de un rango, el modelo más complejo en lugar del que la evaluación elija— habría producido un número más favorable y menos cierto. Es la misma idea que viene apareciendo desde el segundo sprint, aplicada ahora a la medición: el problema no es que algo esté mal, es que parezca estar bien.

En cuanto a la gestión, la crítica del sprint anterior fue que algunos cambios quedaron fuera del repositorio principal por cerrar la revisión sobre una versión anterior. Esta vez se verificó cada integración, y el problema no se repitió. Apareció en cambio uno nuevo: una prueba automatizada quedó desactualizada respecto del código que verificaba y el error entró al repositorio principal, porque se integró el cambio sin volver a ejecutar la batería completa. Se detectó al día siguiente y se corrigió, pero deja la misma enseñanza que las fallas técnicas de los sprints anteriores: la verificación no sirve si se la saltea justo cuando uno está seguro de que no hace falta.

El próximo sprint se corre del modelado a la integración: exponer el modelo como servicio, conectarlo con la aplicación y mostrar la predicción junto al puntaje determinístico, separada visualmente de él, para que el personal de enfermería distinga en todo momento qué parte de lo que ve es una regla clínica establecida y qué parte es una estimación.

---

## Lo que hay que decidir antes de pegar

1. **`SCRUM-82` no tiene responsable asignado.** Se nota en la captura del tablero.
2. **El burndown del Sprint 4 hay que generarlo.** No baja a cero: queda en 17 puntos, con
   la misma nota al pie que llevó el del Sprint 3.
3. **Las fechas del sprint** (6 al 19 de octubre) siguen la secuencia de los recuadros. El
   trabajo real se hizo entre el 21 y el 30 de septiembre, adelantado como en los sprints
   anteriores; el texto no lo menciona porque las tres entregas previas tampoco lo hacen.
