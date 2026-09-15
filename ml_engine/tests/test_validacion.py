"""
Pruebas de los esquemas de validación de la tubería (SCRUM-52).

Lo que se verifica acá no es que los datos buenos pasen —eso lo prueba la corrida real
de la tubería— sino que los datos MALOS sean rechazados. Un esquema que acepta todo es
indistinguible de no tener esquema, y la única forma de saber que la red atrapa algo es
tirarle algo.

    cd ml_engine && python -m pytest tests/test_validacion.py -q

Corre TAMBIÉN sin pytest, igual que `test_news2.py`, porque pytest no está instalado en
el entorno del equipo:

    cd ml_engine && python tests/test_validacion.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from src.data import news2  # noqa: E402
from src.validation import esquemas  # noqa: E402

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - camino sin pytest
    pytest = None


def _observaciones_validas() -> pd.DataFrame:
    """Dos tomas mínimas que sí cumplen el contrato: una puntuable y una que no."""
    return pd.DataFrame(
        {
            "episodio_id": [1, 1],
            "paciente_id": [10, 10],
            "medido_en": pd.to_datetime(["2026-09-01 08:00", "2026-09-01 12:00"]),
            "frecuencia_respiratoria": [16.0, 18.0],
            "spo2": [98.0, 97.0],
            "temperatura": [36.5, None],  # la segunda no es puntuable: falta temperatura
            "presion_sistolica": [120.0, 118.0],
            "frecuencia_cardiaca": [72.0, 80.0],
            "valores_descartados": [0, 0],
            "puntuable": [True, False],
            "news2_score": pd.array([0, None], dtype="Int64"),
            "news2_riesgo": ["Bajo", None],
            "news2_rojo_aislado": [False, None],
            "news2_imputado": [True, None],
            # object y no float: así la deja la tubería real, porque mezcla enteros con
            # el nulo de las tomas no puntuables.
            "news2_puntos_imputados": pd.Series([0, None], dtype=object),
        }
    )


def _rechaza(df: pd.DataFrame, motivo: str) -> None:
    """Afirma que el esquema de observaciones rechaza `df`."""
    try:
        esquemas.validar(esquemas.OBSERVACIONES, df, "prueba")
    except esquemas.ErrorDeEsquema:
        return
    raise AssertionError(f"el esquema ACEPTÓ datos que debía rechazar: {motivo}")


# =============================================================================
# El caso base tiene que pasar, o el resto de las pruebas no prueban nada.
# =============================================================================
def test_observaciones_validas_pasan():
    esquemas.validar(esquemas.OBSERVACIONES, _observaciones_validas(), "prueba")


# =============================================================================
# Rangos fisiológicos
# =============================================================================
def test_rechaza_spo2_imposible():
    df = _observaciones_validas()
    df.loc[0, "spo2"] = 10.0  # el caso real del demo: un error de registro
    _rechaza(df, "SpO2 de 10 %")


def test_rechaza_sistolica_imposible():
    df = _observaciones_validas()
    df.loc[0, "presion_sistolica"] = 11.0  # el otro caso real del demo
    _rechaza(df, "sistólica de 11 mmHg")


def test_rechaza_temperatura_sin_convertir():
    """
    El modo de falla que importa: una temperatura que quedó en Fahrenheit.

    98.6 °F es un paciente sano, pero leído como Celsius es imposible. Si la conversión
    se rompiera, el esquema tiene que verlo.
    """
    df = _observaciones_validas()
    df.loc[0, "temperatura"] = 98.6
    _rechaza(df, "temperatura en Fahrenheit")


# =============================================================================
# Invariantes entre columnas
# =============================================================================
def test_rechaza_score_en_toma_no_puntuable():
    """Un NEWS2 calculado sobre datos incompletos no es un NEWS2 válido."""
    df = _observaciones_validas()
    df["news2_score"] = pd.array([0, 3], dtype="Int64")  # la fila 1 no es puntuable
    _rechaza(df, "score en una toma no puntuable")


def test_rechaza_puntuable_sin_score():
    df = _observaciones_validas()
    df["news2_score"] = pd.array([None, None], dtype="Int64")
    _rechaza(df, "toma puntuable sin score")


def test_rechaza_nivel_de_riesgo_inventado():
    df = _observaciones_validas()
    df.loc[0, "news2_riesgo"] = "Critico"  # no es uno de los cuatro niveles
    _rechaza(df, "nivel de riesgo fuera de la escala")


def test_rechaza_score_fuera_de_la_escala():
    df = _observaciones_validas()
    df["news2_score"] = pd.array([99, None], dtype="Int64")
    _rechaza(df, "score de 99")


def test_los_niveles_salen_del_motor_y_no_de_una_copia():
    """
    Si alguien renombra un nivel en `news2.py`, el esquema tiene que seguirlo solo.

    Esta prueba existe porque la primera versión del esquema copió los cuatro nombres a
    mano y los copió mal.
    """
    assert esquemas.NIVELES_RIESGO == list(
        news2.NivelRiesgo.__args__
    ), "los niveles del esquema se desincronizaron del motor"


# =============================================================================
# El contrato de una toma suelta (Pydantic) — lo que va a recibir la API
# =============================================================================
def test_toma_valida():
    toma = esquemas.TomaDeSignosVitales(
        frecuencia_respiratoria=16,
        spo2=98,
        temperatura=36.5,
        presion_sistolica=120,
        frecuencia_cardiaca=72,
    )
    assert toma.consciencia is None, "consciencia debe poder omitirse (ADR-007)"


def _rechaza_toma(motivo: str, **campos) -> None:
    try:
        esquemas.TomaDeSignosVitales(**campos)
    except ValidationError:
        return
    raise AssertionError(f"el contrato ACEPTÓ una toma que debía rechazar: {motivo}")


def _toma_base() -> dict:
    return dict(
        frecuencia_respiratoria=16,
        spo2=98,
        temperatura=36.5,
        presion_sistolica=120,
        frecuencia_cardiaca=72,
    )


def test_rechaza_toma_incompleta():
    campos = _toma_base()
    del campos["spo2"]
    _rechaza_toma("falta la SpO2", **campos)


def test_rechaza_toma_fuera_de_rango():
    _rechaza_toma("SpO2 de 10 %", **{**_toma_base(), "spo2": 10})


def test_rechaza_consciencia_invalida():
    _rechaza_toma("consciencia 'Z'", **{**_toma_base(), "consciencia": "Z"})


def test_rechaza_campo_desconocido():
    """`extra=forbid`: un campo mal escrito tiene que fallar, no ignorarse en silencio."""
    _rechaza_toma("campo 'spo_2' mal escrito", **{**_toma_base(), "spo_2": 98})


def test_acepta_las_cinco_letras_de_acvpu():
    for letra in ("A", "C", "V", "P", "U"):
        esquemas.TomaDeSignosVitales(**{**_toma_base(), "consciencia": letra})


PRUEBAS = [
    test_observaciones_validas_pasan,
    test_rechaza_spo2_imposible,
    test_rechaza_sistolica_imposible,
    test_rechaza_temperatura_sin_convertir,
    test_rechaza_score_en_toma_no_puntuable,
    test_rechaza_puntuable_sin_score,
    test_rechaza_nivel_de_riesgo_inventado,
    test_rechaza_score_fuera_de_la_escala,
    test_los_niveles_salen_del_motor_y_no_de_una_copia,
    test_toma_valida,
    test_rechaza_toma_incompleta,
    test_rechaza_toma_fuera_de_rango,
    test_rechaza_consciencia_invalida,
    test_rechaza_campo_desconocido,
    test_acepta_las_cinco_letras_de_acvpu,
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
    print(f"OK: {len(PRUEBAS)} pruebas de validacion de esquemas")
