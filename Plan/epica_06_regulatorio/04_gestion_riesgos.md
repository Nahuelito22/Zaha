# Gestión de riesgos del sistema

`SCRUM-75` · Épica 6 · 19/10/2026

> **Qué es este documento.** La identificación de los peligros que el sistema puede
> generar, cuánto pesa cada uno, qué control lo reduce y qué riesgo queda después. Cada
> control nombra **dónde está implementado o verificado**: un control que no se puede
> señalar en el código o en una medición no cuenta como control.
>
> **Qué no es.** Sigue la estructura habitual de la gestión de riesgos de un producto
> médico (uso previsto, identificación de peligros, estimación, control y riesgo
> residual), pero **no es una aplicación certificada de ninguna norma** ni la firma nadie
> habilitado para hacerlo. Las escalas de severidad y probabilidad las define el proyecto.
> El encuadre regulatorio está en `01_samd_anmat.md`.

---

## 1. Uso previsto

Zaha es un sistema de soporte a la decisión para **personal de enfermería** de sala o
guardia. Calcula el puntaje NEWS2 sobre los signos vitales que se cargan al pie de la cama,
ordena la sala por riesgo, emite alertas y muestra una **estimación de un modelo** junto a
la escala.

**Informa, no decide.** La valoración clínica y la conducta quedan siempre en el
profesional. En el marco del IMDRF, ese es el nivel de menor peso: *informar* (ver
`01_samd_anmat.md`).

**Estado actual:** prototipo académico, publicado en `zahasalud.com.ar` con **pacientes
ficticios y usuarios de prueba**. No se usó sobre pacientes reales. Los riesgos se evalúan
**como si se usara en una sala**, porque eso es lo que una gestión de riesgos tiene que
anticipar.

## 2. Escalas

**Severidad del daño posible**

| | Nivel | Qué significa |
|---|---|---|
| S1 | Menor | Molestia o demora sin consecuencia clínica |
| S2 | Moderada | Demora en la atención que podría empeorar el cuadro |
| S3 | Grave | Deterioro no detectado a tiempo, con daño reversible |
| S4 | Crítica | Deterioro no detectado que puede llevar a la muerte o a un daño permanente |

**Probabilidad, si se usara en una sala**

| | Nivel | Qué significa |
|---|---|---|
| P1 | Remota | Requiere una falla combinada de varios controles |
| P2 | Ocasional | Puede ocurrir en condiciones poco habituales |
| P3 | Probable | Ocurriría con el uso normal en algún momento |
| P4 | Frecuente | Ocurriría con el uso normal de forma repetida |

**Aceptabilidad** (S × P): **1–3 aceptable**, **4–6 aceptable con controles y
seguimiento**, **8 o más no aceptable** sin reducirlo.

## 3. Resumen

| ID | Peligro | Inicial | Controles principales | Residual | Estado |
|---|---|---|---|---|---|
| R01 | NEWS2 no detecta un deterioro (falso negativo) | S4·P3 = 12 | La escala completa con sus 7 parámetros y el rojo aislado; aviso de que no reemplaza el criterio | S4·P3 = **12** | ⚠️ Inherente a NEWS2: aceptado sólo como prototipo |
| R02 | La estimación del modelo se toma como diagnóstico o como la escala | S3·P3 = 9 | Separación visual, "no es NEWS2", estado `preliminary` en FHIR, advertencia en cada respuesta | S3·P2 = 6 | Controlado |
| R03 | El modelo opera con un umbral mal calibrado | S3·P3 = 9 | Prueba del umbral, medición contra producción | S3·P1 = 3 | **Ocurrió**, corregido |
| R04 | Fatiga de alarmas | S3·P4 = 12 | Regla de alerta exacta, posponer distinto de descartar, la tesis misma | S3·P3 = **9** | ⚠️ Abierto: es el problema que el proyecto ataca |
| R05 | Error de carga de un valor | S3·P3 = 9 | Rangos plausibles en tres capas, enmiendas con motivo | S3·P2 = 6 | Controlado |
| R06 | Una toma cargada sin señal queda sin puntaje ni alerta | S3·P2 = 6 | Se muestra "sin puntaje" de frente; sincroniza sin duplicar | S3·P2 = 6 | Controlado con seguimiento |
| R07 | Se lee un dato viejo como actual | S2·P3 = 6 | Antigüedad de cada toma a la vista | S2·P1 = 2 | Controlado |
| R08 | El servicio de IA no responde | S2·P3 = 6 | Degradación elegante: NEWS2 no depende del modelo | S1·P3 = 3 | Controlado |
| R09 | El modelo no generaliza a la población local | S3·P4 = 12 | Declarado en cada respuesta; la escala sigue siendo la referencia | S3·P4 = **12** | ⚠️ Abierto: requiere validación local |
| R10 | NEWS2 se calcula distinto en dos lugares | S4·P2 = 8 | Fuente única en la base; verificación contra la investigación | S4·P1 = 4 | Controlado |
| R11 | Escala de SpO₂ mal aplicada (paciente hipercápnico) | S3·P2 = 6 | La escala es prescripción médica por internación, nunca inferida | S3·P2 = 6 | Controlado con seguimiento |
| R12 | Se altera la bitácora de auditoría | S3·P2 = 6 | Append-only sin excepciones + cadena de hashes | S3·P1 = 3 | Controlado, con un límite abierto |
| R13 | Acceso no autorizado a datos de pacientes | S3·P3 = 9 | RLS por rol, registro cerrado, funciones sin acceso anónimo | S3·P1 = 3 | Controlado |
| R14 | Una cuenta con contraseña filtrada | S3·P2 = 6 | Cuentas creadas por el administrador | S3·P2 = 6 | Aceptado: la protección exige plan pago |
| R15 | La explicación del modelo señala el parámetro equivocado | S2·P2 = 4 | Sólo se muestra si reconstruye exactamente la probabilidad | S2·P1 = 2 | Controlado |
| R16 | Se usa el prototipo sobre un paciente real | S4·P2 = 8 | Aviso en la landing, la demo, el login y todas las pantallas de la app; datos ficticios; registro cerrado | S4·P1 = 4 | Controlado con seguimiento |

## 4. Detalle de cada riesgo

### R01 — NEWS2 no detecta un deterioro
**Situación.** Un paciente que va a deteriorarse puntúa bajo y no genera alerta.
**Evidencia de que es real.** Medido sobre la cohorte TRIAGE con el sistema publicado:
NEWS2 detecta **29 de 54 muertes a 30 días (53,7 %)**. Es el caveat de NEWS2 en guardia
(`Plan/epica_04_motor_ia/02_caveat_news2_urgencias.md`, ADR-006): la escala se diseñó
para sala general.
**Controles.** La escala completa —los siete parámetros, ninguno omitido— y la regla de
alerta real (`riesgo distinto de Bajo`, que incluye el rojo aislado), verificada contra el
trigger de producción. El sistema informa; no reemplaza la valoración.
**Residual.** Sigue alto, porque es una limitación de la escala y no del software. Es
aceptable **sólo** para un prototipo: un despliegue real lo trataría con la validación
local del R09.

### R02 — La estimación se confunde con la escala o con un diagnóstico
**Situación.** El profesional lee "alerta 99,4 %" del modelo como si fuera NEWS2, o como
certeza.
**Controles.** En la app, la estimación va en violeta con borde punteado, fuera de los
colores de riesgo, con la etiqueta "no es NEWS2" (`componentes/Prediccion.tsx`). Cada
respuesta trae la advertencia de que la reducción de alertas no está demostrada. En FHIR,
la estimación es un `RiskAssessment` en estado `preliminary` y NEWS2 en estado `final`
(`03_mapeo_fhir.md`). La alerta del modelo **sólo se muestra**: verificado el 19/10 que
todas las alertas registradas en producción son de NEWS2.

### R03 — El modelo opera con un umbral mal calibrado (ocurrió)
**Qué pasó.** Desde el Sprint 5 hasta el 19/10, el umbral publicado se calculaba sobre
todos los pacientes y no sobre los que tuvieron el evento. A "sensibilidad 70 %", el
modelo marcaba alerta en el **70 % de los pacientes**, cuando su propia documentación
anunciaba 28,5 %.
**Por qué el daño quedó acotado.** La alerta del modelo sólo se muestra, nunca se registra
ni se suma a la sala (R02), y NEWS2 no dependía de ella.
**Controles agregados.** Una prueba que exige que el umbral publicado dé la sensibilidad
que promete, y que falla con la lógica vieja (`tests/test_exportar.py`). Y una medición
repetible del sistema publicado contra la investigación
(`ml_engine/src/evaluacion/tasa_produccion.py`). Corregido y republicado el 19/10.
**Lección.** Las pruebas verificaban que el modelo servido fuera igual al evaluado, y lo
era. Nadie verificaba lo que el umbral prometía.

### R04 — Fatiga de alarmas
**Situación.** Con demasiadas alertas, el personal deja de atenderlas, incluidas las
verdaderas.
**Evidencia.** La regla de NEWS2 alerta al **25,7 %** de los pacientes de la cohorte.
**Controles.** Es el problema que el proyecto ataca (ADR-005): la comparativa a
sensibilidad igualada. En la app, **posponer no es descartar**: una alerta pospuesta vuelve
cuando vence su plazo y no cuenta como falsa alarma (`lib/alertas.ts`).
**Residual.** Abierto. La reducción de alertas del modelo está **medida pero no
demostrada**: −29,8 %, con un intervalo de confianza que incluye el cero.

### R05 — Error de carga
**Situación.** Se tipea una saturación de 19 en vez de 91.
**Controles.** Rangos fisiológicamente plausibles en **tres capas** que se verifican entre
sí: el formulario, la API (`rangos.py`) y los `CHECK` de la base. Un valor imposible se
rechaza; nunca produce un puntaje. Para corregir, una **enmienda** que exige motivo escrito
y deja el valor original visible.
**Residual.** Un valor erróneo pero plausible (88 en vez de 98) no se puede detectar
automáticamente.

### R06 — Toma cargada sin señal
**Situación.** En una sala sin conectividad, la toma queda en el dispositivo y todavía no
tiene puntaje ni dispara alerta.
**Controles.** La cola offline la muestra **sin puntaje, dicho de frente**, en vez de
calcular uno local que podría no coincidir con el de la base. Al volver la señal, la
sincroniza **sin duplicar**: el identificador se genera en el dispositivo, y un reintento
que ya había entrado se reconoce (`lib/cola.ts`).
**Residual.** Mientras no hay señal, la alerta no existe. Es el costo de que haya un solo
motor de cálculo válido, y se acepta con el aviso visible.

### R07 — Dato viejo leído como actual
**Control.** Cada fila del tablero dice hace cuánto se tomó ese dato, y el texto se
actualiza solo (`lib/reloj.ts`).

### R08 — El servicio de IA no responde
**Control.** Degradación elegante (ADR-004, SCRUM-65): si el servicio del modelo está
caído o dormido, la pantalla lo dice en una línea discreta y **NEWS2 sigue funcionando**,
porque se calcula en la base y nunca consulta al modelo.

### R09 — El modelo no generaliza a la población local
**Situación.** El modelo se entrenó con 1.303 pacientes de guardia de EE.UU. (72 %),
Francia y Suiza. Una guardia argentina puede ser distinta.
**Controles.** Está declarado en el modelo y en la tesis. La escala, validada
internacionalmente, sigue siendo la referencia, y el modelo se presenta como estimación.
**Residual.** Abierto. Requiere validar el modelo sobre datos locales antes de cualquier
uso real.

### R10 — NEWS2 calculado distinto en dos lugares
**Situación.** La investigación calcula NEWS2 en Python y la aplicación en SQL. Si
divergen, la tesis describe un sistema que no existe.
**Controles.** La base es la única fuente que vale en la aplicación: la cola offline ni
siquiera calcula un puntaje local. Verificado el 19/10: las funciones de producción y las de
la investigación dan **el mismo puntaje en los 1.300 pacientes** de la cohorte. Una prueba
lee la migración SQL y falla si la regla de alerta se desincroniza.

### R11 — Escala de SpO₂ mal aplicada
**Situación.** Un paciente con EPOC e hipercapnia necesita la escala 2 de saturación; con
la escala 1 puntuaría alto sin motivo.
**Control.** La escala es una **prescripción médica** por internación y nunca se infiere de
si el paciente tiene oxígeno. Cada toma guarda la escala con la que se puntuó, así que el
puntaje es reproducible aunque la prescripción cambie.
**Residual.** Depende de que la prescripción se cargue bien.

### R12 — Alteración de la bitácora de auditoría
**Controles.** Las dos capas del ADR-008: append-only sin excepciones, ni siquiera para la
clave de servicio, y cadena de hashes. Verificada íntegra en producción el 19/10, con 22
eventos.
**Límite abierto.** Quien tenga privilegios de dueño de la base puede desactivar el trigger
y **recalcular la cadena entera**: la verificación no lo notaría, porque no hay contra qué
comparar. Se mitigaría publicando periódicamente el último hash en un lugar que la base no
controla. **No está implementado.**

### R13 — Acceso no autorizado
**Controles.** RLS en todas las tablas, por rol. El registro público está cerrado. Las
funciones expuestas no son accesibles para un anónimo. Todo verificado desde afuera
(`02_seguridad_supabase.md`).

### R14 — Cuenta con contraseña filtrada
**Situación.** La protección que rechaza contraseñas filtradas requiere el plan pago.
**Control sustituto.** Con el registro cerrado, las cuentas las crea el administrador.
**Residual.** Aceptado para el prototipo. En un despliegue real: activarla, o usar el
inicio de sesión institucional del hospital.

### R15 — La explicación señala el parámetro equivocado
**Control.** La explicación es la descomposición **exacta** de la regresión logística, y se
muestra sólo si reconstruye la probabilidad servida. Si no, se oculta: una explicación
equivocada de una alerta clínica es peor que ninguna. La edad va aparte, porque no es
accionable al pie de la cama.

### R16 — Uso del prototipo sobre un paciente real
**Situación.** El sistema está publicado. Alguien podría cargar a un paciente real.
**Controles.** El aviso "no es un dispositivo médico" en la landing, en la demo, debajo del
login y en **una franja fija debajo del encabezado de todas las pantallas de la
aplicación** (`App.tsx`, `Login.tsx`). Más los pacientes ficticios y el registro cerrado.
**Cómo se cerró.** Al escribir este documento se encontró que la aplicación no mostraba el
aviso en ninguna pantalla: quien entraba directo a `/app` no lo veía. Se agregó el 19/10.
Va en gris neutro y no en los colores de riesgo, para no competir con las alertas, y es
corto para ocupar sólo dos renglones en un teléfono.
**Residual.** Un aviso no impide el uso: lo vuelve una decisión consciente. Por eso el
residual baja de probabilidad pero no desaparece.

## 5. Riesgo residual global

El software controla lo que es suyo. Los errores de cálculo, de carga, de conectividad, de
acceso y de auditoría tienen controles verificados. El error que ocurrió (R03) se detectó
por una medición del propio proyecto y se corrigió el mismo día, y el control que faltaba
para el uso indebido (R16, el aviso dentro de la aplicación) se agregó al escribir este
documento.

Lo que queda alto no es del software sino del problema: **NEWS2 en guardia pierde la mitad
de los eventos (R01)**, **el modelo no está validado en la población local (R09)** y **la
reducción de alertas no está demostrada (R04)**. Por eso el riesgo residual global es
aceptable **para un prototipo académico con datos ficticios, y no para el uso clínico**.
Pasar al uso clínico exigiría, como mínimo, cerrar R09 con datos locales y R12 con el ancla
externa, y la autorización regulatoria del `01_samd_anmat.md`.

## 6. Cuándo revisar este documento

- Cuando cambie el modelo, sus umbrales o la cohorte de entrenamiento.
- Cuando cambie la regla de alerta o el cálculo de NEWS2.
- Cuando se reproduzca la medición de `tasa_produccion.py` y dé distinto.
- Antes de cualquier uso con pacientes reales.
