"""
Pruebas del baseline sobre el snapshot (SCRUM-56).

Lo que se verifica son las tres cosas que, si se rompen, producen un resultado **mejor** y
falso — que es la clase de error más peligrosa en un trabajo de tesis, porque nadie lo
investiga cuando el número sale lindo:

1. Que las features sean sólo las que hay al pie de la cama. Colar un biomarcador mejora el
   modelo y vuelve la comparación contra NEWS2 tramposa.
2. Que los puntajes de la validación cruzada sean **fuera de fold**. Un puntaje calculado
   por un modelo que vio a ese paciente infla todo y no falla nunca.
3. Que la comparación a sensibilidad igualada se haga contra el rival correcto.

    cd ml_engine && python -m pytest tests/test_baseline.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && python tests/test_baseline.py
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.data import alertas  # noqa: E402
from src.models import baseline  # noqa: E402


def _cohorte(n: int = 240, semilla: int = 3) -> pd.DataFrame:
    """
    Cohorte sintética con señal real: los pacientes con vitales peores mueren más.

    Sin señal, cualquier prueba sobre AUROC daría 0,5 y no distinguiría un modelo que
    aprende de uno roto.
    """
    rng = np.random.default_rng(semilla)
    riesgo = rng.random(n)
    df = pd.DataFrame(
        {
            "paciente_id": np.arange(1, n + 1),
            "frecuencia_respiratoria": 16 + 14 * riesgo + rng.normal(0, 1, n),
            "spo2": 99 - 14 * riesgo + rng.normal(0, 1, n),
            "temperatura": 36.5 + rng.normal(0, 0.4, n),
            "presion_sistolica": 130 - 45 * riesgo + rng.normal(0, 5, n),
            "frecuencia_cardiaca": 75 + 45 * riesgo + rng.normal(0, 5, n),
            "edad": rng.integers(18, 95, n),
            "consciencia": np.where(riesgo > 0.9, "C", "A"),
            "puntuable": True,
            # el desenlace depende del riesgo, con ruido
            "muerte_30d": (riesgo + rng.normal(0, 0.18, n) > 0.80).astype(int),
            "ingreso_uci": (riesgo + rng.normal(0, 0.25, n) > 0.70).astype(int),
        }
    )
    # Biomarcadores: existen en el crudo y NO tienen que llegar al modelo.
    df["PCT"] = riesgo * 10
    df["MR-proADM"] = riesgo * 5
    return df


# =============================================================================
# 1 · Las features
# =============================================================================
def test_la_matriz_no_incluye_biomarcadores():
    """
    El error que haría el resultado mejor y falso: la procalcitonina predice muy bien y
    NO existe al pie de la cama. Si entrara, el modelo ganaría por información que el
    sistema real nunca va a tener y que NEWS2 tampoco tiene.
    """
    X = baseline.matriz(_cohorte())
    for prohibida in baseline.EXCLUIDAS_POR_NO_ESTAR_AL_PIE_DE_LA_CAMA:
        assert prohibida not in X.columns, f"{prohibida} se coló en la matriz de features"


def test_la_matriz_es_exactamente_las_features_declaradas():
    X = baseline.matriz(_cohorte())
    assert list(X.columns) == baseline.FEATURES


def test_la_confusion_se_deriva_de_consciencia():
    """
    Se reconstruye desde `consciencia` y no se lee del crudo, para que el modelo y el
    motor NEWS2 vean exactamente el mismo dato.
    """
    df = _cohorte()
    X = baseline.matriz(df)
    esperado = (df["consciencia"] == "C").astype(int)
    assert (X["confusion"].to_numpy() == esperado.to_numpy()).all()


def test_las_features_son_las_que_guarda_la_app():
    """Los 5 vitales de MIMIC más la consciencia. Si aparece una feature nueva, revisar."""
    vitales = {
        "frecuencia_respiratoria", "spo2", "temperatura",
        "presion_sistolica", "frecuencia_cardiaca",
    }
    assert vitales <= set(baseline.FEATURES)
    assert "confusion" in baseline.FEATURES


# =============================================================================
# 2 · Que la evaluación no tenga fuga
# =============================================================================
def test_la_cv_anidada_devuelve_un_puntaje_por_paciente():
    r = baseline.evaluar_anidada(_cohorte(), n_externo=3, n_interno=2)
    assert len(r.puntajes) == r.n
    assert np.isfinite(r.puntajes).all()


def test_la_cv_anidada_elige_una_familia_por_fold():
    r = baseline.evaluar_anidada(_cohorte(), n_externo=3, n_interno=2)
    assert len(r.elegidos) == 3
    assert set(r.elegidos) <= set(baseline.MODELOS)


def test_la_cv_anidada_aprende_algo_sobre_datos_con_senal():
    from sklearn.metrics import roc_auc_score

    r = baseline.evaluar_anidada(_cohorte(), n_externo=3, n_interno=2)
    assert roc_auc_score(r.y, r.puntajes) > 0.70, "no aprendió una señal que está puesta"


def test_sobre_ruido_puro_la_cv_anidada_NO_encuentra_senal():
    """
    La prueba que detecta la fuga. Con la etiqueta permutada no queda nada que aprender,
    así que un AUROC alto sólo puede venir de que el modelo vio la respuesta.
    """
    from sklearn.metrics import roc_auc_score

    df = _cohorte()
    rng = np.random.default_rng(11)
    df["muerte_30d"] = rng.permutation(df["muerte_30d"].to_numpy())

    r = baseline.evaluar_anidada(df, n_externo=3, n_interno=2)
    auc = roc_auc_score(r.y, r.puntajes)
    assert auc < 0.68, f"AUROC {auc:.3f} sobre etiqueta permutada: hay fuga"


# =============================================================================
# 3 · La comparación
# =============================================================================
def test_la_curva_de_operacion_es_monotona_en_sensibilidad():
    """Bajar el umbral nunca puede reducir la sensibilidad."""
    y = np.array([1, 0, 1, 0, 0, 1, 0, 0])
    puntaje = np.array([0.9, 0.1, 0.8, 0.2, 0.3, 0.7, 0.05, 0.4])
    curva = alertas.curva_operacion(y, puntaje)
    assert curva["sensibilidad"].is_monotonic_increasing
    assert curva["tasa_alertas"].is_monotonic_increasing


def test_la_tasa_para_sensibilidad_toma_la_mas_barata():
    y = np.array([1, 0, 1, 0, 0, 0, 0, 0])
    puntaje = np.array([0.9, 0.1, 0.8, 0.2, 0.3, 0.05, 0.4, 0.15])
    curva = alertas.curva_operacion(y, puntaje)
    assert abs(alertas.tasa_para_sensibilidad(curva, 1.0) - 2 / 8) < 1e-9


def test_una_sensibilidad_inalcanzable_devuelve_nan():
    """No es un error: significa que ese sistema no puede operar ahí."""
    curva = pd.DataFrame({"umbral": [1.0], "tasa_alertas": [0.1], "sensibilidad": [0.3]})
    assert np.isnan(alertas.tasa_para_sensibilidad(curva, 0.9))


def test_la_tolerancia_no_descarta_el_umbral_que_empata():
    """
    La trampa real: la sensibilidad de NEWS2 sale de 29/54 = 0,537037… Si el llamador
    pasa ese valor exacto, el error de punto flotante no puede descartar el umbral que
    justamente lo alcanza — eso favorecería al sistema comparado.
    """
    y = np.array([1, 1, 1, 0, 0, 0])
    puntaje = np.array([0.9, 0.8, 0.1, 0.2, 0.05, 0.3])
    curva = alertas.curva_operacion(y, puntaje)
    objetivo = 2 / 3
    assert abs(alertas.tasa_para_sensibilidad(curva, objetivo) - 2 / 6) < 1e-9


def test_el_intervalo_de_reduccion_cubre_el_valor_puntual():
    df = _cohorte()
    r = baseline.evaluar_anidada(df, n_externo=3, n_interno=2)
    news2_falso = df["frecuencia_respiratoria"].to_numpy()

    puntual, lo, hi = baseline.intervalo_reduccion(
        r.y, r.puntajes, news2_falso, 0.5, remuestreos=120
    )
    if not np.isnan(lo):
        assert lo <= puntual <= hi, f"el puntual {puntual} cae fuera de [{lo}, {hi}]"


PRUEBAS = [
    test_la_matriz_no_incluye_biomarcadores,
    test_la_matriz_es_exactamente_las_features_declaradas,
    test_la_confusion_se_deriva_de_consciencia,
    test_las_features_son_las_que_guarda_la_app,
    test_la_cv_anidada_devuelve_un_puntaje_por_paciente,
    test_la_cv_anidada_elige_una_familia_por_fold,
    test_la_cv_anidada_aprende_algo_sobre_datos_con_senal,
    test_sobre_ruido_puro_la_cv_anidada_NO_encuentra_senal,
    test_la_curva_de_operacion_es_monotona_en_sensibilidad,
    test_la_tasa_para_sensibilidad_toma_la_mas_barata,
    test_una_sensibilidad_inalcanzable_devuelve_nan,
    test_la_tolerancia_no_descarta_el_umbral_que_empata,
    test_el_intervalo_de_reduccion_cubre_el_valor_puntual,
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
    print(f"OK: {len(PRUEBAS)} pruebas del baseline")
