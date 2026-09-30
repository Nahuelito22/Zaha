"""
Pruebas de la regla de alerta y su tasa de referencia (SCRUM-80).

Lo que se verifica es que la regla de este módulo sea **la misma** que la del trigger de
la base, y que el rojo aislado alerte. Si las dos se desincronizan, nada falla: la tesis
publica una tasa de referencia que describe a un sistema distinto del que se despliega, y
toda la comparativa de SCRUM-58 queda anclada a un número equivocado.

    cd ml_engine && python -m pytest tests/test_alertas.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && python tests/test_alertas.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.data import alertas, news2  # noqa: E402

RAIZ_REPO = Path(__file__).resolve().parents[2]
MIGRACION = RAIZ_REPO / "supabase" / "migrations" / "20260521000100_news2_engine.sql"


def _datos(riesgos, horas_por_episodio=6.0, puntuable=True):
    """Un episodio por riesgo, con una toma cada uno."""
    obs = pd.DataFrame({
        "episodio_id": range(1, len(riesgos) + 1),
        "paciente_id": range(1, len(riesgos) + 1),
        "news2_riesgo": list(riesgos),
        "news2_rojo_aislado": [False] * len(riesgos),
        "puntuable": [puntuable] * len(riesgos),
    })
    epi = pd.DataFrame({
        "episodio_id": range(1, len(riesgos) + 1),
        "paciente_id": range(1, len(riesgos) + 1),
        "horas_en_guardia": [horas_por_episodio] * len(riesgos),
    })
    return obs, epi


# =============================================================================
# La regla, contrastada contra la fuente de verdad
# =============================================================================
def test_la_regla_coincide_con_el_trigger_de_la_base():
    """
    Lee la migración y verifica que el IN del trigger sea el mismo conjunto.

    Es la prueba que justifica el módulo entero: son la misma regla escrita dos veces,
    en dos runtimes, y sólo un test que mire las dos puede detectar que se separaron.
    """
    assert MIGRACION.exists(), f"no encontré la migración en {MIGRACION}"
    sql = MIGRACION.read_text(encoding="utf-8")

    m = re.search(r"risk_level\s+IN\s*\(([^)]*)\)", sql, re.IGNORECASE)
    assert m, "no encontré la condición `risk_level IN (...)` en el trigger"

    del_sql = {v.strip().strip("'") for v in m.group(1).split(",")}
    assert del_sql == set(alertas.RIESGOS_QUE_ALERTAN), (
        f"la regla se desincronizó: el trigger dice {sorted(del_sql)} y "
        f"el módulo {sorted(alertas.RIESGOS_QUE_ALERTAN)}"
    )


def test_los_riesgos_que_alertan_existen_en_el_motor():
    """Un typo en un nivel ('Medio bajo') haría que esa categoría nunca alerte."""
    from typing import get_args

    validos = set(get_args(news2.NivelRiesgo))
    assert set(alertas.RIESGOS_QUE_ALERTAN) <= validos, (
        f"{set(alertas.RIESGOS_QUE_ALERTAN) - validos} no son niveles de riesgo válidos"
    )


def test_bajo_no_alerta_y_los_otros_tres_si():
    obs, _ = _datos(["Bajo", "Medio Bajo", "Medio", "Alto"])
    marcadas = alertas.marcar(obs)
    assert list(marcadas["alerta"]) == [False, True, True, True]


def test_el_rojo_aislado_alerta_aunque_el_score_sea_bajo():
    """
    El caso que separa la regla real de 'score >= 5'. Una frecuencia respiratoria de 6
    puntúa 3 y deja el nivel en Medio Bajo con score total bajo: tiene que alertar.
    """
    resultado = news2.calcular(
        frecuencia_respiratoria=6, spo2=98, temperatura=36.5,
        presion_sistolica=120, frecuencia_cardiaca=72,
    )
    assert resultado.score < 5, f"el caso dejó de tener score bajo: {resultado.score}"
    assert resultado.rojo_aislado
    assert resultado.riesgo in alertas.RIESGOS_QUE_ALERTAN, (
        "un rojo aislado con score bajo no está alertando"
    )


def test_una_toma_no_puntuable_nunca_alerta():
    obs, _ = _datos(["Alto", "Alto"], puntuable=False)
    assert not alertas.marcar(obs)["alerta"].any()


# =============================================================================
# Los tres denominadores
# =============================================================================
def test_la_tasa_por_toma_cuenta_solo_puntuables():
    obs, epi = _datos(["Bajo", "Alto", "Alto", "Bajo"])
    obs.loc[3, "puntuable"] = False  # una no puntuable, sale del denominador

    t = alertas.tasa(obs, epi)
    assert t.tomas_puntuables == 3
    assert t.tomas_con_alerta == 2
    assert abs(t.por_toma - 2 / 3) < 1e-9


def test_un_episodio_con_varias_tomas_cuenta_una_vez():
    obs, epi = _datos(["Alto", "Alto", "Bajo"])
    obs["episodio_id"] = [1, 1, 2]  # dos tomas del mismo episodio
    epi = epi.iloc[:2].copy()
    epi["episodio_id"] = [1, 2]

    t = alertas.tasa(obs, epi)
    assert t.episodios_puntuables == 2
    assert t.episodios_con_alerta == 1, "el episodio con 2 alertas se contó dos veces"


def test_la_tasa_por_paciente_dia_usa_todas_las_estadias():
    """
    Un episodio sin tomas puntuables sigue sumando tiempo al denominador. Si se
    excluyera, la tasa subiría y describiría un sistema más ruidoso que el real.
    """
    obs, epi = _datos(["Alto", "Bajo"], horas_por_episodio=12.0)
    epi = pd.concat([epi, pd.DataFrame([{
        "episodio_id": 99, "paciente_id": 99, "horas_en_guardia": 24.0,
    }])], ignore_index=True)

    t = alertas.tasa(obs, epi)
    assert t.episodios_totales == 3
    assert t.episodios_sin_toma_puntuable == 1
    assert abs(t.pacientes_dia - (12 + 12 + 24) / 24) < 1e-9
    assert abs(t.por_100_pacientes_dia - 100 * 1 / 2.0) < 1e-9


def test_la_frecuencia_de_medicion_se_reporta():
    """Sin la frecuencia, la tasa por paciente-día no se puede interpretar."""
    obs, epi = _datos(["Alto", "Bajo"], horas_por_episodio=12.0)
    t = alertas.tasa(obs, epi)
    assert abs(t.tomas_por_paciente_dia - 2 / 1.0) < 1e-9


def test_la_tasa_de_una_cohorte_vacia_no_divide_por_cero():
    obs, epi = _datos([])
    t = alertas.tasa(obs, epi)
    assert t.por_toma == 0.0 and t.por_episodio == 0.0 and t.por_100_pacientes_dia == 0.0


# =============================================================================
# Desglose
# =============================================================================
def test_el_desglose_del_rojo_aislado_ignora_la_consciencia():
    """
    `sub_consciencia` es siempre imputada (ADR-007): MIMIC no la tiene. Contarla como
    origen de un rojo aislado sería atribuirle a un dato que no existe una alerta real.
    """
    obs = pd.DataFrame({
        "puntuable": [True],
        "news2_rojo_aislado": [True],
        "sub_frecuencia_respiratoria": [3],
        "sub_consciencia": [3],
    })
    desglose = alertas.desglose_rojo_aislado(obs)
    assert "consciencia" not in desglose.index
    assert desglose["frecuencia_respiratoria"] == 1


PRUEBAS = [
    test_la_regla_coincide_con_el_trigger_de_la_base,
    test_los_riesgos_que_alertan_existen_en_el_motor,
    test_bajo_no_alerta_y_los_otros_tres_si,
    test_el_rojo_aislado_alerta_aunque_el_score_sea_bajo,
    test_una_toma_no_puntuable_nunca_alerta,
    test_la_tasa_por_toma_cuenta_solo_puntuables,
    test_un_episodio_con_varias_tomas_cuenta_una_vez,
    test_la_tasa_por_paciente_dia_usa_todas_las_estadias,
    test_la_frecuencia_de_medicion_se_reporta,
    test_la_tasa_de_una_cohorte_vacia_no_divide_por_cero,
    test_el_desglose_del_rojo_aislado_ignora_la_consciencia,
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
    print(f"OK: {len(PRUEBAS)} pruebas de la regla de alerta")
