"""
Pruebas de la ingesta de la cohorte TRIAGE (ADR-009).

Lo que se verifica es que esta cohorte NO se degrade silenciosamente hasta parecerse a
MIMIC. Dos cosas la hacen valiosa y las dos se pueden perder sin que nada falle: que la
consciencia sea el **dato real** del estudio y no una imputación, y que los rangos
plausibles sean los **mismos** que los de la otra cohorte y los de la base. Si la
consciencia se imputara por error, esta cohorte dejaría de aportar lo que MIMIC no tiene;
si los rangos se separaran, los NEWS2 de las dos cohortes dejarían de ser comparables y la
tesis compararía peras con manzanas sin avisar.

    cd ml_engine && python -m pytest tests/test_triage.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && python tests/test_triage.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.data import mimic_ed, news2, triage  # noqa: E402
from src.validation import esquemas  # noqa: E402


def _crudo(**reemplazos) -> pd.DataFrame:
    """Una fila sana del formato TRIAGE, con los campos que se quieran pisar."""
    base = {
        "hospital": "Aarau", "country": "Switzerland", "gender": "m", "age": 60,
        "resp_rate": 16, "SpO2": 98, "temp": 36.5, "BPS": 120, "BPD": 80, "HR": 72,
        "confusion": 0, "death30d": 0, "ICU": 0,
        "MR-proADM": 0.5, "PCT": 0.1, "discharge location": "Home", "LOS": 3.0,
    }
    base.update(reemplazos)
    return pd.DataFrame([base])


# =============================================================================
# Lo que hace valiosa a esta cohorte
# =============================================================================
def test_la_confusion_se_lee_como_dato_real_y_no_se_imputa():
    """
    Es la razón de ser del ADR-009: MIMIC no tiene consciencia en NINGUNA fila y acá sí.
    Si esto se rompiera, la cohorte perdería su ventaja sin que nada fallara.
    """
    con = triage.normalizar(_crudo(confusion=1))
    sin = triage.normalizar(_crudo(confusion=0))

    assert con["consciencia"].iloc[0] == "C"
    assert sin["consciencia"].iloc[0] == "A"
    assert con["sub_consciencia"].iloc[0] == 3, "la confusión nueva tiene que puntuar 3"
    assert sin["sub_consciencia"].iloc[0] == 0


def test_la_confusion_cambia_el_score():
    """Si el parámetro se leyera pero no llegara al motor, el score no se movería."""
    con = triage.normalizar(_crudo(confusion=1))["news2_score"].iloc[0]
    sin = triage.normalizar(_crudo(confusion=0))["news2_score"].iloc[0]
    assert con - sin == 3, f"la confusión tiene que sumar 3 puntos, sumó {con - sin}"


def test_solo_se_imputa_el_oxigeno():
    """
    En MIMIC se imputan 2 parámetros; acá tiene que imputarse 1. Los puntos imputados
    del oxígeno a aire ambiente son 0, pero la marca `news2_imputado` sigue en True.
    """
    fila = triage.normalizar(_crudo(confusion=1))
    assert bool(fila["news2_imputado"].iloc[0]), "la imputación del oxígeno no se marcó"
    assert fila["sub_oxigeno_suplementario"].iloc[0] == 0


# =============================================================================
# Consistencia con la otra cohorte y con la base
# =============================================================================
def test_los_rangos_plausibles_son_los_mismos_que_los_de_mimic():
    """
    Fuente única. Si se separaran, el NEWS2 de las dos cohortes se calcularía sobre
    universos distintos y la comparación entre ellas dejaría de significar algo.
    """
    assert triage.RANGOS_PLAUSIBLES is esquemas.RANGOS_PLAUSIBLES
    assert mimic_ed.RANGOS_PLAUSIBLES is esquemas.RANGOS_PLAUSIBLES


def test_un_valor_implausible_se_anula_y_la_fila_deja_de_ser_puntuable():
    fila = triage.normalizar(_crudo(SpO2=10))
    assert pd.isna(fila["spo2"].iloc[0])
    assert fila["valores_descartados"].iloc[0] == 1
    assert not bool(fila["puntuable"].iloc[0])
    assert pd.isna(fila["news2_score"].iloc[0]), "puntuó una fila incompleta"


def test_el_invariante_de_score_y_puntuable_se_mantiene():
    """El mismo invariante que valida la tubería de MIMIC: score si y solo si puntuable."""
    df = triage.normalizar(
        pd.concat([_crudo(), _crudo(SpO2=10), _crudo(confusion=1)], ignore_index=True)
    )
    assert (df["news2_score"].notna() == df["puntuable"]).all()


# =============================================================================
# Los desenlaces
# =============================================================================
def test_se_conservan_los_dos_desenlaces():
    """
    Elegir cuál predecir es decisión del análisis, no de la ingesta. Si el módulo se
    quedara con uno, esa decisión quedaría enterrada acá.
    """
    df = triage.normalizar(_crudo(death30d=1, ICU=1))
    for columna in triage.DESENLACES:
        assert columna in df.columns, f"falta el desenlace {columna}"
    assert df["muerte_30d"].iloc[0] == 1
    assert df["ingreso_uci"].iloc[0] == 1


def test_los_desenlaces_no_son_la_etiqueta_v2():
    """
    Recordatorio ejecutable del límite del ADR-009: esta cohorte no tiene tiempo, así que
    no puede tener la etiqueta v2. Si alguien agregara una columna `y` acá, las dos
    definiciones se mezclarían en una misma métrica sin que nadie lo note.
    """
    df = triage.normalizar(_crudo())
    assert "y" not in df.columns, "esta cohorte no soporta la etiqueta v2 (ADR-009)"
    assert "medido_en" not in df.columns, "no hay eje temporal en esta cohorte"


def test_el_resumen_cuadra():
    # La cuarta fila se rompe con SpO2=10 y no con HR=5: el rango plausible de
    # frecuencia cardíaca es (0, 300), así que un 5 lo pasa. Es la definición del
    # proyecto, compartida con los CHECK de la base, no un descuido de este módulo.
    crudo = pd.concat(
        [_crudo(death30d=1), _crudo(ICU=1), _crudo(confusion=1), _crudo(SpO2=10)],
        ignore_index=True,
    )
    r = triage.resumir(triage.normalizar(crudo))
    assert r.pacientes == 4
    assert r.puntuables == 3
    assert r.con_confusion == 1
    assert r.muertes_30d == 1
    assert r.ingresos_uci == 1
    assert abs(r.prevalencia_muerte - 0.25) < 1e-9


# =============================================================================
# Esquema
# =============================================================================
def test_el_esquema_rechaza_un_desenlace_que_no_es_binario():
    crudo = _crudo(death30d=2)
    try:
        esquemas.validar(esquemas.TRIAGE_CRUDO, crudo, "prueba")
    except esquemas.ErrorDeEsquema:
        return
    raise AssertionError("aceptó un death30d fuera de {0, 1}")


def test_el_esquema_rechaza_si_falta_la_confusion():
    crudo = _crudo().drop(columns=["confusion"])
    try:
        esquemas.validar(esquemas.TRIAGE_CRUDO, crudo, "prueba")
    except esquemas.ErrorDeEsquema:
        return
    raise AssertionError("aceptó el archivo sin la columna que justifica el ADR-009")


def test_cargar_un_archivo_que_no_existe_explica_de_donde_sacarlo():
    try:
        triage.cargar(Path("no_existe_este_archivo.xls"))
    except FileNotFoundError as e:
        assert "zenodo" in str(e).lower()
        return
    raise AssertionError("no falló con un archivo inexistente")


PRUEBAS = [
    test_la_confusion_se_lee_como_dato_real_y_no_se_imputa,
    test_la_confusion_cambia_el_score,
    test_solo_se_imputa_el_oxigeno,
    test_los_rangos_plausibles_son_los_mismos_que_los_de_mimic,
    test_un_valor_implausible_se_anula_y_la_fila_deja_de_ser_puntuable,
    test_el_invariante_de_score_y_puntuable_se_mantiene,
    test_se_conservan_los_dos_desenlaces,
    test_los_desenlaces_no_son_la_etiqueta_v2,
    test_el_resumen_cuadra,
    test_el_esquema_rechaza_un_desenlace_que_no_es_binario,
    test_el_esquema_rechaza_si_falta_la_confusion,
    test_cargar_un_archivo_que_no_existe_explica_de_donde_sacarlo,
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
    print(f"OK: {len(PRUEBAS)} pruebas de la cohorte TRIAGE")
