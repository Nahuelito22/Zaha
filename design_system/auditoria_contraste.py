# Auditoria WCAG 2.1 de las DOS capas del sistema de diseno de Zaha.
# Capa clinica (SCRUM-45) y capa de marca (SCRUM-35). Correr: python design_system/auditoria_contraste.py
def lum(h):
    h = h.lstrip("#")
    c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

BG      = "#ffffff"
SURFACE = "#f6f7f9"
SURF_A  = "#eceef2"

# (etiqueta, color, fondo, umbral, tipo)
pruebas = [
    ("riesgo Bajo — texto s/ su fondo",      "#1f7a44", "#e6f4ec", 4.5, "texto"),
    ("riesgo Medio Bajo — texto s/ su fondo","#8a6d00", "#fdf5d9", 4.5, "texto"),
    ("riesgo Medio — texto s/ su fondo",     "#a4480a", "#fdeee0", 4.5, "texto"),
    ("riesgo Alto — texto s/ su fondo",      "#a71322", "#fdeaec", 4.5, "texto"),

    ("riesgo Bajo — texto s/ blanco",        "#1f7a44", BG, 4.5, "texto"),
    ("riesgo Medio Bajo — texto s/ blanco",  "#8a6d00", BG, 4.5, "texto"),
    ("riesgo Medio — texto s/ blanco",       "#a4480a", BG, 4.5, "texto"),
    ("riesgo Alto — texto s/ blanco",        "#a71322", BG, 4.5, "texto"),

    ("riesgo Bajo — texto s/ surface",       "#1f7a44", SURFACE, 4.5, "texto"),
    ("riesgo Medio Bajo — texto s/ surface", "#8a6d00", SURFACE, 4.5, "texto"),
    ("riesgo Medio — texto s/ surface",      "#a4480a", SURFACE, 4.5, "texto"),
    ("riesgo Alto — texto s/ surface",       "#a71322", SURFACE, 4.5, "texto"),

    ("borde Bajo s/ blanco",                 "#1f7a44", BG, 3.0, "no-texto"),
    ("borde Medio Bajo s/ blanco",           "#b08c00", BG, 3.0, "no-texto"),
    ("borde Medio s/ blanco",                "#d1600f", BG, 3.0, "no-texto"),
    ("borde Alto s/ blanco",                 "#c8182a", BG, 3.0, "no-texto"),

    ("texto principal s/ blanco",            "#14171c", BG, 4.5, "texto"),
    ("texto atenuado s/ blanco",             "#5a636f", BG, 4.5, "texto"),
    ("texto atenuado s/ surface",            "#5a636f", SURFACE, 4.5, "texto"),
    ("texto atenuado s/ surface-alt",        "#5a636f", SURF_A, 4.5, "texto"),
    ("texto tenue (faint) s/ blanco [solo placeholder]", "#8b95a1", BG, 3.0, "no-texto"),
    ("dato faltante s/ blanco [ahora muted]", "#5a636f", BG, 4.5, "texto"),

    ("accion azul s/ blanco",                "#1f5fb8", BG, 4.5, "texto"),
    ("accion azul s/ su tinte",              "#1f5fb8", "#e8f0fb", 4.5, "texto"),
    ("foco (outline) s/ blanco",             "#1f5fb8", BG, 3.0, "no-texto"),
    ("prediccion IA s/ su fondo",            "#5b3d9e", "#f0ebfa", 4.5, "texto"),
    # NO es falla: --c-border solo separa (borde de .panel, linea entre filas de
    # tabla). WCAG 1.4.11 exige 3:1 a lo que delimita un COMPONENTE, no a un
    # divisor decorativo. Se deja medido, con umbral 0, para que el numero este a
    # la vista y una falla de verdad no se pierda entre ruido. Ver SCRUM-45.
    ("borde neutro s/ blanco [divisor decorativo]", "#d6dae1", BG, 0.0, "decorativo"),
    ("borde neutro fuerte s/ blanco",        "#7b8798", BG, 3.0, "no-texto"),
]

# ── Capa de MARCA (brand.css) ────────────────────────────────────────────────
# Se suma en SCRUM-35. La landing y el login son territorio de marca, y la paleta
# tierra es clara: varios de sus colores NO sirven para texto aunque sí sirvan
# para bordes y rellenos. Esa distinción es la que se verifica acá.
B_BG, B_SURF = "#f5ead8", "#ebddc5"


def mezcla(fg, bg, pct):
    """Resuelve color-mix(in srgb, fg pct%, transparent) compuesto sobre bg.
    brand.css define sus grises atenuados así, y hay que evaluarlos ya
    compuestos: sin esto se mide el color opaco, que no es el que se ve."""
    f = [int(fg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    a = pct / 100
    return "#%02x%02x%02x" % tuple(round(f[i] * a + b[i] * (1 - a)) for i in range(3))


TEXTO_MARCA = "#201e1d"

pruebas_marca = [
    ("marca: texto s/ fondo",              TEXTO_MARCA, B_BG, 4.5, "texto"),
    ("marca: texto s/ superficie",         TEXTO_MARCA, B_SURF, 4.5, "texto"),
    (".text-muted (65%) s/ fondo",         mezcla(TEXTO_MARCA, B_BG, 65), B_BG, 4.5, "texto"),
    (".card-body (80%) s/ superficie",     mezcla(TEXTO_MARCA, B_SURF, 80), B_SURF, 4.5, "texto"),
    (".card-meta (65%) s/ superficie",     mezcla(TEXTO_MARCA, B_SURF, 65), B_SURF, 4.5, "texto"),
    (".tag-neutral: n-800 s/ n-100",       "#474238", "#f9f4ed", 4.5, "texto"),
    (".tag-outline: texto acento-700",     "#8c491a", B_BG, 4.5, "texto"),
    (".tag-outline: borde acento",         "#c67139", B_BG, 3.0, "no-texto"),
    ("outline de foco s/ fondo",           "#c67139", B_BG, 3.0, "no-texto"),
    # Los dos de abajo NO son fallas: se listan como recordatorio de que estos
    # colores son de relleno y borde, y que usarlos para texto rompe AA.
    ("acento terracota (solo relleno)",    "#c67139", B_BG, 3.0, "no-texto"),
    ("oliva (solo relleno)",               "#7a8a5e", B_BG, 3.0, "no-texto"),
]

pruebas = pruebas + pruebas_marca


def auditar(casos=pruebas):
    """Devuelve la lista de fallas. Se importa desde otros chequeos (la landing
    usa `ratio` para verificar la paleta de marca), así que la corrida va bajo
    __main__: importar el módulo no tiene que imprimir nada."""
    fallos = []
    print(f"{'':52} {'ratio':>7}  {'min':>4}  estado")
    print("-" * 78)
    for etq, fg, bg, minimo, tipo in casos:
        r = ratio(fg, bg)
        ok = r >= minimo
        if not ok:
            fallos.append((etq, fg, bg, r, minimo, tipo))
        print(f"{etq:52} {r:7.2f}  {minimo:4.1f}  {'OK' if ok else 'FALLA'}")
    print()
    if fallos:
        print(f"{len(fallos)} FALLA(S):")
        for etq, fg, bg, r, m, tipo in fallos:
            print(f"  - {etq}: {fg} sobre {bg} = {r:.2f}:1, necesita {m}:1 ({tipo})")
    else:
        print("Sin fallas.")
    return fallos


if __name__ == "__main__":
    auditar()
