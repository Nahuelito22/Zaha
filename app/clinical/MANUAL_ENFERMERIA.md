# Manual de uso para enfermería

`SCRUM-78` · Zaha · versión del 19/10/2026

> **Antes de empezar.** Zaha es un **prototipo académico. No es un dispositivo médico**: no
> lo uses con pacientes reales. Los pacientes que vas a ver son ficticios. El aviso está en
> todas las pantallas para que nadie lo olvide.

Zaha calcula la escala **NEWS2** a partir de los signos vitales que cargás al pie de la cama,
ordena la sala por riesgo y avisa cuando un paciente necesita revisión. Además muestra una
**estimación de un modelo de IA**, que es un dato complementario y nunca reemplaza a la escala.

Se usa desde el navegador en **zahasalud.com.ar/app**, en tablet, teléfono o computadora.

---

## 1. Entrar

Ingresá tu **correo** y tu **contraseña** y tocá **Entrar**.

- Las cuentas **no se crean desde la app**: te la da jefatura o el administrador del sistema.
- Si el correo o la contraseña están mal, la app dice "Correo o contraseña incorrectos." y no
  aclara cuál de los dos falló. Es a propósito.
- Si entrás y ves "Tu usuario no tiene perfil activo", tu cuenta existe pero jefatura todavía
  no la habilitó. Hasta entonces no vas a ver pacientes.

Arriba a la derecha vas a ver tu nombre, tu rol y tu matrícula. **Salir** cierra la sesión.
Cerrala siempre si la tablet es compartida: cada toma queda firmada por quien tiene la sesión
abierta.

*Figura 35: pantalla de ingreso.*

---

## 2. La sala

Es la pantalla principal. Hay una fila por cama ocupada y muestra **la última toma vigente**
de cada paciente.

**El orden es por riesgo**, de mayor a menor: arriba está el paciente que más necesita que lo
mires. Si dos tienen el mismo nivel, primero va el de puntaje más alto, y si también empatan,
se ordenan por cama. La lista no se reordena sola si no cambió nada.

Cada fila muestra:

| Dato | Qué significa |
|---|---|
| **Cama** | Identifica al paciente en la sala |
| **NEWS2** | El puntaje total de la última toma |
| **Nivel** | Bajo, Medio Bajo, Medio o Alto (ver la sección 4) |
| **Nombre** | Tocalo para abrir el detalle del paciente |
| **Antigüedad** | Cuánto hace que se tomó: "hace 20 min", "hace 3 h". **Se resalta cuando pasaron 8 horas o más** |

En la parte de arriba dice cuántas camas hay y si la sala está **"actualización en vivo"**: los
cambios que carga otra persona aparecen solos. Si dice **"sin actualización en vivo"**, la
conexión se cortó y lo que ves puede estar desactualizado. Recargá la página.

En una tablet acostada o en una computadora, la sala se ve como una tabla. En una tablet
vertical o un teléfono, como tarjetas. Los datos y el orden son los mismos, y el botón
**Cargar vitales** queda siempre a la derecha.

Cada paciente tiene dos botones:

- **Historial**: abre el detalle directamente en las tomas anteriores.
- **Cargar vitales**: abre el formulario de una toma nueva.

*Figura 36: la sala en tablet vertical. Figura 37: la sala como tabla.*

---

## 3. Cargar una toma

Tocá **Cargar vitales** en la cama del paciente. Arriba vas a ver su nombre, el servicio, la
cama y el número de historia clínica. **Verificá que sea el paciente correcto antes de cargar.**

Se cargan **los 7 parámetros de NEWS2, todos**. Si falta uno, no se puede guardar: un NEWS2
con datos incompletos no es un NEWS2 válido.

| Parámetro | Unidad | Rango que acepta la app |
|---|---|---|
| Frecuencia respiratoria | rpm | 0 a 80 |
| Saturación de oxígeno | % | 50 a 100 |
| Temperatura | °C | 25 a 45 (con decimales) |
| Presión sistólica | mmHg | 30 a 300 |
| Frecuencia cardíaca | lpm | 0 a 300 |
| Oxígeno suplementario | — | **Aire ambiente** o **Con oxígeno** |
| Nivel de consciencia (ACVPU) | — | Se elige de la lista |

Si un valor está fuera de rango, aparece en rojo debajo del campo: "Fuera del rango posible".
Casi siempre es un error de tipeo, por ejemplo un 8 en lugar de un 80.

**Nivel de consciencia.** Las opciones son **A** Alerta, **C** Confusión nueva, **V** Responde a
la voz, **P** Responde al dolor y **U** Sin respuesta. La lista arranca en "Elegir nivel…" a
propósito, para que no quede "Alerta" elegido sin que lo hayas mirado. Ojo con la **C**:
la confusión *nueva* suma 3 puntos por sí sola.

**Escala de SpO₂ 2.** Si el paciente tiene indicada la escala 2 (hipercapnia, objetivo 88–92 %),
aparece un recuadro avisándolo. La saturación se puntúa con esa escala. **Sólo medicina puede
cambiarla.**

### Confirmar

Al tocar **Guardar toma** se abre un resumen con los siete valores. **Leelo antes de
confirmar.** Una toma guardada **no se puede borrar ni editar**, y un valor mal cargado puede
disparar una alerta sobre un paciente que no la necesita.

- **Confirmar y guardar** registra la toma.
- **Volver a revisar** cierra el resumen sin guardar.

### Lo que pasa después

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| **Toma registrada** | Se guardó y la base calculó el NEWS2 y el nivel | Nada más. Si el nivel no es Bajo, se generó una alerta |
| **Toma guardada, sin puntaje todavía** | No había conexión. Los datos quedaron guardados **en este dispositivo** y se van a enviar solos cuando vuelva la red | **Seguí el criterio clínico habitual**: mientras tanto no hay puntaje. La app no calcula uno aproximado |
| **La toma no se pudo registrar** | El servidor la rechazó (por ejemplo, el episodio ya no está activo) | Revisá los valores. Reintentar no la arregla |

El puntaje **lo calcula siempre el servidor**, nunca la pantalla. Así hay una sola fuente
para el número.

*Figura 38: formulario completo. Figura 39: el resumen de confirmación. Figura 40: toma
registrada.*

---

## 4. Cómo leer el nivel de riesgo

| Nivel | Cuándo | Genera alerta |
|---|---|---|
| **Bajo** | Puntaje de 0 a 4, sin ningún parámetro en 3 | No |
| **Medio Bajo** | Puntaje de 0 a 4, **pero un parámetro solo suma 3** (el "rojo aislado") | Sí |
| **Medio** | Puntaje de 5 o 6 | Sí |
| **Alto** | Puntaje de 7 o más | Sí |

Cada nivel tiene un **color y una forma**. Además, el nombre siempre está escrito: no hace falta
distinguir colores para leerlo.

**"sin score"** no es lo mismo que riesgo bajo. Significa que el paciente no tiene una toma con
puntaje, por ejemplo porque todavía no se le cargó ninguna o porque la última quedó sin enviar.

---

## 5. El detalle del paciente

Se abre tocando el nombre en la sala. De arriba hacia abajo muestra:

1. **El puntaje vigente**, con su nivel, la fecha y hora de la toma y cuánto hace.
2. **Aporte de cada parámetro**: los 7 valores y cuántos puntos suma cada uno. Un parámetro
   con 3 puntos (el máximo) aparece marcado con borde rojo. Sirve para ver **de dónde sale el
   número**: un 7 que sale entero de la frecuencia respiratoria no es lo mismo que un 7
   repartido entre todos.
3. **La estimación del modelo** (sección 7).
4. **Alertas por atender** (sección 6).
5. **El historial** de todas las tomas del episodio, de la más nueva a la más vieja.

Si la escala de SpO₂ cambió, una toma vieja conserva la escala con la que se puntuó, y la app
lo aclara.

*Figura 41: detalle de un paciente con riesgo Alto.*

---

## 6. Atender una alerta

Cuando una toma da un nivel distinto de Bajo, se genera una alerta. Aparece en el detalle
del paciente, en **Alertas por atender**, con su nivel, el puntaje y la hora.

Cada alerta se resuelve con **un solo toque**, sin confirmaciones:

- **Validar**: la viste y la estás atendiendo. Sale de la lista.
- **Posponer 30 min**: la alerta se va y **vuelve sola a los 30 minutos** si sigue sin
  resolver. Cuando vuelve, avisa "Pospuesta hasta … · el plazo venció".

Posponer **no es descartar**: la alerta vuelve. Cada acción queda registrada con tu nombre y la
hora en una bitácora que no se puede modificar ni borrar.

Si aparece "No se pudo registrar el acuse", la acción **no** se guardó y la alerta sigue
pendiente. Volvé a intentarlo.

*Figura 42: una alerta pendiente con sus dos botones.*

---

## 7. La estimación del modelo

En el detalle de cada paciente hay un bloque **violeta con borde punteado** llamado
**Estimación del modelo**. Es un modelo de IA que estima el riesgo de muerte a los 30 días a
partir de los mismos signos vitales y la edad.

**No es NEWS2**, y por eso se ve distinto: no usa los colores de la escala. Tené en cuenta lo
siguiente:

- **La escala manda.** Las alertas que tenés que atender salen de NEWS2, no del modelo.
- Dice **"alerta"** o **"sin alerta"** y una probabilidad. Debajo, en una línea, nombra los
  parámetros que más empujan la estimación hacia arriba.
- **Ver desglose completo y límites del modelo** muestra cuánto pesa cada parámetro, el umbral
  que usa y su advertencia. La edad aparece aparte porque no se puede modificar.
- Si dice **"sin estimación"**, el servicio no respondió (a veces tarda en arrancar). **No pasa
  nada**: el NEWS2 y las alertas no dependen del modelo.

*Figura 43: estimación con su explicación.*

---

## 8. Sin conexión

Si se corta la red mientras cargás, **la toma no se pierde**: queda guardada en el dispositivo.

Arriba de cualquier pantalla aparece un recuadro: "**N tomas guardadas en este dispositivo,
sin enviar**", con el paciente, la cama y la hora de cada una. Se envían solas cuando vuelve
la conexión, o podés tocar **Enviar ahora**.

- La hora que queda registrada es **la de la toma**, no la del envío.
- Mientras no se envíen, **no tienen puntaje**.
- No cierres sesión ni borres los datos del navegador con tomas pendientes: están en ese
  dispositivo y en ningún otro lado.

Si el servidor **rechaza** una toma, aparece en el mismo recuadro con el motivo y el botón
**Descartar**. Reintentarla no la arregla: revisá el dato y cargala de nuevo si corresponde.

*Figura 44: tomas pendientes de envío.*

---

## 9. Si cargaste un dato mal

Una toma guardada **no se borra ni se edita**. Esto lo exige la ley: la historia clínica tiene
que conservar cada registro y cada corrección.

La forma prevista de corregir es una **enmienda**: una toma nueva que reemplaza a la errónea y
dice por qué. Las dos quedan en el historial, la vieja marcada como **corregida** y la nueva
con su motivo.

> **Limitación del prototipo.** La base de datos ya admite enmiendas, pero **la aplicación
> todavía no tiene una pantalla para cargarlas**. Si cargaste un dato mal, avisale a
> jefatura. Mientras tanto, no cargues una toma "corregida" como si fuera nueva: quedarían
> dos tomas válidas en lugar de una errónea y una corrección.

---

## Preguntas frecuentes

**¿Por qué no puedo guardar con un parámetro vacío?**
Porque NEWS2 se calcula con los 7. Con seis daría un número más bajo que el real.

**El paciente se ve bien pero la app dice Medio Bajo.**
Hay un parámetro que suma 3 por sí solo, aunque el total sea bajo. Fijate cuál es en el
**Aporte de cada parámetro**. Puede ser un error de carga o un signo real que hay que revisar.

**El modelo dice "alerta" y NEWS2 dice Bajo. ¿A cuál le hago caso?**
A NEWS2 y a tu criterio clínico. El modelo es un complemento en evaluación.

**¿Quién ve lo que cargo?**
Sólo el personal con cuenta activa. Cada toma y cada acción sobre una alerta quedan firmadas
con tu usuario.
