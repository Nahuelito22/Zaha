"""
Pruebas de la etiqueta v2 (SCRUM-53).

Lo que se verifica son los bordes de la definición, que es donde una etiqueta se rompe
sin avisar: el límite exacto de la ventana ciega, el límite del horizonte, y que una
toma descartada no termine contada como negativa. Un error acá no produce ningún
síntoma visible — produce un modelo que aprendió otra cosa.

    cd ml_engine && python -m pytest tests/test_etiquetas.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && python tests/test_etiquetas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.data import etiquetas  # noqa: E402

EVENTO = pd.Timestamp("2026-09-15 12:00")


def _caso(*horas_antes_del_evento: float, adverso: bool = True) -> pd.DataFrame:
    """Un episodio con tomas a N horas del evento. Devuelve la tabla ya etiquetada."""
    observaciones = pd.DataFrame(
        {
            "episodio_id": [1] * len(horas_antes_del_evento),
            "paciente_id": [10] * len(horas_antes_del_evento),
            "medido_en": [EVENTO - pd.Timedelta(hours=h) for h in horas_antes_del_evento],
        }
    )
    episodios = pd.DataFrame(
        {
            "episodio_id": [1],
            "egreso_en": [EVENTO],
            "desenlace_adverso": [adverso],
        }
    )
    return etiquetas.etiquetar(observaciones, episodios)


def _y(df: pd.DataFrame) -> list:
    return [None if pd.isna(v) else int(v) for v in df["y"]]


# =============================================================================
# El caso central
# =============================================================================
def test_toma_dentro_del_horizonte_es_positiva():
    assert _y(_caso(12)) == [1], "una toma 12 h antes del evento tiene que ser y=1"


def test_toma_sin_evento_es_negativa():
    assert _y(_caso(12, adverso=False)) == [0], "sin desenlace adverso, y=0"


def test_toma_fuera_del_horizonte_es_negativa():
    assert _y(_caso(30)) == [0], "30 h antes está fuera del horizonte de 24 h"


# =============================================================================
# Los bordes exactos. El intervalo es (1 h, 24 h]: abierto abajo, cerrado arriba.
# =============================================================================
def test_borde_de_la_ventana_ciega_se_descarta():
    df = _caso(1.0)
    assert _y(df) == [None], "exactamente 1 h cae DENTRO de la ventana ciega"
    assert bool(df["en_ventana_ciega"].iloc[0])


def test_apenas_despues_de_la_ventana_ciega_es_positiva():
    assert _y(_caso(1.01)) == [1], "apenas pasada 1 h ya es etiquetable y positiva"


def test_borde_del_horizonte_es_positiva():
    assert _y(_caso(24.0)) == [1], "exactamente 24 h todavía es positiva"


def test_apenas_pasado_el_horizonte_es_negativa():
    assert _y(_caso(24.01)) == [0], "pasadas las 24 h ya es negativa"


# =============================================================================
# Los dos motivos de descarte, que no son lo mismo
# =============================================================================
def test_ventana_ciega_no_se_cuenta_como_negativa():
    """
    El error que más caro sale: marcar como sana una toma de un paciente que se está
    descompensando. Tiene que quedar nula, no en 0.
    """
    df = _caso(0.5)
    assert _y(df) == [None]
    assert bool(df["en_ventana_ciega"].iloc[0])
    assert not bool(df["posterior_al_evento"].iloc[0])


def test_toma_posterior_al_egreso_se_descarta_y_se_distingue():
    """En el demo hay 65 de estas, alguna con 35 h de desfasaje. No son ventana ciega."""
    df = _caso(-3)
    assert _y(df) == [None]
    assert bool(df["posterior_al_evento"].iloc[0])
    assert not bool(df["en_ventana_ciega"].iloc[0]), "un dato roto no es una decisión"


# =============================================================================
# La etiqueta no puede mirar el NEWS2 (sería circular)
# =============================================================================
def test_la_etiqueta_no_depende_del_news2():
    """
    Se etiquetan dos veces las mismas tomas, con scores NEWS2 opuestos. Si la etiqueta
    cambiara, estaría contaminada por la escala que el proyecto quiere superar.
    """
    base = pd.DataFrame(
        {
            "episodio_id": [1, 1],
            "paciente_id": [10, 10],
            "medido_en": [EVENTO - pd.Timedelta(hours=h) for h in (12, 30)],
        }
    )
    episodios = pd.DataFrame(
        {"episodio_id": [1], "egreso_en": [EVENTO], "desenlace_adverso": [True]}
    )

    sano = base.assign(news2_score=pd.array([0, 0], dtype="Int64"))
    grave = base.assign(news2_score=pd.array([15, 15], dtype="Int64"))

    assert _y(etiquetas.etiquetar(sano, episodios)) == _y(
        etiquetas.etiquetar(grave, episodios)
    ), "la etiqueta cambió con el NEWS2: está contaminada"


# =============================================================================
# El resumen tiene que cuadrar
# =============================================================================
def test_el_resumen_cuadra():
    df = _caso(0.5, -3, 12, 30)  # ciega, posterior, positiva, negativa
    r = etiquetas.resumir(df)
    assert r.observaciones == 4
    assert r.en_ventana_ciega == 1
    assert r.posteriores_al_evento == 1
    assert r.etiquetables == 2, "descartadas fuera, quedan 2"
    assert r.positivas == 1
    assert abs(r.prevalencia - 0.5) < 1e-9


PRUEBAS = [
    test_toma_dentro_del_horizonte_es_positiva,
    test_toma_sin_evento_es_negativa,
    test_toma_fuera_del_horizonte_es_negativa,
    test_borde_de_la_ventana_ciega_se_descarta,
    test_apenas_despues_de_la_ventana_ciega_es_positiva,
    test_borde_del_horizonte_es_positiva,
    test_apenas_pasado_el_horizonte_es_negativa,
    test_ventana_ciega_no_se_cuenta_como_negativa,
    test_toma_posterior_al_egreso_se_descarta_y_se_distingue,
    test_la_etiqueta_no_depende_del_news2,
    test_el_resumen_cuadra,
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
    print(f"OK: {len(PRUEBAS)} pruebas de la etiqueta v2")
