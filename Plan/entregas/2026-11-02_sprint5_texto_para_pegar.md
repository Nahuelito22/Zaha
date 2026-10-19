# Texto para el Doc — Sprint 5 (pestaña Enfermeria)

Replica la estructura exacta de la entrega del 19 de octubre: siete subtítulos en el mismo
orden. Las figuras van numeradas del 26 al 31 y están en esta misma carpeta.

Orden de los subtítulos: Sprint 5 — Integración IA · Apreciación general · Evidencia de
gestión en Jira · Evidencia del incremento funcionando · Medición del sprint · Burndown
Chart · Conclusión.

---

## Entrega del 2 de noviembre de 2026

### Sprint 5 — Integración IA

Iteración 5. Del 13 de octubre al 2 de noviembre de 2026. 11 ítems de trabajo, 64 puntos de
historia: el sprint arrancó con 9 ítems y 54 puntos, y el 15 de octubre se sumaron dos.

### Apreciación general

Los cuatro sprints anteriores construyeron las dos puntas del sistema por separado: una
aplicación que registra signos vitales y calcula la escala, y un modelo que estima riesgo a
partir de esos mismos siete parámetros. Este sprint tenía que unirlas, y tenía que hacerlo
sin que la aplicación quedara dependiendo del modelo.

Esa condición ordena todas las decisiones del sprint. La escala se calcula en la base de
datos, de forma determinística, y nunca consulta al modelo. La estimación es un agregado: si
el servicio que la provee está caído, dormido o tarda demasiado, la pantalla lo declara y
sigue mostrando la escala. Un sistema de soporte a la decisión que se apaga entero porque un
servicio opcional no responde es peor que no tenerlo, porque enseña a desconfiar de él.

El trabajo quedó repartido en cuatro piezas. El modelo entrenado en el sprint anterior se
publicó como un servicio consultable, alojado en una plataforma pública y gratuita. Entre la
aplicación y ese servicio se intercaló un intermediario que corre del lado del servidor:
traduce el vocabulario de la base de datos al del modelo, consulta la historia clínica con
los mismos permisos que tendría el navegador de quien está usando el sistema —nunca con
permisos de administrador— y decide, en un único lugar, qué se le informa a la pantalla
cuando no hay estimación. La tercera pieza es la estimación mostrada en la pantalla del
paciente, deliberadamente separada del puntaje de la escala. La cuarta es el flujo de un
solo clic para validar o posponer una alerta.

La separación visual entre la escala y la estimación no es una preferencia estética. La
escala tiene una codificación de color establecida y conocida por el personal; teñir la
estimación con esos mismos colores la haría pasar por un puntaje determinístico cuando no lo
es. Por eso la estimación aparece fuera de esa escala cromática y con un borde discontinuo,
que es una señal que no depende del color. Junto a ella se muestra la contribución de cada
parámetro, y la edad aparece separada del resto bajo una advertencia explícita: pesa mucho en
la estimación, pero no es algo sobre lo que se pueda actuar al pie de la cama. No se oculta,
porque las contribuciones deben sumar exactamente el resultado para que la explicación sea
verificable.

La decisión de diseño más consecuente del sprint fue incorporar un estado nuevo para las
alertas pospuestas. La alternativa era tratar «posponer» como «descartar», que ya existía.
Habría sido más simple y habría sido un error grave de medición: registraría una falsa alarma
cada vez que una enfermera está ocupada, y la tasa de falsas alarmas es exactamente la
métrica que el proyecto busca reducir. Una alerta pospuesta no es una alerta equivocada. La
cola de alertas pendientes se deriva sola de la combinación de estado y plazo, sin ningún
proceso automático que modifique registros, porque un proceso así generaría eventos de
auditoría que ninguna persona ejecutó y borraría la firma de quién pospuso.

Dos defectos aparecieron recién al correr el sistema completo, y ninguna prueba automatizada
podía encontrarlos, porque en los dos casos las dos puntas estaban bien y lo que fallaba era
el acuerdo entre ellas. El primero hacía que el navegador descartara la respuesta del
servidor sin leerla. El segundo hacía que el intermediario se rompiera cuando el servicio del
modelo respondía con algo que no eran datos, y al romperse devolvía un error que el navegador
también descartaba. Lo que los volvió difíciles es que los dos producían el mismo síntoma
visible: el mensaje de que el motor no está disponible. Es decir, el mecanismo de degradación
funcionaba tan bien que ocultaba las fallas, no sólo al usuario —donde debe ocultarlas— sino
también a quien estaba buscándolas.

De ahí salió la corrección de método más útil del sprint: la degradación es silenciosa para
el usuario y debe dejar rastro para quien diagnostica. Cada camino por el que el sistema
decide no mostrar una estimación registra ahora qué se pidió y qué se recibió. La diferencia
práctica es entre media jornada de búsqueda y una línea de registro.

El sprint incluyó además el encuadre regulatorio del producto, que corrigió un supuesto que
el proyecto arrastraba desde su planteo inicial. La norma que la documentación trataba como
«la norma de software médico» regula en realidad el procedimiento de registro; la
clasificación por riesgo proviene de una disposición anterior y sus modificatorias. El
documento resultante deliberadamente no asigna una clase de riesgo, porque los anexos que la
definen no pudieron consultarse, y deja listado lo que queda sin verificar. La conclusión que
sí se sostiene es que el sistema sería producto médico desde el momento en que se use sobre
un paciente real o se instale en un efector de salud: el límite es el uso, no un tecnicismo.

El alcance comprometido al arrancar, nueve ítems y cincuenta y cuatro puntos, se completó al
tercer día de una ventana de tres semanas, porque el trabajo de integración resultó corto una
vez que las dos puntas existían. Ese mismo día se sumaron dos ítems que el propio sprint había
vuelto necesarios: la landing todavía decía que el motor de inteligencia artificial no
existía, y el sistema sólo corría en el equipo de desarrollo. El sitio se actualizó —incluye
ahora una demostración en la que cualquier visitante carga signos vitales y ve la estimación
del modelo con su explicación— y el sistema se publicó en zahasalud.com.ar. El sprint cerró
con los once ítems completos y los sesenta y cuatro puntos hechos.

Queda declarado un límite importante: que el sistema esté publicado no cambia sobre qué datos
funciona. Se verificó de extremo a extremo sobre pacientes ficticios y con usuarios de
prueba. No se ha usado sobre pacientes reales, y no debe
usarse hasta que medie la autorización regulatoria correspondiente.

### Evidencia de gestión en Jira

Figura 26. Sprint 5 planificado. Los nueve ítems comprometidos antes de estimar, todos en la
primera columna del flujo y sin puntos de historia asignados. Es el estado del tablero en el
momento de la reunión de planificación.

Figura 27. El mismo sprint una vez estimado. Los cincuenta y cuatro puntos de historia
repartidos entre los nueve ítems. La estimación se hace sobre el ítem y no sobre el tiempo:
mide tamaño relativo, no horas.

Figura 28. Estado del Sprint 5 al cierre. Los once ítems con su responsable, su prioridad,
su estimación y su estado, incluidos los dos que se sumaron el 15 de octubre. Los sesenta y
cuatro puntos quedaron completos. La tabla se compuso a partir de los datos del tablero: el
gestor oculta los ítems cerrados, de modo que una captura de la pantalla mostraría este
sprint vacío.

### Evidencia del incremento funcionando

Figura 29. La pantalla del paciente con el sistema completo en funcionamiento. Arriba, el
puntaje de la escala y el aporte de cada uno de los siete parámetros, calculado por la base
de datos. Abajo, separada y fuera de la escala cromática, la estimación del modelo con la
contribución de cada parámetro, el umbral utilizado, la medición sobre la que se estimó y la
advertencia de que la reducción de alertas frente a la escala todavía no está demostrada. Es
la primera vez en el proyecto que las dos mitades aparecen juntas y funcionando.

Figura 30. La bitácora de auditoría. Cada acuse de una alerta queda firmado con la identidad
de quien lo realizó y encadenado criptográficamente al evento anterior: el valor de control
de cada fila es el del evento previo, de modo que alterar o borrar un registro intermedio
rompe la cadena desde ese punto hacia abajo y la verificación lo detecta. Los dos primeros
eventos de la tabla provienen de una prueba de desarrollo y siguen visibles porque la tabla
no admite modificación ni borrado para ningún rol, que es precisamente la propiedad que se
busca demostrar.

### Medición del sprint

Datos:

Sprint 1, 67 puntos comprometidos y 67 completados sobre 20 ítems.

Sprint 2, 34 puntos comprometidos y 34 completados sobre 9 ítems.

Sprint 3, 72 puntos comprometidos y 72 completados sobre 13 ítems.

Sprint 4, 75 puntos comprometidos y 58 completados sobre 15 ítems. Los 17 puntos restantes
corresponden a trabajo bloqueado por una dependencia externa y a historias que se cierran con
sus tareas hijas.

Sprint 5, 64 puntos comprometidos y 64 completados sobre 11 ítems. Arrancó con 54 puntos
sobre 9 ítems; los 10 restantes se sumaron el 15 de octubre.

### Burndown Chart

Figura 31. Evolución del Sprint 5. El trabajo restante día por día contra el avance ideal, y
el alcance comprometido como una línea aparte: el escalón del 15 de octubre son los dos ítems
que se sumaron ese día. A diferencia del sprint anterior, la curva llega a cero. El alcance
original se completó al tercer día, porque los cuatro sprints previos ya habían construido
las dos piezas que este sprint tenía que unir; los dos ítems agregados cerraron el 15 y el
19 de octubre.

Cobertura de pruebas automatizadas al cierre del sprint: 214 casos, frente a los 126 del
sprint anterior. Las 88 nuevas verifican el servicio de inferencia, su despliegue, la
degradación cuando el servicio no responde, el flujo de acuse de alertas y la traducción de
parámetros entre la base de datos y el modelo. Esta última es el punto donde un error se
vuelve invisible: un parámetro mal mapeado devuelve una estimación perfectamente plausible,
pero de otro paciente.

### Conclusión

Los sprints anteriores dejaron una lección cada uno: el primero, dónde se usa el sistema; el
segundo, a qué tipo de error hay que tenerle miedo; el tercero, la diferencia entre un dato
correcto y un dato suficiente; el cuarto, la diferencia entre un resultado y un resultado
demostrado. Este dejó una sobre la diferencia entre que las partes funcionen y que el sistema
funcione.

Las dos piezas que este sprint tenía que unir estaban probadas por separado, con doscientos
catorce casos automatizados que siguen en verde. Los dos defectos que aparecieron no estaban
en ninguna de las dos: estaban en el acuerdo entre ellas, en supuestos que cada lado daba por
ciertos sobre el otro y que ninguna prueba unitaria podía contradecir. Sólo se vieron al
correr el sistema completo contra el servicio real, con un paciente en pantalla.

Lo incómodo del hallazgo es que el mecanismo que los ocultó es el mismo que el sprint se
propuso construir. La degradación elegante existe para que una enfermera nunca vea un error
técnico y nunca pierda el puntaje por culpa de un servicio opcional, y cumplió esa función
sin fallar una sola vez. El costo es que convirtió dos defectos distintos en el mismo mensaje
tranquilizador, también para quien los estaba buscando. Las dos cosas eran correctas por
separado y juntas producían una falla invisible.

La corrección fue separar los dos destinatarios: silencio para el usuario, rastro para el
diagnóstico. Es un cambio pequeño en el código y grande en el método, y vale para cualquier
sistema que degrade con elegancia.

Queda dicho con claridad lo que este sprint no demuestra. El sistema funciona de extremo a
extremo y está publicado, pero sobre datos ficticios y con usuarios de prueba. No se ha
usado sobre pacientes reales, la reducción de alertas frente a la escala sigue sin estar
demostrada —el intervalo de confianza del sprint anterior sigue incluyendo el cero— y el
encuadre regulatorio establece que el sistema sería producto médico desde el momento en que
se use sobre una persona. Tener el sistema completo y funcionando no cambia ninguna de esas
tres cosas, y el proyecto no se las atribuye.
