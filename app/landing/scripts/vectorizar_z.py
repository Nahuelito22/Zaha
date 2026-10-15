"""Saca de la Z del logo los moldes vectoriales de sus cinco símbolos.

La Z que se VE en la landing es el PNG, con su textura de piedra. Estos
trazados no se dibujan: son moldes para recortar ese mismo PNG y encender
cada símbolo por separado en la intro.

Los símbolos sueltos (sol, barras, puntos) salen solos como componentes
conexos del canal alfa. El corazón y las dos espirales están pegados al
cuerpo de la Z, así que se recortan con una región a mano.

Uso:
    python app/landing/scripts/vectorizar_z.py <Zaha_Solo_Z_Sin_Fondo.png> [vista.png]

Escribe app/landing/src/marca/z-simbolos.ts. Con un segundo argumento
también guarda una vista previa con cada grupo pintado de un color.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SALIDA = Path(__file__).resolve().parent.parent / "src" / "marca" / "z-simbolos.ts"

# Regiones a mano, en píxeles del PNG original (467×500). Se intersecan con
# el cuerpo de la Z (el componente más grande).
# Las de las espirales son holgadas a propósito: la barra de la Z sigue de
# largo y un corte recto se notaría. El borde real lo hace un degradé radial
# en la máscara de la landing (ver CENTROS_ESPIRALES más abajo).
ESPIRAL_ARRIBA = [(40, 50), (225, 50), (225, 195), (40, 195)]
ESPIRAL_ABAJO = [(275, 345), (425, 345), (425, 470), (275, 470)]
CENTROS_ESPIRALES = [(117, 120), (352, 408)]
CORAZON = [(150, 262), (162, 238), (198, 232), (220, 247), (240, 235),
           (266, 241), (270, 249), (236, 299), (205, 350), (150, 292)]


def poligono(forma, puntos):
    m = np.zeros(forma, np.uint8)
    cv2.fillPoly(m, [np.array(puntos, np.int32)], 1)
    return m


def trazado(mascara):
    """Contornos de la máscara como un `d` de SVG. Los agujeros (el centro
    del sol, la espiral del corazón) salen como subtrazados y se respetan con
    fill-rule evenodd."""
    contornos, _ = cv2.findContours(mascara, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    partes = []
    for c in contornos:
        c = cv2.approxPolyDP(c, 0.6, True)
        if len(c) < 3:
            continue
        pts = c.reshape(-1, 2)
        partes.append("M" + "L".join(f"{x} {y}" for x, y in pts) + "Z")
    return "".join(partes)


def main():
    rgba = np.array(Image.open(sys.argv[1]).convert("RGBA"))
    opaco = (rgba[:, :, 3] > 128).astype(np.uint8)
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(opaco, 8)

    cuerpo_id = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    cuerpo = (etiquetas == cuerpo_id).astype(np.uint8)

    sol = np.zeros_like(opaco)
    barras = np.zeros_like(opaco)
    puntos = np.zeros_like(opaco)
    for i in range(1, n):
        if i == cuerpo_id or stats[i, cv2.CC_STAT_AREA] < 15:
            continue
        x, y, w, h = stats[i, :4]
        cx, cy = x + w / 2, y + h / 2
        # El sol (anillo + 8 rayos) queda arriba a la derecha; la barra
        # derecha del corazón cae casi en la misma x, por eso también se
        # mira la altura.
        destino = puntos if cy > 300 else sol if (cx > 243 and cy < 200) else barras
        destino[etiquetas == i] = 1

    forma = opaco.shape
    grupos = {
        # El orden es el del encendido: Caminos → Corazón → Conexión → Tierra → Equilibrio.
        "caminos": cuerpo & (poligono(forma, ESPIRAL_ARRIBA) | poligono(forma, ESPIRAL_ABAJO)),
        "corazon": (cuerpo & poligono(forma, CORAZON)) | barras,
        "conexion": sol,
        # Tierra · Origen es la piedra misma: se enciende la Z entera.
        "tierra": opaco,
        "equilibrio": puntos,
    }

    datos = {k: trazado(v) for k, v in grupos.items()}
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        "// Generado por app/landing/scripts/vectorizar_z.py. No editar a mano.\n"
        "// Moldes de los cinco símbolos de la Z, en el sistema de coordenadas\n"
        "// del PNG (467×500). No se dibujan: recortan el PNG.\n"
        f"export const ANCHO = {forma[1]}\nexport const ALTO = {forma[0]}\n"
        f"export const SIMBOLOS = {json.dumps(datos, indent=2)} as const\n"
        f"export const CENTROS_ESPIRALES = {json.dumps(CENTROS_ESPIRALES)} as const\n",
        encoding="utf-8",
    )
    print("escrito", SALIDA, {k: len(v) for k, v in datos.items()})

    if len(sys.argv) > 2:
        vista = np.full((*forma, 3), 245, np.uint8)
        vista[opaco == 1] = (200, 190, 180)
        colores = {"caminos": (40, 90, 200), "corazon": (200, 40, 60),
                   "conexion": (230, 160, 0), "equilibrio": (30, 150, 70)}
        for k, c in colores.items():
            vista[grupos[k] == 1] = c
        Image.fromarray(vista).resize((forma[1] * 2, forma[0] * 2), Image.NEAREST).save(sys.argv[2])


if __name__ == "__main__":
    main()
