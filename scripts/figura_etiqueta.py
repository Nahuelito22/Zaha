"""
Figura de la etiqueta v2 (SCRUM-53) para la documentacion del Sprint 3.

Muestra, sobre el demo de MIMIC-IV-ED, como se reparten las tomas respecto del
desenlace adverso, y por que el horizonte de 24 h casi no discrimina en este dataset.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TERRACOTA = "#c67139"
TINTA = "#201e1d"
GRIS = "#8c8681"
GRIS_TENUE = "#d8d3cc"
OLIVA = "#7a8a5e"

plt.rcParams.update({
    "font.family": ["Figtree", "Segoe UI", "DejaVu Sans"],
    "figure.dpi": 200, "savefig.dpi": 200, "text.color": TINTA,
})

RAIZ = Path(__file__).resolve().parents[1] / "ml_engine"
df = pd.read_parquet(
    RAIZ / "data/processed/mimic-iv-ed-demo-2.2/observaciones_etiquetadas.parquet"
)
horas = df["horas_al_evento"].dropna()

fig, ax = plt.subplots(figsize=(9.5, 4.8))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

bins = [i for i in range(-8, 31)]
ax.hist(horas.clip(-8, 30), bins=bins, color=TERRACOTA, edgecolor="white", linewidth=0.6)

# Zona descartada: dato posterior al egreso (horas < 0) y ventana ciega (0 a 1 h)
ax.axvspan(-8, 0, color=GRIS_TENUE, alpha=0.55, zorder=0)
ax.axvspan(0, 1, color=GRIS, alpha=0.35, zorder=0)
ax.axvline(1, color=GRIS, linewidth=1.5, linestyle=(0, (4, 3)))
ax.axvline(24, color=OLIVA, linewidth=2)

tope = ax.get_ylim()[1]
ax.text(-4, tope * 0.93, "dato posterior\nal egreso\n(65 tomas)",
        ha="center", va="top", fontsize=8.5, color=GRIS, linespacing=1.5)
# La banda de la ventana ciega es demasiado angosta para escribir adentro: la
# etiqueta va afuera, con una guia que la senala.
ax.annotate("ventana ciega\n1 h · 97 tomas", xy=(1, tope * 0.38),
            xytext=(8.5, tope * 0.60), fontsize=8.5, color=GRIS,
            ha="center", linespacing=1.5,
            arrowprops=dict(arrowstyle="-", color=GRIS, linewidth=1,
                            connectionstyle="arc3,rad=-0.25"))
ax.text(12, tope * 0.93, "y = 1   ·   585 tomas", ha="center", va="top",
        fontsize=10, color=TERRACOTA, fontweight="bold")
ax.annotate("horizonte\n24 h", xy=(24, tope * 0.55), xytext=(27, tope * 0.75),
            fontsize=9, color=OLIVA, ha="center", linespacing=1.5)

ax.set_xlim(-8, 30)
ax.set_xlabel("Horas entre la toma y el desenlace adverso", fontsize=10,
              color=GRIS, labelpad=8)
ax.set_ylabel("Tomas", fontsize=10, color=GRIS, labelpad=10)
ax.tick_params(labelsize=9, colors=GRIS, length=0)
ax.grid(axis="y", color=GRIS_TENUE, linewidth=0.8, alpha=0.7)
ax.set_axisbelow(True)
for lado in ("top", "right", "left"):
    ax.spines[lado].set_visible(False)
ax.spines["bottom"].set_color(GRIS_TENUE)

ax.set_title("Distribución de las tomas respecto del desenlace adverso",
             fontsize=14, fontweight="bold", loc="left", pad=34)
ax.text(0, 1.025, "Demo de MIMIC-IV-ED · 222 episodios · etiqueta v2 (SCRUM-53)",
        transform=ax.transAxes, fontsize=10, color=GRIS)
ax.text(0, -0.22,
        "Solo 2 de 749 tomas caen más allá del horizonte de 24 h: con estadías de "
        "mediana 5,8 h el horizonte no separa,\ny la etiqueta colapsa a «el episodio "
        "terminó en internación». La definición es correcta; el demo no alcanza para "
        "medir con ella.",
        transform=ax.transAxes, fontsize=9, color=GRIS, va="top", linespacing=1.6)

fig.tight_layout()
salida = Path("C:/Users/matia/Desktop/Zaha_Graficos/figura_etiqueta_v2.png")
fig.savefig(salida, facecolor="white", bbox_inches="tight")
print("OK ", salida)
