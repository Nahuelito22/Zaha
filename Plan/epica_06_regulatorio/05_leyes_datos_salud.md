# Encuadre legal: datos personales e historia clínica electrónica

`SCRUM-74` · Épica 6 · Escrito el 19/10/2026

> **Qué es este documento.** Qué exigen la **Ley 25.326** (protección de datos personales)
> y la **Ley 27.706** (historia clínica electrónica) a un sistema como Zaha, artículo por
> artículo, y qué hace el sistema con cada exigencia. Los artículos se leyeron del **texto
> oficial** el 19/10/2026, no se citan de memoria; las fuentes están al final. También se
> usa la **Ley 26.529** (derechos del paciente), porque la 27.706 remite a ella.
>
> **Qué NO es.** No es un dictamen jurídico. Lo escribe un equipo de desarrollo para saber
> qué tiene que garantizar el software. Donde la ley deja una pregunta abierta (por ejemplo,
> si un hospital tiene que inscribir la base), se dice que está abierta y no se la contesta.

---

## La situación de partida

Zaha es un **prototipo académico** que hoy sólo guarda **datos ficticios**: los pacientes
de la sala de desarrollo son inventados, y el aviso de que no es un dispositivo médico está
en todas las pantallas (gestión de riesgos, R16). Mientras eso sea así, ninguna de estas
leyes se está aplicando sobre una persona real.

El análisis igual vale por dos razones. Primero, el diseño tiene que **sostenerse el día que
haya pacientes reales**: es más barato que la base ya sea append-only que agregarlo después.
Segundo, varias decisiones ya tomadas se justificaron citando la ley (el ADR-008 cita el
art. 9 de la 25.326), y eso hay que poder respaldarlo con el texto.

Lo que Zaha guarda de cada paciente: nombre, apellido, número de historia clínica, fecha de
nacimiento, sexo, la internación (cama, fechas) y las tomas de signos vitales con su puntaje
NEWS2. De cada usuario: nombre, rol y matrícula.

---

## Ley 25.326: protección de los datos personales

### Los datos de Zaha son datos sensibles

El art. 2 define como **datos sensibles** los que revelan, entre otras cosas, "información
referente a la salud". Todo lo que Zaha guarda de un paciente cae ahí: un nombre junto a una
saturación de oxígeno es un dato de salud.

El art. 7.2 dice que los datos sensibles sólo se tratan cuando "medien razones de interés
general autorizadas por ley". La autorización para el caso de Zaha es el **art. 8**: los
establecimientos sanitarios y los profesionales de la salud pueden recolectar y tratar los
datos de salud de sus pacientes, "respetando los principios del secreto profesional".

**Consecuencia de diseño:** Zaha no puede ser un servicio que trate datos de salud por su
cuenta. Lo opera el establecimiento, para sus profesionales. Es lo que ya hace el sistema:
no hay registro abierto, las cuentas las crea el administrador (`02_seguridad_supabase.md`)
y cada usuario tiene rol y matrícula.

### Consentimiento (art. 5)

El art. 5.1 hace ilícito el tratamiento sin "consentimiento libre, expreso e informado", pero
el 5.2 lo exceptúa cuando los datos derivan de una "relación contractual, científica o
profesional del titular" y son necesarios para su desarrollo (inc. d). La atención en una
guardia es esa relación profesional. **Zaha no pide un consentimiento aparte para registrar
signos vitales**, y no tendría que hacerlo: sería un formulario más en el peor momento.

Lo que sí cambia es si los datos se usaran **para otra cosa**, por ejemplo para reentrenar el
modelo. Eso ya no es atención del paciente; ver "Lo que queda abierto".

### Calidad y finalidad (art. 4)

| Exige | Qué hace Zaha |
|---|---|
| Datos "ciertos, adecuados, pertinentes y no excesivos" (4.1) | Se guardan los 7 parámetros de NEWS2 y lo mínimo para identificar al paciente. No hay diagnóstico, medicación, domicilio ni documento |
| No usarlos para finalidades distintas (4.3) | Los datos sólo alimentan la escala, la alerta y la estimación del modelo para ese mismo paciente |
| Exactos y actualizados (4.4) | Rangos plausibles en tres capas (pantalla, base, servicio) y enmiendas con motivo (R05) |
| Destruirlos cuando dejen de ser necesarios (4.7) | **No resuelto.** Choca con la obligación de conservar la historia clínica; ver art. 16 |

### Seguridad (art. 9)

El art. 9.1 exige "las medidas técnicas y organizativas que resulten necesarias para
garantizar la seguridad y confidencialidad de los datos personales", y además que permitan
**detectar desvíos**, intencionales o no. El 9.2 prohíbe registrar datos en archivos "que no
reúnan condiciones técnicas de integridad y seguridad".

| Medida | Dónde está | Riesgo |
|---|---|---|
| Sólo usuarios autenticados con perfil activo ven datos (RLS en todas las tablas) | `supabase/migrations/20260521000200_rls_policies.sql` | R13 |
| Registro cerrado: no se puede crear una cuenta desde afuera (verificado: el alta responde 422) | `02_seguridad_supabase.md` | R13, R14 |
| Las funciones con privilegios no se pueden llamar sin sesión (verificado: 42501) | ídem | R13 |
| Las tomas de signos vitales no se pueden modificar ni borrar: un trigger lo impide incluso con la clave de servicio | `guard_vital_record_immutable()` | R05 |
| Cada evento de una alerta queda en una bitácora append-only con cadena de hashes, verificable con `verificar_cadena_auditoria()` | ADR-008 | R12 |
| Tráfico cifrado (HTTPS en el dominio de producción y en la API) | `vercel.json` | — |

La bitácora con cadena de hashes es justamente la medida para **detectar desvíos**: si
alguien altera una fila por fuera de la aplicación, la cadena deja de cerrar.

### Confidencialidad (art. 10)

El art. 10.1 obliga al secreto profesional a todas las personas "que intervengan en cualquier
fase del tratamiento", y la obligación sigue después de terminada la relación. Para el
software, la parte que le toca es **no mostrar datos de más**:

- La función de predicción no distingue entre "el paciente no existe" y "no lo podés ver",
  para no filtrar que existe (`supabase/functions/prediccion/index.ts`).
- El login no distingue entre correo inexistente y contraseña incorrecta.
- Los registros del servidor nunca incluyen el token ni datos del paciente.

### Cesión y transferencia (arts. 11 y 12)

Zaha le manda datos a un tercero en un solo lugar: la estimación del modelo, que corre en un
Space de Hugging Face. **Lo que viaja son los siete signos vitales y la edad en el momento de
la toma.** No viaja el nombre, ni la historia clínica, ni la fecha de nacimiento, ni la fecha
de la toma (`aObservacion` en `supabase/functions/prediccion/mapeo.ts`).

Eso se acerca a lo que el art. 2 llama **disociación**, un tratamiento tal que la información
"no pueda asociarse a persona determinada o determinable", y el art. 11.3 (e) exceptúa del
consentimiento la cesión de datos disociados. Pero que una edad con siete números no
identifique a nadie es una **afirmación razonable, no algo demostrado**, así que no se la
presenta como cumplimiento. Lo mismo con el art. 12, que prohíbe transferir datos a países
sin protección adecuada: el servidor de Hugging Face no está en Argentina, y si los datos
contaran como personales habría que encuadrar esa transferencia. En una implementación real,
lo prudente es correr el modelo **dentro de la infraestructura del hospital**. El ONNX ya
está pensado para eso: no depende de Hugging Face.

### Derechos del titular (arts. 14, 15 y 16)

| Derecho | Qué exige | Qué hace Zaha |
|---|---|---|
| Acceso (14) | Responder dentro de los diez días corridos | **No hay una vía para el paciente.** Zaha es una herramienta del personal; el acceso del paciente le corresponde a la historia clínica del hospital. El exportador FHIR (`SCRUM-71`) es lo que permitiría entregarle sus datos en un formato estándar |
| Contenido (15) | Información clara, "exenta de codificaciones" | El Bundle FHIR está codificado (LOINC). Para el paciente haría falta una versión legible |
| Rectificación (16.1) | Corregir los datos erróneos en cinco días hábiles | **Sí, y sin perder el original.** Una enmienda reemplaza la toma con motivo y autor, y la original queda sellada como reemplazada |
| Supresión (16.1) | Suprimir los datos | **No se puede, a propósito.** El 16.5 dice que la supresión no procede cuando hay obligación legal de conservar los datos, y la Ley 26.529 (art. 18) obliga a guardar la historia clínica un mínimo de diez años |

### Inscripción de la base (art. 21) y órgano de control

El art. 21.1 obliga a inscribir en un registro "todo archivo, registro, base o banco de datos
público, y privado destinado a proporcionar informes", y el art. 24 extiende la obligación a
los particulares que formen archivos que no sean "para un uso exclusivamente personal".
**Si una base clínica de un hospital entra en esa categoría es una pregunta legal que el
texto no contesta**, y no la contesta este documento. Lo que sí está claro es que la
inscripción, si corresponde, la hace **el establecimiento que opera el sistema**, no el
equipo que lo desarrolla.

El órgano de control está previsto en el art. 29, y el art. 45 dejó en manos del Poder
Ejecutivo establecerlo. **El texto de la ley no dice cuál es hoy**, y no se verificó en el
decreto correspondiente, así que no se lo nombra acá.

---

## Ley 27.706: historia clínica electrónica

Sancionada el 28/02/2023 y publicada en el Boletín Oficial el 16/03/2023, crea el **Programa
Federal Único de Informatización y Digitalización de Historias Clínicas**, "con la finalidad
de instaurar, en forma progresiva, el Sistema Único de Registro de Historias Clínicas
Electrónicas" (art. 1). El art. 1 la subordina a la Ley 26.529 y a la 25.326.

### ¿Zaha es una historia clínica electrónica?

**No.** Zaha es un sistema de soporte a la decisión que registra signos vitales y calcula una
escala. No tiene evolución, indicaciones, estudios ni consentimientos. Pero **lo que registra
es contenido de historia clínica**: una toma de signos vitales es una "actuación realizada al
paciente por profesionales y auxiliares de la salud" (Ley 26.529, art. 12). En un hospital
real, Zaha sería un módulo que **alimenta** la historia clínica, no la reemplaza. Por eso
sus registros tienen que cumplir las mismas condiciones, y por eso existe el exportador FHIR.

### Lo que exige y lo que hace Zaha

| Artículo | Exige | Qué hace Zaha | Estado |
|---|---|---|---|
| 4 | La información no puede alterarse "sin que quede registrada la modificación pertinente", aunque sea para corregir un error | Tomas append-only; la corrección es una enmienda con motivo, autor y fecha, y la original queda | ✅ Signos vitales · ⚠️ Datos del paciente: ver brechas |
| 5 y 7 (a) | Consulta "restringida a quien esté autorizado"; tres niveles de acceso: consulta, consulta y actualización, y modificación | Roles enfermería, medicina y jefatura; sin sesión no se ve nada | ⚠️ Ver brechas |
| 6 (b) y 7 (e) | **Trazabilidad**: cada acción asociada "de modo inequívoco a un individuo", "dejando rastro del respectivo acceso" | Cada toma lleva `recorded_by` (la base exige que sea el usuario de la sesión) y cada evento de alerta queda en la bitácora | ⚠️ Escrituras sí, lecturas no |
| 6 (c) | Mecanismos de autenticación de los profesionales | Correo y contraseña, con cuentas creadas por el administrador | ⚠️ Sin segundo factor |
| 6 (f) | Sistema "auditable e inspeccionable" | `verificar_cadena_auditoria()` comprueba la cadena entera; verificada intacta con 22 eventos | ✅ |
| 7 (b) | Impedir que los datos sean "leídos, copiados o retirados por personas no autorizadas" | RLS, registro cerrado, funciones sin acceso anónimo | ✅ |
| 7 (c) | **Integridad**: la información permanece "completa e inalterada" o sólo la modifica la persona autorizada | Trigger de inmutabilidad + cadena de hashes | ✅ |
| 8 | Documento "con marca temporal" y "refrendado con la firma digital del responsable" | Marca temporal en cada toma (`recorded_at` y `created_at`) | ❌ No hay firma digital |
| 2 (d) | Un "marco de interoperabilidad" entre los sistemas existentes y los nuevos | Exportador a FHIR R4 validado contra el esquema oficial (`03_mapeo_fhir.md`) | ✅ Como exportación; no hay intercambio en vivo |

Sobre la interoperabilidad: la ley no nombra ningún estándar (ni HL7 ni FHIR). Le deja a la
autoridad de aplicación la definición de las características técnicas (art. 2, b y c). FHIR
se eligió porque es el estándar internacional vigente, no porque la ley lo exija.

---

## Las brechas, ordenadas

Ninguna es un problema mientras los datos sean ficticios. Todas lo serían con un paciente
real, y por eso se escriben.

1. **No hay firma digital** (Ley 27.706, art. 8). La autoría de una toma está garantizada por
   la base (`recorded_by` es siempre el usuario de la sesión), pero eso es autenticación, no
   firma digital en el sentido de la ley. Resolverlo implica certificados por profesional;
   está fuera del alcance de un prototipo.
2. **Las lecturas no dejan rastro** (art. 7 e). Se sabe quién cargó y quién reconoció cada
   cosa, pero no quién **miró** la ficha de un paciente. Es la brecha más barata de cerrar:
   una tabla de accesos escrita desde las mismas funciones que ya leen.
3. **Los datos del paciente se pueden editar sin historial** (art. 4). Las tomas son
   append-only, pero nombre, historia clínica y fecha de nacimiento se actualizan en el
   lugar: queda la fecha del último cambio, no qué decía antes ni quién lo cambió.
4. **Todo el personal activo ve a todos los pacientes** (arts. 5 y 7 a). Los roles existen,
   pero el acceso no se restringe por servicio ni por asignación. En una guardia chica es
   razonable; en un hospital no.
5. **Sin segundo factor de autenticación** (art. 6 c). La protección contra contraseñas
   filtradas no está disponible en el plan gratuito (R14, aceptado).
6. **El modelo corre fuera del país** (Ley 25.326, art. 12). Lo que viaja no identifica al
   paciente, pero eso no está demostrado. En producción, el modelo tiene que correr en la
   infraestructura del hospital.

## Lo que queda abierto

- **Reentrenar el modelo con datos del hospital** sería una finalidad distinta de la atención
  (Ley 25.326, art. 4.3). Haría falta disociar los datos (art. 7.2 admite fines científicos
  si los titulares no pueden ser identificados) o un consentimiento, además de la aprobación
  de un comité de ética. Hoy no pasa: el modelo se entrenó con cohortes públicas.
- **La conservación contra la destrucción.** El art. 4.7 de la 25.326 pide destruir los datos
  que ya no hacen falta y el art. 18 de la 26.529 obliga a guardar la historia clínica diez
  años como mínimo. Gana la obligación de conservar (art. 16.5), pero el plazo de borrado
  después de esos diez años lo define el establecimiento, no el software.
- **La inscripción de la base** (art. 21) y **el órgano de control** actual: ver arriba.
- **El decreto reglamentario de la 27.706.** No se pudo leer del texto oficial (la búsqueda en
  argentina.gob.ar no lo devolvió), así que este documento se apoya sólo en la ley.

---

## Fuentes

Leídas el 19/10/2026:

- Ley 25.326, texto actualizado en InfoLEG:
  https://servicios.infoleg.gob.ar/infolegInternet/anexos/60000-64999/64790/texact.htm
- Ley 27.706, texto en argentina.gob.ar:
  https://www.argentina.gob.ar/normativa/nacional/ley-27706-380710/texto
- Ley 26.529, texto actualizado en InfoLEG:
  https://servicios.infoleg.gob.ar/infolegInternet/anexos/160000-164999/160432/texact.htm

Documentos del proyecto que este complementa: `01_samd_anmat.md` (encuadre como software
médico), `02_seguridad_supabase.md` (lo verificado de la base), `03_mapeo_fhir.md`
(interoperabilidad) y `04_gestion_riesgos.md` (R05, R12, R13, R14, R16).
