"""
Compone las figuras de gestion del Sprint 4 a partir de los datos reales de Jira.

POR QUE COMPUESTA Y NO CAPTURA DE PANTALLA
La vista de busqueda de Jira no entra completa en una captura: el viewport del navegador
queda fijo en 633 px de alto, `resize_window` no lo cambia y la tabla tiene su propio
contenedor con scroll, asi que de 15 items solo entran 8 filas.

POR QUE MATPLOTLIB Y NO HTML + CHROME HEADLESS
El metodo de las figuras 16 y 17 del Sprint 3 era HTML renderizado con Chrome headless.
**Aca no funciona**: probado con --headless, --headless=old, --headless=new y con
--no-sandbox + --user-data-dir, Chrome devuelve codigo 0, no escribe nada en stderr y NO
genera el archivo. Es la misma falla silenciosa que ya estaba anotada para ese metodo.
Matplotlib ademas da consistencia visual con el burndown y con las curvas de resultados,
que son las otras figuras de esta misma entrega.

LOS DATOS SON REALES Y LA FIGURA LO DICE
Las 15 filas salen de `sprint = 6` en el proyecto SCRUM, leidas por la API el 01/10/2026.
El pie de cada figura declara el origen y la fecha: una tabla compuesta que se hiciera
pasar por una captura de pantalla seria peor que no tener figura.

Uso:  python scripts/figura_sprint4.py
Salida: 20_jira_sprint4.png y 21_jira_bloqueadas.png en el directorio actual.
"""
import matplotlib
matplotlib.use("Agg")

import logging
import os

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Figtree no esta instalada: matplotlib cae a Segoe UI sin afectar la figura, pero emite
# un warning por cada texto. Son cientos y tapan la salida util.
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

# --- paleta de marca, la misma de burndown.py y de src/viz/estilo.py -------
TERRACOTA = "#c67139"
TINTA = "#201e1d"
GRIS = "#8c8681"
GRIS_TENUE = "#d8d3cc"
SUPERFICIE = "#fcfcfb"
# Verde del sistema de diseno clinico (--c-risk-low). Va SIEMPRE acompanado del texto
# "Done": el proyecto no codifica nada solo con color.
VERDE = "#1f7a44"
VERDE_FONDO = "#e6f4ec"
GRIS_FONDO = "#ececea"

FECHA_LECTURA = "1 de octubre de 2026"

plt.rcParams.update({
    "font.family": ["Figtree", "Segoe UI", "DejaVu Sans"],
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "text.color": TINTA,
})

# Leido de Jira el 01/10/2026 con `sprint = 6`. Orden: completados primero.
# (clave, titulo, tipo, responsable, prioridad, estado, puntos)
ITEMS = [
    ("SCRUM-54", "Split por paciente (nunca por fila) y control de fuga temporal",
     "Tarea", "matiasghilardisalinas", "High", "Done", 5),
    ("SCRUM-55", "Análisis exploratorio de datos (EDA) en notebooks",
     "Tarea", "matiasghilardisalinas", "Medium", "Done", 8),
    ("SCRUM-56", "Baseline XGBoost sobre el snapshot actual",
     "Tarea", "matiasghilardisalinas", "High", "Done", 8),
    ("SCRUM-58", "Comparativa de tasa de alertas a sensibilidad igualada",
     "Tarea", "matiasghilardisalinas", "Highest", "Done", 8),
    ("SCRUM-59", "Exportar el modelo elegido a ONNX",
     "Tarea", "matiasghilardisalinas", "Medium", "Done", 8),
    ("SCRUM-60", "Documentar el caveat de rendimiento de NEWS2 en urgencias",
     "Tarea", "Gustavo Garcia", "Medium", "Done", 3),
    ("SCRUM-76", "Redacción del marco teórico de la tesis",
     "Tarea", "Gustavo Garcia", "Medium", "Done", 5),
    ("SCRUM-80", "Reproducir NEWS2 sobre MIMIC-IV-ED y medir su tasa de alertas",
     "Tarea", "matiasghilardisalinas", "Highest", "Done", 5),
    ("SCRUM-82", "Adoptar la cohorte TRIAGE como segunda fuente (ADR-009)",
     "Tarea", "Gustavo Garcia", "Medium", "Done", 8),
    ("SCRUM-47", "HU-03 — Motor de Inteligencia Artificial y Alertas Predictivas",
     "Historia", "matiasghilardisalinas", "Medium", "To Do", 8),
    ("SCRUM-49", "Firmar el DUA específico de MIMIC-IV-ED",
     "Tarea", "matiasghilardisalinas", "High", "To Do", 1),
    ("SCRUM-51", "Descarga y limpieza de MIMIC-IV-ED",
     "Tarea", "matiasghilardisalinas", "High", "To Do", 5),
    ("SCRUM-57", "LSTM sobre series de 48 h — hipótesis bajo prueba",
     "Tarea", "matiasghilardisalinas", "Medium", "To Do", None),
    ("SCRUM-70", "HU-05 — Estructura de Datos FHIR y Trazabilidad Legal",
     "Historia", "matiasghilardisalinas", "High", "To Do", 3),
    ("SCRUM-71", "Mapear el esquema propio a recursos FHIR",
     "Tarea", "matiasghilardisalinas", "High", "To Do", None),
]

# Por que sigue abierto cada item. Un tablero que muestra trabajo abierto sin decir por
# que no sirve para la gestion.
MOTIVOS = {
    "SCRUM-49": ("Bloqueada", "acreditación de PhysioNet, en revisión externa"),
    "SCRUM-51": ("Bloqueada", "acreditación de PhysioNet, en revisión externa"),
    "SCRUM-57": ("Bloqueada", "requiere datos con serie temporal que esa acreditación habilita"),
    "SCRUM-47": ("Historia", "se cierra cuando terminan sus tareas hijas"),
    "SCRUM-70": ("Historia", "se cierra cuando terminan sus tareas hijas"),
    "SCRUM-71": ("Fuera de foco", "interoperabilidad; ajena al objetivo del sprint"),
}

# El layout es PROPORCIONAL, no de fracciones fijas. Con alturas de fila fijas en
# fracciones de figura, 15 filas sumaban mas de 1.0 y el pie terminaba dibujado encima
# de la tabla. Ahora se reparte el espacio disponible entre las filas que haya.
MARGEN_SUP = 0.14      # titulo, subtitulo y encabezados
MARGEN_INF = 0.085     # pie
PESO_GRUPO = 0.85      # un separador de grupo ocupa menos que una fila


def _badge(fig, x, y, texto, fondo, color, alto_fila):
    """Etiqueta de estado: rectangulo redondeado + texto. Nunca color solo."""
    h = min(alto_fila * 0.62, 0.030)
    fig.patches.append(FancyBboxPatch(
        (x, y - h / 2), 0.050, h,
        boxstyle="round,pad=0.002,rounding_size=0.004",
        transform=fig.transFigure, facecolor=fondo, edgecolor="none", zorder=2))
    fig.text(x + 0.025, y, texto, fontsize=9.5, color=color,
             ha="center", va="center", fontweight="bold", zorder=3)


def _tabla(archivo, titulo, subtitulo, columnas, filas, pie, ancho=15.6, alto_px_fila=0.46):
    """
    `columnas`: lista de (encabezado, x, alineacion).
    `filas`: lista de dicts {tipo: 'grupo'|'item'|'total', ...}.
    """
    peso = sum(PESO_GRUPO if f["tipo"] == "grupo" else 1.0 for f in filas)
    alto = 2.3 + peso * alto_px_fila

    fig = plt.figure(figsize=(ancho, alto))
    fig.patch.set_facecolor(SUPERFICIE)

    # Los margenes se calculan en PULGADAS y recien despues se pasan a fraccion: como
    # fraccion fija, en una figura baja el encabezado quedaba tan comprimido que el
    # subtitulo se superponia con los nombres de columna.
    m_sup = max(MARGEN_SUP, 1.55 / alto)
    m_inf = max(MARGEN_INF, 0.75 / alto)
    disponible = 1.0 - m_sup - m_inf
    h = disponible / peso                      # altura de una fila, en fraccion de figura

    fig.text(0.035, 0.975, titulo, fontsize=19, fontweight="bold", color=TINTA, va="top")
    fig.text(0.035, 0.975 - 0.42 / alto, subtitulo, fontsize=11.5, color=GRIS, va="top")

    y = 1.0 - m_sup + h * 0.45
    for enc, x, ha in columnas:
        fig.text(x, y, enc.upper(), fontsize=9, color=GRIS, ha=ha, va="center",
                 fontweight="bold")
    y -= h * 0.45
    fig.add_artist(plt.Line2D([0.035, 0.965], [y, y], color=GRIS_TENUE, lw=1.6,
                              transform=fig.transFigure))

    for f in filas:
        if f["tipo"] == "grupo":
            y -= h * PESO_GRUPO
            fig.text(0.035, y, f["texto"].upper(), fontsize=9.5, color=TERRACOTA,
                     fontweight="bold", va="center")
            continue
        if f["tipo"] == "total":
            # Separacion generosa: con 0.25h la linea del total quedaba pegada al
            # subtitulo de tipo de la ultima fila y parecia tacharlo.
            y -= h * 0.60
            fig.add_artist(plt.Line2D([0.035, 0.965], [y, y], color=GRIS_TENUE, lw=1.6,
                                      transform=fig.transFigure))
            y -= h * 0.80
            fig.text(0.035, y, f["texto"], fontsize=11.5, color=TINTA, fontweight="bold",
                     va="center")
            fig.text(0.965, y, f["valor"], fontsize=11.5, color=TINTA, fontweight="bold",
                     ha="right", va="center")
            continue

        y -= h
        for celda, (_, x, ha) in zip(f["celdas"], columnas):
            if isinstance(celda, tuple) and celda[0] == "badge":
                _badge(fig, x, y, celda[1], celda[2], celda[3], h)
            elif isinstance(celda, tuple) and celda[0] == "doble":
                fig.text(x, y + h * 0.17, celda[1], fontsize=10.5, color=TINTA,
                         ha=ha, va="center", fontweight="bold")
                fig.text(x, y - h * 0.21, celda[2], fontsize=8.5, color=GRIS,
                         ha=ha, va="center")
            else:
                gris = isinstance(celda, tuple) and celda[0] == "gris"
                txt = celda[1] if isinstance(celda, tuple) else celda
                fig.text(x, y, txt, fontsize=10.5,
                         color=GRIS if gris else TINTA, ha=ha, va="center")
        fig.add_artist(plt.Line2D([0.035, 0.965], [y - h / 2, y - h / 2],
                                  color=GRIS_TENUE, lw=0.7, transform=fig.transFigure))

    # El pie va DEBAJO de la ultima fila, no en una coordenada fija.
    fig.text(0.035, y - h * 1.15, pie, fontsize=8.5, color=GRIS, va="top",
             linespacing=1.7)

    fig.savefig(archivo, facecolor=SUPERFICIE, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    print(f"OK  {archivo}  ({os.path.getsize(archivo):,} bytes)")


def figura_sprint():
    hechos = [i for i in ITEMS if i[5] == "Done"]
    abiertos = [i for i in ITEMS if i[5] != "Done"]
    ph = sum(i[6] or 0 for i in hechos)
    pa = sum(i[6] or 0 for i in abiertos)

    columnas = [("Clave", 0.035, "left"), ("Trabajo", 0.145, "left"),
                ("Responsable", 0.655, "left"), ("Prioridad", 0.815, "left"),
                ("Estado", 0.888, "left"), ("Puntos", 0.965, "right")]

    def fila(it):
        clave, titulo, tipo, resp, prio, estado, pts = it
        fondo, color = (VERDE_FONDO, VERDE) if estado == "Done" else (GRIS_FONDO, "#5f5a56")
        return {"tipo": "item", "celdas": [
            ("doble", clave, tipo), titulo, resp, prio,
            ("badge", estado, fondo, color),
            str(pts) if pts is not None else ("gris", "—"),
        ]}

    filas = [{"tipo": "grupo", "texto": f"Completado — {len(hechos)} ítems, {ph} puntos"}]
    filas += [fila(i) for i in hechos]
    filas.append({"tipo": "grupo", "texto": f"Abierto — {len(abiertos)} ítems, {pa} puntos"})
    filas += [fila(i) for i in abiertos]
    filas.append({"tipo": "total", "texto": "Completado sobre comprometido",
                  "valor": f"{ph} / {ph + pa}"})

    _tabla("20_jira_sprint4.png", "Sprint 4 — Modelado",
           "6 al 19 de octubre de 2026 · 15 ítems de trabajo · 75 puntos de historia",
           columnas, filas,
           f"Datos del proyecto SCRUM en Jira, sprint «Sprint 4 — Modelado», leídos el "
           f"{FECHA_LECTURA}. Tabla compuesta a partir de esos datos para que los quince "
           f"ítems entren completos en una sola imagen. El guion en Puntos marca los dos "
           f"ítems sin estimar: su trabajo real pertenece a sprints posteriores.")


def figura_bloqueadas():
    abiertos = [i for i in ITEMS if i[5] != "Done"]
    pa = sum(i[6] or 0 for i in abiertos)

    columnas = [("Clave", 0.035, "left"), ("Trabajo", 0.145, "left"),
                ("Motivo por el que sigue abierto", 0.560, "left"),
                ("Puntos", 0.965, "right")]

    def fila(it):
        clave, titulo, tipo, _resp, _prio, _estado, pts = it
        etiqueta, detalle = MOTIVOS[clave]
        return {"tipo": "item", "celdas": [
            ("doble", clave, tipo), titulo,
            ("doble", etiqueta, detalle),
            str(pts) if pts is not None else ("gris", "—"),
        ]}

    filas = [fila(i) for i in abiertos]
    filas.append({"tipo": "total", "texto": "Puntos no completados", "valor": str(pa)})

    _tabla("21_jira_bloqueadas.png", "Sprint 4 — trabajo no completado y su motivo",
           f"6 ítems · {pa} puntos de historia · ninguno pendiente por falta de avance",
           columnas, filas,
           "Tres de los seis ítems dependen de una acreditación externa que lleva más de un "
           "mes en revisión; dos son historias de usuario que se cierran al terminar sus\n"
           "tareas hijas; uno corresponde a trabajo de interoperabilidad ajeno al objetivo "
           f"del sprint. Datos del proyecto SCRUM en Jira leídos el {FECHA_LECTURA}.",
           ancho=14.0)


if __name__ == "__main__":
    figura_sprint()
    figura_bloqueadas()
