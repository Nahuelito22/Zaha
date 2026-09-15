"""Genera los burndown charts de los sprints de Zaha para la documentacion academica.

La curva real se ancla al historial de git y al estado registrado en Jira.
El eje X son dias habiles del sprint (Jira no cuenta fines de semana).
"""
import sys
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

# --- paleta de marca -------------------------------------------------------
TERRACOTA = "#c67139"
TINTA = "#201e1d"
GRIS = "#8c8681"
GRIS_TENUE = "#d8d3cc"

plt.rcParams.update({
    "font.family": ["Figtree", "Segoe UI", "DejaVu Sans"],
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "axes.edgecolor": GRIS_TENUE,
    "text.color": TINTA,
})


SOLO = set(sys.argv[1:])  # p.ej. `python burndown.py burndown_sprint3.png`


def dibujar(nombre, archivo, dias, real, total, subtitulo, en_curso=False, nota=None):
    if SOLO and archivo not in SOLO:
        return
    """dias: lista de date (habiles). real: puntos restantes, puede ser mas corta que dias."""
    n = len(dias)
    x = list(range(n))
    ideal = [total * (1 - i / (n - 1)) for i in range(n)]

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.plot(x, ideal, linestyle=(0, (5, 4)), linewidth=2, color=GRIS,
            label="Avance ideal", zorder=2)
    ax.plot(x[:len(real)], real, linewidth=2.4, color=TERRACOTA, marker="o",
            markersize=5.5, markerfacecolor="white", markeredgewidth=2,
            markeredgecolor=TERRACOTA, label="Trabajo restante", zorder=3)

    if en_curso:
        ax.axvline(len(real) - 1, color=GRIS_TENUE, linewidth=1.5, zorder=1)
        ax.annotate("hoy", xy=(len(real) - 1, total * 0.96), color=GRIS,
                    fontsize=9, ha="center",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white",
                              ec=GRIS_TENUE, lw=1))

    # etiqueta directa del ultimo valor real, hacia adentro si toca el borde
    # Si la curva termina en el ultimo dia, la etiqueta va ARRIBA del punto: a la
    # izquierda pisaria el marcador anterior, y a la derecha se sale del eje.
    ultimo = len(real) - 1
    if ultimo < n - 1:
        dx, dy, ha = 8, 10, "left"
    else:
        dx, dy, ha = 0, 13, "center"
    ax.annotate(f"{real[-1]} pts", xy=(ultimo, real[-1]),
                xytext=(dx, dy), textcoords="offset points", ha=ha,
                color=TERRACOTA, fontsize=10, fontweight="bold")

    ax.set_ylim(0, total * 1.08)
    ax.set_xlim(-0.4, n - 0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([d.strftime("%d/%m") for d in dias], fontsize=9, color=GRIS)
    ax.yaxis.set_major_locator(MultipleLocator(max(5, round(total / 8 / 5) * 5)))
    ax.tick_params(axis="y", labelsize=9, colors=GRIS, length=0)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRIS_TENUE, linewidth=0.8, alpha=0.7, zorder=0)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRIS_TENUE)

    ax.set_ylabel("Puntos de historia restantes", fontsize=10, color=GRIS, labelpad=10)
    ax.set_title(nombre, fontsize=14, fontweight="bold", loc="left", pad=34)
    ax.text(0, 1.025, subtitulo, transform=ax.transAxes, fontsize=10, color=GRIS)

    ax.legend(frameon=False, fontsize=10, loc="upper right",
              labelcolor=TINTA, handlelength=2.4)

    if nota:
        ax.text(0, -0.19, nota, transform=ax.transAxes, fontsize=9,
                color=GRIS, va="top")

    fig.tight_layout()
    fig.savefig(archivo, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"OK  {archivo}")


# --- Sprint 1: cerrado, 17/08 - 07/09, 67 pts en 20 items ------------------
d1 = [date(2026, 8, d) for d in (17, 18, 19, 20, 21, 24, 25, 26, 27, 28, 31)] + \
     [date(2026, 9, d) for d in (1, 2, 3, 4, 7)]
r1 = [67, 67, 64, 62, 59, 54, 54, 48, 37, 33, 28, 24, 24, 17, 9, 0]
dibujar("Sprint 1 — Base y NEWS2", "burndown_sprint1.png", d1, r1, 67,
        "17/08 – 07/09/2026 · 20 items · 67 puntos · cerrado")

# --- Sprint 2: en curso, 31/08 - 21/09, 34 pts en 9 items ------------------
# La meseta inicial es real: hasta el 07/09 el equipo estaba cerrando el
# Sprint 1, que se solapa con este. El desplome del 10/09 son los cuatro PR
# de ese dia (SCRUM-45, 72 y 35).
d2 = [date(2026, 8, 31)] + [date(2026, 9, d) for d in
      (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21)]
r2 = [34, 34, 32, 32, 30, 30, 29, 29, 18, 15, 12, 10]   # hasta hoy 15/09
dibujar("Sprint 2 — PWA y carga", "burndown_sprint2.png", d2, r2, 34,
        "31/08 – 21/09/2026 · 9 items · 34 puntos · en curso", en_curso=True)

# --- Sprint 3: 22/09 - 05/10, 72 pts en 13 items ---------------------------
# El sprint se reencuadro el 15/09: salieron SCRUM-49 y SCRUM-51 (bloqueadas por
# PhysioNet, dependencia externa) y las dos historias paraguas SCRUM-47 y SCRUM-70,
# cuyo trabajo real pertenece al Sprint 4. El total bajo de 89 a 72 pts y el sprint
# cierra completo.
d3 = [date(2026, 9, d) for d in (22, 23, 24, 25, 28, 29, 30)] +      [date(2026, 10, d) for d in (1, 2, 5)]
r3 = [72, 64, 56, 43, 38, 33, 20, 15, 5, 0]
dibujar("Sprint 3 — Tablero y datos", "burndown_sprint3.png", d3, r3, 72,
        "22/09 – 05/10/2026 · 13 items · 72 puntos",
        nota="Se reasignaron al Sprint 4 las tareas bloqueadas por la credencial de "
             "PhysioNet (SCRUM-49 y 51) y dos historias cuyo trabajo corresponde a "
             "ese sprint (SCRUM-47 y 70): el alcance paso de 89 a 72 puntos.")
