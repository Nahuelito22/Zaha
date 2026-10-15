# Encuadre regulatorio: Zaha como software de uso médico en Argentina

`SCRUM-73` · Épica 6 · Consultado el 14/10/2026

> **Qué es este documento y qué no.** Es el encuadre regulatorio del prototipo para la
> tesis: qué norma aplica, qué diría de Zaha, y qué haría falta para llevarlo a una sala
> real. **No es asesoramiento regulatorio** y no lo firma nadie habilitado para darlo.
> Donde la norma no se pudo verificar en su texto, se dice explícitamente en vez de
> completar con lo que suena razonable.

---

## 1. La pregunta que hay que responder

Zaha calcula NEWS2 sobre signos vitales y agrega una estimación de un modelo. Eso lo pone
cerca de una categoría con nombre propio: **software como producto médico** — *Software as
a Medical Device*, SaMD —, que en Argentina no es una metáfora sino un encuadre con
consecuencias administrativas concretas.

Las tres preguntas, en orden:

1. ¿Zaha es un producto médico bajo la norma argentina?
2. Si lo es, ¿en qué clase de riesgo cae y qué exige registrarlo?
3. ¿Por qué el prototipo de hoy **no** está alcanzado, y qué cambiaría eso?

---

## 2. Qué dice la norma — lo verificado

### 2.1 El software independiente ya está contemplado, y es "producto médico activo"

La **Disposición ANMAT 9688/2019** (DI-2019-9688-APN-ANMAT#MSYDS, firmada el 29/11/2019,
publicada en el Boletín Oficial el 3/12/2019) regula el registro de productos de
tecnología médica de clases I a IV, nacionales e importados: inscripción, modificación,
reválida, transferencia y cancelación.

Lo que importa acá es su **artículo 26**, que alcanza cuatro supuestos:

- software **integrado** en un producto médico,
- software **accesorio**,
- **telemonitoreo** de productos activos implantables,
- y **software independiente**.

Sobre ese último dice dos cosas decisivas:

- que tal software **«deberá estar inscripto por esta Administración Nacional»**;
- que el software independiente **«se considerará producto médico activo»**.

El artículo remite al **Anexo V** para la definición de *software as medical device*. Ese
anexo **no se pudo leer** en las fuentes consultadas, así que la definición exacta que
ANMAT adopta queda sin verificar (ver §7).

El artículo exige además evaluar **diseño del software, gestión de riesgos, y
verificación y validación a lo largo del ciclo de vida**.

### 2.2 La clase de riesgo no la fija 9688/19

9688/19 establece el *procedimiento*; la *clasificación* viene de otra norma. Los productos
médicos se encuadran en clases **I, II, III o IV según el riesgo intrínseco** que
representan para el paciente, el operador o terceros, aplicando las **reglas de
clasificación del Anexo II de la Disposición ANMAT 2318/02** (t.o. 2004, que incorpora el
Reglamento Técnico MERCOSUR), con las modificaciones de la Disposición 727/13.

Entre los factores que determinan el riesgo están la invasividad, el sitio del cuerpo, si
el producto es **activo**, si administra o intercambia energía, y si controla o monitorea
productos activos de clase III.

### 2.3 El procedimiento cambia mucho según la clase

| Clase | Vía de registro | Plazo de ANMAT |
|---|---|---|
| I (ciertos productos del Anexo II parte A) | Declaración jurada | Inmediato: la declaración acredita el registro |
| I restante y II | Declaración de Conformidad | **15** días hábiles |
| **III y IV** | **Evaluación completa de ANMAT** | **110** días hábiles |

El registro **dura cinco años** y se renueva por períodos iguales; la reválida se inicia
dentro de los 30 días hábiles previos al vencimiento. Las observaciones se notifican una
sola vez y hay 30 días hábiles para subsanarlas.

La diferencia entre II y III no es administrativa: son 15 días hábiles contra 110, y un
expediente de otra naturaleza.

---

## 3. ¿Zaha sería un producto médico?

**Sí, si se lo pusiera en el mercado.** No por el stack ni por usar aprendizaje
automático, sino por su **finalidad prevista**: Zaha está destinado a informar una
decisión clínica sobre un paciente identificado, calculando un puntaje de deterioro y
emitiendo alertas. Es software independiente —no viene embebido en un equipo— y el
artículo 26 lo alcanza de lleno.

Dos aclaraciones que suelen confundirse:

**No deja de ser producto médico por calcular una escala publicada.** Que NEWS2 sea un
estándar internacional abierto no cambia la finalidad del software que lo implementa y
dispara alertas sobre pacientes concretos.

**No deja de serlo porque «la decisión la toma el profesional».** Ese argumento sirve para
discutir la *clase de riesgo*, no la condición de producto médico. Un sistema de soporte a
la decisión clínica es, por definición, un intermediario entre el dato y la decisión.

---

## 4. Por qué el prototipo de hoy NO está alcanzado

La norma regula la **inscripción para comercializar o poner en uso** productos médicos. El
estado actual de Zaha queda fuera por cuatro razones acumulativas, y conviene que estén
escritas porque son las que sostienen que el proyecto es legítimo tal como está:

1. **No se comercializa ni se cede a terceros.** Es un trabajo académico de una
   tecnicatura, sin oferta ni contraprestación.
2. **No se usa sobre pacientes reales.** Los datos de la aplicación son sintéticos,
   generados para desarrollo, y los del motor de IA son cohortes de investigación
   anonimizadas y de acceso autorizado.
3. **No está instalado en ningún efector de salud.** No hay una sala usándolo.
4. **Lo declara donde se lo puede leer.** La tarjeta del Space dice, antes que nada, que
   no es un dispositivo médico y que no está autorizado por ANMAT.

**Qué cambiaría el encuadre.** Cualquiera de estas tres bastaría para que el registro pase
a ser obligatorio: instalarlo en un efector aunque sea gratis, usarlo sobre un paciente
real aunque sea un piloto, u ofrecerlo a un tercero. **El límite no es técnico ni
contractual: es el uso.**

---

## 5. La clase de riesgo: lo que se puede afirmar y lo que no

**Lo que se puede afirmar:** Zaha es software independiente, por lo tanto **producto
médico activo** (art. 26). No administra ni intercambia energía con el paciente, no es
invasivo, y no controla ni monitorea un producto activo de clase III: no comanda bombas,
ni ventiladores, ni nada que actúe sobre el cuerpo. Su salida es información en pantalla.

**Lo que NO se puede afirmar sin leer el Anexo II:** la clase concreta. Las reglas de
clasificación del MERCOSUR siguen la lógica de la directiva europea de productos médicos,
donde el software de apoyo a la decisión suele caer en las clases bajas salvo que su
resultado pueda causar un daño grave o la muerte — y una herramienta de **detección
temprana de deterioro** es precisamente un caso donde ese análisis no es automático: un
falso negativo puede retrasar una intervención.

**Este documento no fija una clase.** Afirmar «Zaha es clase II» sin haber aplicado las
reglas del Anexo II sería exactamente el tipo de afirmación cómoda que el proyecto evita
en el resto de la tesis. Queda como pendiente verificable en §7.

### Qué dice el marco internacional, y por qué igual importa

El marco del **IMDRF** categoriza el riesgo de un SaMD cruzando dos ejes: qué tan crítica
es la situación clínica, y qué tanto pesa la información que el software aporta —si
*informa*, si *orienta* o si *decide* el tratamiento.

Zaha **informa**: muestra un puntaje y una estimación, y la decisión y la acción quedan
íntegramente en el personal de salud. Esa es también la razón por la que la interfaz
separa visualmente la predicción del puntaje determinístico (`SCRUM-67`) y por la que la
pantalla declara la limitación del modelo: **no afirmar más de lo que el sistema hace es,
además de honestidad, lo que sostiene el encuadre de menor riesgo.**

> Esta sección describe el marco del IMDRF en términos generales. **No se verificó** que
> ANMAT lo haya adoptado formalmente ni cómo lo mapea a las clases I–IV.

---

## 6. Qué exigiría registrarlo

Del propio artículo 26, el expediente tendría que demostrar tres cosas sobre el ciclo de
vida del software, y **las tres ya tienen trabajo hecho en este proyecto**:

| Exigencia del art. 26 | Dónde está hoy |
|---|---|
| **Diseño del software** | ADRs en `Plan/02_DECISIONES_TECNICAS.md`, con las decisiones y su motivo |
| **Gestión de riesgos** | `SCRUM-75`, pendiente — es el documento que falta |
| **Verificación y validación** | 165 pruebas automatizadas, con los 21 casos clínicos de NEWS2 contra los rangos publicados |

A eso se agregarían, fuera de lo que una tecnicatura puede producir: un sistema de gestión
de calidad, el legajo técnico completo, y un responsable técnico habilitado.

**Lo que ya está y no es poco:** la trazabilidad. El registro de mediciones es
append-only con enmiendas versionadas, y la bitácora de alertas es inalterable con cadena
de hashes — cada fila sella el hash de la anterior, así que una modificación posterior
rompe la cadena y se puede detectar. Para un expediente regulatorio eso no es decorativo:
es la diferencia entre afirmar que el registro es confiable y poder demostrarlo.

---

## 7. Lo que queda sin verificar

Se anota porque la mitad del valor de un encuadre regulatorio es saber dónde termina lo
comprobado:

1. **El Anexo V de 9688/19** — la definición exacta de SaMD que ANMAT adopta. No estaba en
   el texto consultado.
2. **El Anexo II de 2318/02 (t.o. 2004) y la Disposición 727/13** — las reglas de
   clasificación. Sin leerlas no se puede afirmar una clase.
3. **Si ANMAT adoptó formalmente el marco del IMDRF**, y con qué correspondencia a las
   clases I–IV.
4. **Normativa posterior a 2019.** Hay disposiciones más recientes sobre productos médicos
   (por ejemplo 8671/2021) que no se revisaron; conviene confirmar que 9688/19 sigue
   vigente en lo que acá se cita.

Ninguna de las cuatro cambia la conclusión de la §4 —el prototipo no está alcanzado porque
no se pone en uso—, pero las dos primeras son imprescindibles para afirmar una clase.

---

## 8. Conclusión

Zaha **sería** un producto médico en los términos del artículo 26 de la Disposición ANMAT
9688/2019 —software independiente, producto médico activo, sujeto a inscripción— **desde
el momento en que se lo use sobre un paciente real o se lo instale en un efector**. Hoy no
lo está, y la diferencia no es un tecnicismo: es que no se usa.

Lo relevante para la tesis es que el límite está **identificado y declarado**, no evitado.
El proyecto dice en su documentación, en la tarjeta pública del servicio y en la propia
interfaz qué es y qué no es. Ese es, en un trabajo académico sobre software clínico, el
encuadre correcto: no pretender una autorización que no se tiene, y saber exactamente qué
haría falta para tenerla.

---

## Fuentes

- [Disposición 9688/2019 — texto oficial, argentina.gob.ar](https://www.argentina.gob.ar/normativa/nacional/norma-332646/texto)
- [Disposición 9688/2019 — Boletín Oficial, 3/12/2019](https://www.boletinoficial.gob.ar/detalleAviso/primera/222600/20191203)
- [Disposición 9688/2019 — e-legis-ar, Ministerio de Salud](https://e-legis-ar.msal.gov.ar/htdocs/legisalud/migration/pdf/34470.pdf)
- [Disposición 5706/2017 — clasificación por riesgo y reglas del Anexo II](https://www.argentina.gob.ar/normativa/nacional/norma-275426/texto)
- [Disposición 8671/2021 — normativa posterior, sin revisar](https://www.argentina.gob.ar/normativa/nacional/norma-357173/texto)
