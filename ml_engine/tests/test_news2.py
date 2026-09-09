"""
Los MISMOS 21 casos clínicos que `supabase/tests/news2_cases.sql`.

Si este archivo y aquel dejan de coincidir, los dos motores de NEWS2 —el de Python
para la tubería de datos y el de PostgreSQL para producción— divergieron, y un
paciente podría recibir un score distinto según por dónde pasó el dato. Es el riesgo
principal de tener dos implementaciones, y esta es la red que lo atrapa.

    cd ml_engine && python -m pytest tests/test_news2.py -q

Corre TAMBIÉN sin pytest, que hoy no está instalado en el entorno del equipo:

    cd ml_engine && python tests/test_news2.py

Se banca las dos formas a propósito: un test de seguridad clínica que solo corre si
antes instalaste el entorno de desarrollo completo es un test que no se corre.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import news2  # noqa: E402

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - camino sin pytest
    pytest = None


def _parametrize(argnames, argvalues, ids=None):
    """`pytest.mark.parametrize` cuando hay pytest; un no-op cuando no lo hay."""
    if pytest is not None:
        return pytest.mark.parametrize(argnames, argvalues, ids=ids)
    return lambda fn: fn

# nombre, rr, spo2, escala, o2, temp, tas, fc, acvpu, score esperado, riesgo esperado
CASOS = [
    # --- Línea de base ---
    ("Adulto sano, todo en rango", 16, 98, 1, False, 36.5, 120, 72, "A", 0, "Bajo"),

    # --- Regresión: score bajo con un parámetro en rojo ---
    ("Score 4 con rojo aislado -> Medio Bajo, no Alto", 8, 94, 1, False, 36.5, 120, 72, "A", 4, "Medio Bajo"),
    ("Score 3 con rojo aislado -> Medio Bajo", 8, 98, 1, False, 36.5, 120, 72, "A", 3, "Medio Bajo"),
    ("Score 4 sin ningún rojo -> Bajo", 10, 94, 1, False, 35.8, 105, 72, "A", 4, "Bajo"),

    # --- Regresión: la escala de SpO2 es una prescripción, no se infiere del O2 ---
    ("EPOC (escala 2) respirando aire, SpO2 90 -> en objetivo, 0 puntos", 16, 90, 2, False, 36.5, 120, 72, "A", 0, "Bajo"),
    ("Escala 1 con oxígeno, SpO2 90 -> hipoxemia real, 3 + 2 puntos", 16, 90, 1, True, 36.5, 120, 72, "A", 5, "Medio"),
    ("EPOC (escala 2) con oxígeno, SpO2 98 -> hiperoxia, 3 + 2 puntos", 16, 98, 2, True, 36.5, 120, 72, "A", 5, "Medio"),
    ("EPOC (escala 2) con oxígeno, SpO2 90 -> en objetivo, solo suma el O2", 16, 90, 2, True, 36.5, 120, 72, "A", 2, "Bajo"),

    # --- Regresión: la C de ACVPU (confusión nueva) puntúa 3 ---
    ("Confusión nueva (C) -> 3 puntos, rojo aislado", 16, 98, 1, False, 36.5, 120, 72, "C", 3, "Medio Bajo"),
    ("Responde a la voz (V) -> 3 puntos", 16, 98, 1, False, 36.5, 120, 72, "V", 3, "Medio Bajo"),

    # --- Bordes de cada parámetro ---
    ("FR 20 y 21: borde entre 0 y 2", 21, 98, 1, False, 36.5, 120, 72, "A", 2, "Bajo"),
    ("Temperatura 39.1 -> 2 puntos (nunca 3)", 16, 98, 1, False, 39.1, 120, 72, "A", 2, "Bajo"),
    ("Temperatura 35.0 -> 3 puntos", 16, 98, 1, False, 35.0, 120, 72, "A", 3, "Medio Bajo"),
    ("Hipertensión 220 -> 3 puntos, no 0", 16, 98, 1, False, 36.5, 220, 72, "A", 3, "Medio Bajo"),
    ("TAS 111 y 219 son ambos 0", 16, 98, 1, False, 36.5, 219, 72, "A", 0, "Bajo"),
    ("Bradicardia 40 -> 3 puntos", 16, 98, 1, False, 36.5, 120, 40, "A", 3, "Medio Bajo"),
    ("Taquicardia 131 -> 3 puntos", 16, 98, 1, False, 36.5, 120, 131, "A", 3, "Medio Bajo"),

    # --- Umbrales de clasificación ---
    ("Score 5 -> Medio", 21, 94, 1, False, 35.8, 105, 72, "A", 5, "Medio"),
    ("Score 6 -> Medio", 22, 94, 1, False, 35.5, 105, 95, "A", 6, "Medio"),

    # --- Deterioro compuesto ---
    ("Sepsis probable: deterioro en todos los ejes -> Alto", 26, 90, 1, True, 38.4, 98, 122, "V", 16, "Alto"),
    ("Score máximo teórico", 30, 80, 1, True, 34.0, 85, 140, "U", 20, "Alto"),
]


@_parametrize(
    "nombre,rr,spo2,escala,o2,temp,tas,fc,acvpu,score_esperado,riesgo_esperado",
    CASOS,
    ids=[c[0] for c in CASOS],
)
def test_caso_clinico(nombre, rr, spo2, escala, o2, temp, tas, fc, acvpu, score_esperado, riesgo_esperado):
    r = news2.calcular(
        frecuencia_respiratoria=rr,
        spo2=spo2,
        escala_spo2=escala,
        oxigeno_suplementario=o2,
        temperatura=temp,
        presion_sistolica=tas,
        frecuencia_cardiaca=fc,
        consciencia=acvpu,
    )
    assert r.score == score_esperado, f"{nombre}: score {r.score} != {score_esperado}"
    assert r.riesgo == riesgo_esperado, f"{nombre}: riesgo {r.riesgo} != {riesgo_esperado}"
    assert not r.imputado, "Los casos clínicos traen los 7 parámetros: no debe imputar nada"


def test_son_21_casos():
    """Si alguien agrega un caso al SQL y no acá, esto lo delata."""
    assert len(CASOS) == 21


# -----------------------------------------------------------------------------
# Imputación de ACVPU y oxígeno suplementario (ADR-007)
# -----------------------------------------------------------------------------

def test_imputacion_marca_la_fila_y_cuenta_los_puntos():
    r = news2.calcular(
        frecuencia_respiratoria=16, spo2=98, temperatura=36.5,
        presion_sistolica=120, frecuencia_cardiaca=72,
    )
    assert r.imputado
    assert r.puntos_imputados == 5  # 3 de consciencia + 2 de oxígeno
    assert r.score == 0


def test_el_sesgo_de_la_imputacion_va_siempre_hacia_abajo():
    """
    La propiedad que vuelve defendible al ADR-007: sea cual sea el valor real de los
    dos parámetros ausentes, el score imputado nunca puede quedar por ENCIMA del real.
    """
    base = dict(
        frecuencia_respiratoria=22, spo2=93, temperatura=38.5,
        presion_sistolica=105, frecuencia_cardiaca=115,
    )
    imputado = news2.calcular(**base)

    for acvpu in ("A", "C", "V", "P", "U"):
        for con_o2 in (False, True):
            real = news2.calcular(**base, consciencia=acvpu, oxigeno_suplementario=con_o2)
            assert imputado.score <= real.score, (
                f"El score imputado ({imputado.score}) superó al real "
                f"({real.score}) con ACVPU={acvpu}, O2={con_o2}"
            )


# -----------------------------------------------------------------------------
# Corredor propio, para cuando no hay pytest en el entorno.
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    fallos = []
    for caso in CASOS:
        try:
            test_caso_clinico(*caso)
        except AssertionError as e:
            fallos.append(str(e))

    for prueba in (
        test_son_21_casos,
        test_imputacion_marca_la_fila_y_cuenta_los_puntos,
        test_el_sesgo_de_la_imputacion_va_siempre_hacia_abajo,
    ):
        try:
            prueba()
        except AssertionError as e:
            fallos.append(f"{prueba.__name__}: {e}")

    total = len(CASOS) + 3
    if fallos:
        print(f"FALLARON {len(fallos)} de {total}:")
        for f in fallos:
            print("  -", f)
        raise SystemExit(1)
    print(f"OK: {total} pruebas ({len(CASOS)} casos clinicos + 3 de imputacion)")
