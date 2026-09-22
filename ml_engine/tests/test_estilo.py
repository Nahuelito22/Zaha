"""
Pruebas del estilo único de figuras (SCRUM-55).

`estilo.py` afirma dos cosas que, si dejan de ser ciertas, no rompen nada: la figura
sigue saliendo, sólo que mal. Una rampa que deja de ser monótona en luminancia convierte
una escala ordinal en un adorno —el lector ya no puede leer el orden—, y en una impresión
en blanco y negro el error es total y silencioso. Por eso se prueban.

    cd ml_engine && python -m pytest tests/test_estilo.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && python tests/test_estilo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.colors as mcolors  # noqa: E402

from src.viz import estilo  # noqa: E402


def _luminancia(color: str) -> float:
    """Luminancia relativa WCAG."""
    def canal(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in mcolors.to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_la_rampa_es_monotona_en_luminancia():
    """La propiedad que define una rampa secuencial: claro a oscuro, sin excepción."""
    for n in range(2, 7):
        luces = [_luminancia(c) for c in estilo.rampa(n)]
        assert all(luces[i] > luces[i + 1] for i in range(len(luces) - 1)), (
            f"la rampa de {n} pasos no es monótona: {estilo.rampa(n)}"
        )


def test_la_rampa_devuelve_la_cantidad_pedida():
    for n in range(1, 7):
        assert len(estilo.rampa(n)) == n


def test_la_rampa_no_repite_colores():
    for n in range(2, 7):
        pasos = estilo.rampa(n)
        assert len(set(pasos)) == n, f"la rampa de {n} repite un paso: {pasos}"


def test_la_rampa_rechaza_tamanos_no_verificados():
    """Mejor un error que una rampa de 9 pasos que nadie comprobó."""
    for n in (0, 7, 12):
        try:
            estilo.rampa(n)
        except ValueError:
            continue
        raise AssertionError(f"aceptó una rampa de {n} pasos sin verificar")


def test_el_paso_mas_oscuro_contrasta_con_la_superficie():
    """El extremo de la rampa tiene que separarse del fondo al menos 3:1."""
    oscuro = _luminancia(estilo.rampa(4)[-1])
    superficie = _luminancia(estilo.SUPERFICIE)
    contraste = (superficie + 0.05) / (oscuro + 0.05)
    assert contraste >= 3.0, f"el paso más oscuro contrasta sólo {contraste:.2f}:1"


def test_el_paso_mas_claro_exige_borde():
    """
    El paso más claro NO se distingue del fondo por sí solo (queda por debajo de 3:1).
    Es un hecho conocido y por eso `BORDE_OBLIGATORIO` existe. Si algún día la rampa
    cambiara y el paso más claro pasara a contrastar solo, esta prueba avisa para que se
    revise si el borde sigue siendo necesario — no es un error, es una alerta de diseño.
    """
    claro = _luminancia(estilo.rampa(4)[0])
    superficie = _luminancia(estilo.SUPERFICIE)
    contraste = (superficie + 0.05) / (claro + 0.05)
    assert contraste < 3.0, (
        f"el paso más claro ahora contrasta {contraste:.2f}:1; revisar si BORDE_OBLIGATORIO sigue haciendo falta"
    )
    assert estilo.BORDE_OBLIGATORIO["linewidth"] > 0


def test_los_colores_de_marca_son_hex_validos():
    for nombre in ("TERRACOTA", "TINTA", "GRIS", "GRIS_TENUE", "OLIVA", "SUPERFICIE"):
        color = getattr(estilo, nombre)
        assert mcolors.is_color_like(color), f"{nombre} = {color!r} no es un color"


def test_aplicar_no_deja_un_ciclo_de_colores_ajeno():
    """
    Una segunda serie NO puede aparecer en el azul por defecto de matplotlib. El proyecto
    tiene un solo color de datos; si hacen falta dos, la decisión es explícita.
    """
    import matplotlib as mpl

    estilo.aplicar()
    ciclo = mpl.rcParams["axes.prop_cycle"].by_key()["color"]
    assert ciclo == [estilo.TERRACOTA], f"el ciclo de colores quedó en {ciclo}"


PRUEBAS = [
    test_la_rampa_es_monotona_en_luminancia,
    test_la_rampa_devuelve_la_cantidad_pedida,
    test_la_rampa_no_repite_colores,
    test_la_rampa_rechaza_tamanos_no_verificados,
    test_el_paso_mas_oscuro_contrasta_con_la_superficie,
    test_el_paso_mas_claro_exige_borde,
    test_los_colores_de_marca_son_hex_validos,
    test_aplicar_no_deja_un_ciclo_de_colores_ajeno,
]


if __name__ == "__main__":
    fallos = []
    for prueba in PRUEBAS:
        try:
            prueba()
        except AssertionError as e:
            fallos.append(f"{prueba.__name__}: {e}")

    if fallos:
        print(f"FALLARON {len(fallos)} de {len(PRUEBAS)}:")
        for f in fallos:
            print("  -", f)
        raise SystemExit(1)
    print(f"OK: {len(PRUEBAS)} pruebas del estilo de figuras")
