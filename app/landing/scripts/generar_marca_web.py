"""Genera los íconos y la imagen de vista previa del sitio a partir del logo.

Reemplaza los favicons de fábrica (el cohete de Astro en la landing, el logo
de Vite en la app) y crea la imagen OpenGraph que aparece al compartir el link.

Uso:
    python app/landing/scripts/generar_marca_web.py <carpeta_de_fuentes>

La carpeta tiene que tener `figtree.ttf` (la variable, con eje de peso) y
`caprasimo.ttf`, las dos de github.com/google/fonts (licencia OFL). No se
versionan: el resultado sí.

Escribe:
    app/landing/public/favicon.ico        16, 32 y 48 px
    app/landing/public/apple-touch-icon.png
    app/landing/public/og.png             1200×630
    app/clinical/public/favicon.ico
"""
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[3]
LANDING = RAIZ / "app" / "landing" / "public"
CLINICA = RAIZ / "app" / "clinical" / "public"

# La Z sobre el beige de theme.json: es la versión que ya se lee bien a 192 px
# en el ícono de la PWA. La Z tallada con piedra se empasta a 16 px.
ICONO = CLINICA / "icons" / "pwa-512.png"
Z_PIEDRA = LANDING / "marca" / "zaha-z.png"

CREMA = "#f5ead8"
ACENTO_700 = "#8c491a"   # 5,72:1 sobre crema
NEUTRO_700 = "#645c50"   # 5,53:1 sobre crema
TEXTO = "#201e1d"


def figtree(carpeta, tam, peso):
    f = ImageFont.truetype(str(carpeta / "figtree.ttf"), tam)
    f.set_variation_by_axes([peso])
    return f


def texto_espaciado(dibujo, xy, texto, fuente, color, espacio):
    """Pillow no tiene letter-spacing: se dibuja letra por letra."""
    x, y = xy
    for letra in texto:
        dibujo.text((x, y), letra, font=fuente, fill=color)
        x += dibujo.textlength(letra, font=fuente) + espacio
    return x


def partir(dibujo, texto, fuente, ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if dibujo.textlength(prueba, font=fuente) <= ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    return lineas + [actual]


def imagen_og(carpeta):
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), CREMA)

    # Franja terracota abajo, como el bloque de la landing.
    ImageDraw.Draw(img).rectangle([0, H - 18, W, H], fill=ACENTO_700)

    z = Image.open(Z_PIEDRA).convert("RGBA")
    alto_z = 440
    z = z.resize((round(z.width * alto_z / z.height), alto_z), Image.LANCZOS)
    img.paste(z, (90, (H - 18 - alto_z) // 2), z)

    d = ImageDraw.Draw(img)
    x = 90 + z.width + 70
    ancho = W - x - 80

    texto_espaciado(d, (x, 120), "ZAHA", figtree(carpeta, 64, 600), ACENTO_700, 26)
    texto_espaciado(d, (x, 205), "SALUD ANCESTRAL · INTELIGENCIA QUE CUIDA",
                    figtree(carpeta, 17, 600), NEUTRO_700, 2.6)

    titular = ImageFont.truetype(str(carpeta / "caprasimo.ttf"), 46)
    y = 265
    for linea in partir(d, "El deterioro avisa antes de ser una urgencia.", titular, ancho):
        d.text((x, y), linea, font=titular, fill=TEXTO)
        y += 58

    d.text((x, y + 26), "zahasalud.com.ar", font=figtree(carpeta, 26, 600), fill=ACENTO_700)
    img.save(LANDING / "og.png", optimize=True)


def main():
    carpeta = Path(sys.argv[1])
    icono = Image.open(ICONO).convert("RGBA")
    for destino in (LANDING, CLINICA):
        icono.save(destino / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    shutil.copyfile(CLINICA / "icons" / "apple-touch-icon.png", LANDING / "apple-touch-icon.png")
    imagen_og(carpeta)
    print("listo:", *(p.relative_to(RAIZ) for p in (
        LANDING / "favicon.ico", LANDING / "apple-touch-icon.png",
        LANDING / "og.png", CLINICA / "favicon.ico")))


if __name__ == "__main__":
    main()
