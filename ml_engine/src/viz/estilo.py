"""
Estilo único de las figuras de la tesis.

POR QUÉ EXISTE
Las figuras de la tesis tienen que leerse como un sistema: misma paleta, mismos ejes,
misma tipografía. Hasta ahora la paleta estaba **copiada dentro de**
`scripts/figura_etiqueta.py`, que es exactamente la divergencia que la regla de
`ml_engine/src/` quiere evitar: dos figuras de la misma tesis con dos terracotas
distintos no se ven como un error, se ven como descuido.

Acá vive la fuente única. Los notebooks la importan; `scripts/` todavía no (ver el
pendiente al final).

LA PALETA NO SE ELIGE POR GUSTO
Está heredada de la marca y ya tiene dos restricciones **medidas**, no opinadas:

1. **`TERRACOTA` + `OLIVA` no sirve como par de dos series.** Falla el control de
   daltonismo: ΔE 4.8 en protanopia y 12.8 en visión normal, por debajo del piso de 15.
   El oliva sirve como marca de referencia (una línea de corte, un umbral), no como una
   segunda serie de datos. Documentado en `scripts/README.md`.

2. **Los cuatro colores de riesgo del sistema clínico NO sirven como colores de serie.**
   Medido con el validador de la skill `dataviz` sobre `--c-risk-*` de
   `design_system/clinical.css`:

       CVD separation      #a4480a (Medio) ↔ #8a6d00 (Medio Bajo)  ΔE 3.0 en deuteranopia
       Normal-vision floor #a71322 (Alto)  ↔ #a4480a (Medio)       ΔE 8.8, piso 15

   En la **interfaz** son legales porque nunca van solos: llevan texto y forma, que es
   justo lo que arregló la auditoría de accesibilidad de `SCRUM-45`. En un **gráfico**,
   donde el color suele ser lo único que distingue una barra de otra, no alcanzan.
   Además el nivel de riesgo es una variable **ordinal**, y a una ordinal le corresponde
   una rampa secuencial de un solo tono, no cuatro tonos distintos. Para eso está
   `rampa(n)`.

REGLA QUE NO SE NEGOCIA EN ESTE PROYECTO
Nunca codificar sólo con color. Toda figura lleva además etiqueta directa, forma o
texto. Es la misma regla de accesibilidad que rige la interfaz clínica, y vale igual
para una figura impresa en blanco y negro en un tribunal.
"""

from __future__ import annotations

import colorsys
import logging
import warnings

import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt

# --- Los colores de la marca -------------------------------------------------
TERRACOTA = "#c67139"  # el color de los datos; una sola serie va siempre en este
TINTA = "#201e1d"      # texto principal
GRIS = "#8c8681"       # ejes, texto secundario, líneas de referencia
GRIS_TENUE = "#d8d3cc" # grilla, zonas sombreadas
OLIVA = "#7a8a5e"      # SÓLO marcas de referencia (umbrales, cortes). Nunca 2ª serie.
SUPERFICIE = "#fcfcfb" # fondo de la figura

# El paso más claro de `rampa()` queda en 1.34:1 contra la superficie: es suficiente
# para un área grande pero NO se distingue del fondo por sí solo. Por eso toda barra o
# área rellena con la rampa lleva borde. No es decorativo.
BORDE_OBLIGATORIO = dict(edgecolor=SUPERFICIE, linewidth=1.2)


def rampa(n: int) -> list[str]:
    """
    `n` pasos del tono terracota, de claro a oscuro, para una variable ORDINAL.

    Es una rampa secuencial: un solo tono, luminancia monótona. Verificada monótona en
    luminancia relativa WCAG para n <= 6. Se usa para el nivel de riesgo NEWS2, que
    tiene orden (Bajo < Medio Bajo < Medio < Alto) y por lo tanto NO es categórica.
    """
    if not 1 <= n <= 6:
        raise ValueError(f"La rampa está verificada para 1..6 pasos, se pidieron {n}")

    tono, _, saturacion = colorsys.rgb_to_hls(*mcolors.to_rgb(TERRACOTA))
    if n == 1:
        luminancias = [0.54]
    else:
        luminancias = [0.86 - i * (0.48 / (n - 1)) for i in range(n)]

    return [
        mcolors.to_hex(colorsys.hls_to_rgb(tono, L, saturacion)) for L in luminancias
    ]


def aplicar() -> None:
    """
    Fija el estilo global de matplotlib. Se llama una vez por notebook.

    Los ejes son recesivos a propósito: la grilla y los marcos compiten con los datos, y
    en una figura impresa el gris claro desaparece mientras que los datos quedan.

    `Figtree` es la tipografía de la marca y **no está instalada en el equipo local**:
    matplotlib cae a `Segoe UI` sin avisar en la figura, pero emite un warning por cada
    texto que dibuja — más de novecientos en un notebook con seis figuras, que tapan por
    completo la salida real de las celdas. Se silencia sólo ese warning: la figura sale
    bien, y perder el resto de las advertencias de matplotlib sería peor.
    """
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message="findfont", module="matplotlib")

    plt.rcParams.update(
        {
            "font.family": ["Figtree", "Segoe UI", "DejaVu Sans"],
            "figure.dpi": 200,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "figure.facecolor": SUPERFICIE,
            "axes.facecolor": SUPERFICIE,
            "savefig.facecolor": SUPERFICIE,
            "text.color": TINTA,
            "axes.labelcolor": TINTA,
            "axes.edgecolor": GRIS_TENUE,
            "axes.linewidth": 1.0,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRIS_TENUE,
            "grid.linewidth": 0.8,
            "xtick.color": GRIS,
            "ytick.color": GRIS,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "legend.fontsize": 9,
        }
    )
    # Una sola serie no necesita ciclo de colores, y dejar el ciclo por defecto de
    # matplotlib invita a que una segunda serie aparezca en un azul que no es de nadie.
    mpl.rcParams["axes.prop_cycle"] = mpl.cycler(color=[TERRACOTA])


def etiquetar_barras(ax, barras, formato="{:.0f}", color=TINTA) -> None:
    """
    Escribe el valor sobre cada barra.

    No es adorno: es la codificación redundante que exige el proyecto. Si la figura se
    imprime en blanco y negro o la lee alguien con daltonismo, el número sigue ahí. El
    texto va en tinta y NO en el color de la serie — el color identifica la marca, el
    texto se lee.
    """
    for barra in barras:
        altura = barra.get_height()
        ax.annotate(
            formato.format(altura),
            xy=(barra.get_x() + barra.get_width() / 2, altura),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color=color,
        )


# PENDIENTE: `scripts/burndown.py` y `scripts/figura_etiqueta.py` todavía tienen la
# paleta copiada. Migrarlos a importar de acá exige correrlos de nuevo, y eso pisa las
# figuras ya entregadas en Drive, así que se hace aparte y verificando el resultado.
