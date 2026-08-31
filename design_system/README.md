# Sistema de diseño de Zaha

Dos capas separadas a propósito. No se mezclan.

| Capa | Archivo | Dónde se usa | Cromática |
| --- | --- | --- | --- |
| **Marca** | `brand.css` | Landing `/`, splash, login/registro, onboarding, ícono de app, footer | Paleta tierra completa (terracota + salvia) |
| **Clínica** | `clinical.css` | Todo `/app`: dashboard, carga de vitales, detalle, alertas | Neutros fríos de alto contraste + acento azul |

La capa clínica se activa poniendo `class="zaha-clinical"` en el contenedor raíz de cada
pantalla de `/app`. Todos sus tokens y clases están namespaceados bajo esa clase.

> ⚠️ **La simetría no existe: `brand.css` NO está namespaceado.** Define sobre `:root` y
> `body` globales, así que importarlo en el bundle de `app/clinical` pisaría la capa
> clínica de TODA la aplicación, no solo de la pantalla que lo pida — exactamente el
> escenario de fatiga de alarma que estas dos capas existen para evitar. Antes de aplicar
> la capa de marca al login (SCRUM-36) hay que encerrar `brand.css` bajo una clase raíz,
> igual que `clinical.css`.
>
> Por eso la clase clínica va en la raíz de **cada pantalla** y no en la raíz de la
> aplicación: el login pertenece a la capa de marca, y colgarla del root lo metía a la
> fuerza en la capa equivocada.

## Por qué están separadas

La terracota de marca (`#c67139`) ocupa el mismo rango cromático que el rojo y el ámbar de
alerta NEWS2. Si tiñe la interfaz clínica pasan dos cosas malas a la vez:

1. Elementos neutros **parecen** alerta → fatiga de alarma, exactamente lo que el proyecto
   dice querer reducir (ADR-005: la métrica principal es tasa de alertas a sensibilidad
   igualada, referencia a batir 37,6 alertas / 100 pacientes-día).
2. La alerta real **no destaca**, porque todo alrededor ya es de ese color.

Es la misma tesis del proyecto aplicada a la interfaz: si el diseño produce alertas de más,
contradice el trabajo.

## Reglas innegociables de `/app`

- **Rojo, ámbar, naranja y verde están reservados** en exclusiva para los 4 niveles de riesgo
  NEWS2 (Bajo / Medio Bajo / Medio / Alto). Ningún otro elemento de `/app` puede usar esos
  hues — ni un botón de "guardar" verde, ni un badge naranja de "nuevo".
- **Codificación redundante siempre**: color **+** texto **+** forma. Nunca un punto de color
  solo. Los glifos de `.risk-*` cambian de forma por nivel (círculo · rombo · triángulo ·
  triángulo relleno) para que el nivel se lea sin color.
- **La predicción de IA no entra en la escala NEWS2.** Va en violeta y con borde punteado
  (`.predict`), para que el usuario distinga "esto lo calculó la escala" de "esto lo estimó
  un modelo". Si el Space de Hugging Face duerme, ese bloque desaparece y NEWS2 se sigue
  mostrando igual (ADR-004).
- **Dato faltante ≠ dato normal.** Un NEWS2 calculado sobre vitales incompletos se marca con
  `.score-incomplete` y los vitales sin cargar con `.missing`.
- **Antigüedad visible.** Un NEWS2 de hace 6 h no vale lo mismo que uno de hace 10 min:
  `.staleness` / `.staleness-overdue`.
- **Targets de 44 px mínimo.** Se carga con guantes, en una tablet, de pie. `.cbtn-sm`
  (36 px) existe **solo** para chrome no clínico: salir de la sesión, cerrar un panel.
  Ningún botón que se toque durante la ronda baja de 44 px.
- **Nada de tamaños de texto sueltos.** La escala de cuerpo es `.ctext-lead` (16) /
  `.ctext` (15) / `.ctext-sm` (14) / `.ctext-xs` (13) / `.ctext-2xs` (12), y el color
  secundario es `.ctext-muted`. Si hace falta un sexto tamaño, se agrega acá, no en la
  pantalla.
- **`.ctext-faint` nunca lleva información clínica.** Da 3.0:1 sobre el fondo y no alcanza
  AA; sirve para un placeholder o un separador. `.ctext-muted` sí es legible (6.1:1, pasa
  AA y AAA para texto normal).
- Iconografía funcional convencional en `/app`. Los 5 íconos de marca (caminos de la vida,
  corazón, sol, tierra, equilibrio) son para landing y onboarding.

## Origen

`brand.css` y `theme.json` vienen del proyecto de Claude Design **"Organic"**
(`projectId f2c3c130-0305-4977-a4a1-c3e43495af02`). Ese proyecto además tiene páginas de
referencia que **no se importaron** porque son documentación, no código de producto:
`foundations/` (type, color, layout, icons, image), `components/` (buttons, cards, dialog,
forms, navigation, table) y `templates/landing/`. Si hace falta ver el markup de un
componente, se mira ahí.

Si se retoca el tema en Claude Design, hay que volver a bajar `brand.css` y `theme.json`
a mano — la sincronización no es automática.

### Direccion visual de la marca (resumen de "Organic")

Layouts asimétricos alineados a la izquierda. Formas sobre-redondeadas: `--radius-lg` en
contenedores, `border-radius: 999px` en botones e inputs. Caprasimo para títulos sobre
Figtree para texto. Fotografía siempre envuelta en `.washed` (desaturada, bajada de
contraste) para que se hunda en el fondo cálido en vez de flotar encima. La salvia
(`--color-accent-2`) es una segunda voz real, no un highlight. Íconos Lucide a stroke-width
2.75.

Cuidado con el contraste: el par acento/fondo está afinado a 3:1 — alcanza para íconos,
texto grande y chrome, **no** para texto de párrafo. Para texto chico en acento usar
`--color-accent-700`.
