"""
Pruebas de la exportación a ONNX (SCRUM-59).

Lo que se verifica es que **el modelo servido sea el mismo que el evaluado**. Es la clase de
error que no avisa: un `.onnx` convertido de más, con el escalado perdido o las columnas
corridas, sigue devolviendo probabilidades perfectamente plausibles — sólo que de otro
modelo. Las métricas de la tesis describirían entonces algo que no es lo que corre.

    cd ml_engine && .venv/Scripts/python -m pytest tests/test_exportar.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && .venv/Scripts/python tests/test_exportar.py
"""
import json
import sys
import tempfile
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.models import baseline, exportar  # noqa: E402


def _cohorte(n: int = 300, semilla: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    riesgo = rng.random(n)
    df = pd.DataFrame({
        "paciente_id": np.arange(1, n + 1),
        "frecuencia_respiratoria": 16 + 14 * riesgo + rng.normal(0, 1, n),
        "spo2": 99 - 14 * riesgo + rng.normal(0, 1, n),
        "temperatura": 36.5 + rng.normal(0, 0.4, n),
        "presion_sistolica": 130 - 45 * riesgo + rng.normal(0, 5, n),
        "frecuencia_cardiaca": 75 + 45 * riesgo + rng.normal(0, 5, n),
        "edad": rng.integers(18, 95, n),
        "consciencia": np.where(riesgo > 0.9, "C", "A"),
        "puntuable": True,
        "muerte_30d": (riesgo + rng.normal(0, 0.18, n) > 0.80).astype(int),
        "ingreso_uci": (riesgo + rng.normal(0, 0.25, n) > 0.70).astype(int),
    })
    df["PCT"] = riesgo * 10
    df["MR-proADM"] = riesgo * 5
    return df


# =============================================================================
# La garantía central: el modelo servido es el evaluado
# =============================================================================
def test_onnx_y_sklearn_dan_la_misma_probabilidad():
    df = _cohorte()
    modelo = baseline.entrenar(df)
    X = baseline.matriz(df).to_numpy(dtype=float)

    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "m.onnx"
        exportar.exportar(modelo, X.shape[1], ruta)
        paridad = exportar.verificar_paridad(modelo, ruta, X, df["muerte_30d"].to_numpy().astype(bool))

    assert paridad.filas == len(df)
    assert paridad.aceptable, (
        f"la conversion cambio el modelo: desviacion {paridad.desviacion_maxima:.2e}"
    )


def test_ninguna_decision_cambia_de_lado():
    """
    Una desviación numérica chica es tolerable; que un paciente cruce el umbral por culpa
    de la conversión, no. Es lo único que se nota en producción.
    """
    df = _cohorte()
    modelo = baseline.entrenar(df)
    X = baseline.matriz(df).to_numpy(dtype=float)

    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "m.onnx"
        exportar.exportar(modelo, X.shape[1], ruta)
        paridad = exportar.verificar_paridad(modelo, ruta, X, df["muerte_30d"].to_numpy().astype(bool))

    for objetivo, cuantas in paridad.decisiones_cambiadas.items():
        assert cuantas == 0, f"{cuantas} decisiones cambian a sensibilidad {objetivo:.0%}"


def test_el_export_incluye_el_preprocesamiento():
    """
    Si sólo se exportara el clasificador, alimentarlo con datos SIN escalar daria
    probabilidades muy distintas. Se verifica pasando datos crudos: si el escalado viaja
    dentro del grafo, ONNX coincide con sklearn sobre esos mismos datos crudos.
    """
    df = _cohorte()
    modelo = baseline.entrenar(df)
    X = baseline.matriz(df).to_numpy(dtype=float)

    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "m.onnx"
        exportar.exportar(modelo, X.shape[1], ruta)
        p_onnx = exportar._probabilidades_onnx(ruta, X)

    p_sklearn = modelo.predict_proba(X)[:, 1]
    # Los datos crudos no estan centrados: si el escalado faltara, la diferencia seria enorme.
    assert np.max(np.abs(p_sklearn - p_onnx)) < 1e-5


def test_la_paridad_detecta_una_divergencia_inyectada():
    """Si el verificador no detecta una diferencia puesta a mano, no sirve de nada."""
    paridad = exportar.Paridad(filas=10, desviacion_maxima=1e-3)
    assert not paridad.aceptable


# =============================================================================
# El contrato que viaja con el archivo
# =============================================================================
def _meta(df):
    modelo = baseline.entrenar(df)
    X = baseline.matriz(df).to_numpy(dtype=float)
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "m.onnx"
        exportar.exportar(modelo, X.shape[1], ruta)
        paridad = exportar.verificar_paridad(modelo, ruta, X, df["muerte_30d"].to_numpy().astype(bool))
    # Se pasan puntajes fuera de fold reales: sin esto, `tasa_de_alertas_esperada`
    # queda en None y la prueba no ejercita el camino que importa.
    oof = baseline.evaluar_anidada(df, n_externo=3, n_interno=2).puntajes
    return exportar.metadatos(df, modelo, "muerte_30d", paridad, fuera_de_fold=oof)


def test_los_metadatos_congelan_el_orden_de_las_features():
    """
    ONNX recibe un tensor: las columnas viajan por posicion. Mandar la frecuencia cardiaca
    donde el modelo espera la temperatura no da error, da un numero.
    """
    meta = _meta(_cohorte())
    assert meta["features_en_orden"] == baseline.FEATURES
    assert len(meta["features_en_orden"]) == len(set(meta["features_en_orden"]))


def test_los_metadatos_no_publican_biomarcadores_como_entrada():
    meta = _meta(_cohorte())
    for prohibida in baseline.EXCLUIDAS_POR_NO_ESTAR_AL_PIE_DE_LA_CAMA:
        assert prohibida not in meta["features_en_orden"]
    assert prohibida in meta["features_excluidas"]["cuales"]


def test_los_metadatos_publican_la_curva_de_umbrales():
    """Sin la curva, quien despliega no tiene con que elegir el umbral."""
    meta = _meta(_cohorte())
    curva = meta["umbral"]["curva"]
    assert len(curva) == len(exportar.SENSIBILIDADES_PUBLICADAS)
    assert all("umbral" in p for p in curva)
    assert meta["umbral"]["elegir_es_decision_clinica"] is True


def test_el_umbral_publicado_da_la_sensibilidad_que_promete():
    """
    El error que llegó a producción (encontrado por SCRUM-69 el 19/10).

    Cada punto de la curva dice "con este umbral, el modelo detecta al menos esta
    sensibilidad". Hasta el 19/10 el umbral salía del percentil de TODOS los pacientes, y
    con él alertaba esa fracción de la cohorte —70 % de alertas a "sensibilidad 70 %"—
    mientras la tasa publicada al lado decía otra cosa. Todas las pruebas pasaban porque
    nadie verificaba la promesa del umbral, sólo que ONNX y sklearn coincidieran.

    Se verifica sobre el modelo final, que es el que publica el umbral: la sensibilidad
    alcanzada tiene que llegar al objetivo, y la tasa de alertas con ese umbral tiene que
    ser la in-sample que el mismo punto declara.
    """
    df = _cohorte()
    meta = _meta(df)
    modelo = baseline.entrenar(df)
    probas = modelo.predict_proba(baseline.matriz(df).to_numpy(dtype=float))[:, 1]
    y = df["muerte_30d"].to_numpy().astype(bool)

    for punto in meta["umbral"]["curva"]:
        alerta = probas >= punto["umbral"]
        sensibilidad = alerta[y].mean()
        assert sensibilidad >= punto["sensibilidad_objetivo"] - 1e-6, (
            f"el umbral {punto['umbral']} da sensibilidad {sensibilidad:.2f}, "
            f"no {punto['sensibilidad_objetivo']:.0%}"
        )
        assert abs(alerta.mean() - punto["tasa_de_alertas_in_sample_optimista"]) < 1e-3, (
            f"con el umbral publicado alerta el {alerta.mean():.1%}, pero el mismo punto "
            f"declara {punto['tasa_de_alertas_in_sample_optimista']:.1%}"
        )


def test_la_curva_distingue_la_tasa_esperada_de_la_in_sample():
    """
    La clave que importa es `tasa_de_alertas_esperada`, que sale de los puntajes fuera de
    fold. La in-sample se publica SOLO para mostrar cuanto optimismo tendria confiar en
    ella; si alguien dimensiona la carga de alertas con esa, la subestima.
    """
    meta = _meta(_cohorte())
    for punto in meta["umbral"]["curva"]:
        assert "tasa_de_alertas_esperada" in punto
        assert "tasa_de_alertas_in_sample_optimista" in punto
    assert "fuera de fold" in meta["umbral"]["usar_tasa_de_alertas_esperada"]

    # La esperada no puede ser optimista respecto de la in-sample: el modelo final vio a
    # estos pacientes, asi que su tasa in-sample es la cota inferior.
    for punto in meta["umbral"]["curva"]:
        esperada = punto["tasa_de_alertas_esperada"]
        in_sample = punto["tasa_de_alertas_in_sample_optimista"]
        if esperada is not None and in_sample is not None:
            assert esperada >= in_sample - 1e-9, (
                f"la tasa esperada ({esperada}) salio por debajo de la in-sample "
                f"({in_sample}): el sentido del optimismo esta invertido"
            )


def test_los_metadatos_declaran_que_la_reduccion_no_esta_demostrada():
    """
    El artefacto no puede viajar sin el caveat: si alguien lo despliega leyendo solo el
    JSON, tiene que enterarse de que la ventaja contra NEWS2 no esta probada.
    """
    meta = _meta(_cohorte())
    assert "no esta demostrada" in meta["advertencia"].lower()


def test_los_metadatos_son_json_serializable():
    """Se escriben a disco: un tipo de numpy suelto rompe el volcado sin aviso util."""
    meta = _meta(_cohorte())
    json.dumps(meta, ensure_ascii=False)


def test_el_pipeline_declarado_coincide_con_el_modelo_elegido():
    meta = _meta(_cohorte())
    assert meta["modelo"] == "regresion_logistica"
    assert "LogisticRegression" in meta["pipeline"]
    assert "StandardScaler" in meta["pipeline"]


def test_los_metadatos_traen_los_coeficientes_para_explicar():
    """
    SCRUM-66 se apoya en que el sidecar lleve con qué descomponer el logit. Sin esto la
    API no puede explicar nada: el grafo ONNX da la probabilidad, no de dónde salió.
    """
    df = _cohorte()
    meta = _meta(df)
    bloque = meta["explicabilidad"]

    assert bloque is not None
    assert bloque["exacta"] is True
    for clave in ("intercepto", "coeficientes", "escalado_media", "escalado_escala"):
        assert clave in bloque, clave
    assert list(bloque["coeficientes"]) == meta["features_en_orden"]


def test_sin_modelo_lineal_la_explicabilidad_es_nula_y_no_inventada():
    """
    Si la CV anidada pasara a elegir XGBoost, la descomposición exacta deja de existir.
    Tiene que aparecer `null`, no coeficientes de otro modelo: la API lo detecta y
    responde sin explicación en vez de mostrar una falsa.
    """
    df = _cohorte()
    arbol = baseline.entrenar(df, modelo="xgb_1")
    assert exportar.explicabilidad(arbol, baseline.FEATURES) is None


PRUEBAS = [
    test_onnx_y_sklearn_dan_la_misma_probabilidad,
    test_ninguna_decision_cambia_de_lado,
    test_el_export_incluye_el_preprocesamiento,
    test_la_paridad_detecta_una_divergencia_inyectada,
    test_los_metadatos_congelan_el_orden_de_las_features,
    test_los_metadatos_no_publican_biomarcadores_como_entrada,
    test_los_metadatos_publican_la_curva_de_umbrales,
    test_el_umbral_publicado_da_la_sensibilidad_que_promete,
    test_la_curva_distingue_la_tasa_esperada_de_la_in_sample,
    test_los_metadatos_declaran_que_la_reduccion_no_esta_demostrada,
    test_los_metadatos_son_json_serializable,
    test_el_pipeline_declarado_coincide_con_el_modelo_elegido,
    test_los_metadatos_traen_los_coeficientes_para_explicar,
    test_sin_modelo_lineal_la_explicabilidad_es_nula_y_no_inventada,
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
    print(f"OK: {len(PRUEBAS)} pruebas de la exportacion a ONNX")
