"""
Pruebas de la API de inferencia (SCRUM-62).

Lo que se verifica es que **el servicio sirva el modelo que se evaluó, con el punto de
operación declarado**. Los dos modos de falla que importan no se ven desde afuera:

  - Columnas corridas: si la API arma el vector en otro orden que el del entrenamiento,
    sigue devolviendo probabilidades plausibles — de otro paciente.
  - Umbral implícito: si la alerta viaja sin su punto de operación, quien integre el
    servicio no tiene forma de saber cuántas alertas por turno va a recibir.

    cd ml_engine && .venv/Scripts/python -m pytest tests/test_api.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && .venv/Scripts/python tests/test_api.py
"""
import json
import shutil
import sys
import tempfile
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src import rangos  # noqa: E402
from src.api import main, modelo as cargador  # noqa: E402

MODELOS = Path(__file__).resolve().parents[1] / "models"

OBSERVACION = {
    "frecuencia_respiratoria": 22,
    "spo2": 94,
    "temperatura": 37.8,
    "presion_sistolica": 104,
    "frecuencia_cardiaca": 110,
    "confusion": 0,
    "edad": 74,
}


def _cliente() -> TestClient:
    return TestClient(main.app)


def _copia_de_los_modelos(destino: Path) -> Path:
    for nombre in (cargador.NOMBRE_ONNX, cargador.NOMBRE_METADATOS):
        shutil.copy(MODELOS / nombre, destino / nombre)
    return destino


# -- contrato con la tubería ---------------------------------------------------------


def test_los_rangos_de_la_api_son_los_de_la_tuberia():
    """
    La API valida con el mismo diccionario que la ingesta.

    Si estos dos se separan, la base rechaza mediciones que la API acepta y el NEWS2
    histórico y el de producción pasan a calcularse sobre universos distintos.
    """
    from src.validation import esquemas

    assert esquemas.RANGOS_PLAUSIBLES is rangos.RANGOS_PLAUSIBLES


def test_la_api_y_el_exportador_leen_igual_la_salida_onnx():
    """
    La extracción de la probabilidad está duplicada a propósito (el contenedor de
    producción no lleva pandas). Esta prueba es lo que mantiene honesta la copia.
    """
    from src.models import exportar

    m = cargador.Modelo(MODELOS)
    X = np.array(
        [[float(OBSERVACION[f]) for f in m.features],
         [20.0, 97.0, 36.5, 130.0, 72.0, 0.0, 40.0]],
        dtype=float,
    )

    por_la_api = cargador._probabilidades(m.sesion, X)
    por_el_exportador = exportar._probabilidades_onnx(m.ruta_onnx, X)

    assert np.allclose(por_la_api, por_el_exportador, atol=1e-12)


def test_el_vector_se_arma_en_el_orden_del_sidecar_y_no_en_el_del_json():
    """Mandar las mismas claves en otro orden tiene que dar exactamente lo mismo."""
    m = cargador.Modelo(MODELOS)
    al_derecho = m.predecir(dict(OBSERVACION), 0.70)
    al_reves = m.predecir(dict(reversed(list(OBSERVACION.items()))), 0.70)
    assert al_derecho.probabilidad == al_reves.probabilidad


# -- verificaciones de arranque ------------------------------------------------------


def test_se_niega_a_cargar_si_el_grafo_y_el_sidecar_no_coinciden():
    with tempfile.TemporaryDirectory() as tmp:
        directorio = _copia_de_los_modelos(Path(tmp))
        ruta = directorio / cargador.NOMBRE_METADATOS
        meta = json.loads(ruta.read_text(encoding="utf-8"))
        meta["features_en_orden"] = meta["features_en_orden"] + ["lactato"]
        ruta.write_text(json.dumps(meta), encoding="utf-8")

        try:
            cargador.Modelo(directorio)
        except cargador.ContratoRoto as exc:
            assert "columnas" in str(exc)
        else:
            raise AssertionError("cargo un sidecar que declara una feature de mas")


def test_se_niega_a_servir_un_modelo_cuya_paridad_fallo():
    with tempfile.TemporaryDirectory() as tmp:
        directorio = _copia_de_los_modelos(Path(tmp))
        ruta = directorio / cargador.NOMBRE_METADATOS
        meta = json.loads(ruta.read_text(encoding="utf-8"))
        meta["paridad_onnx_vs_sklearn"]["aceptable"] = False
        ruta.write_text(json.dumps(meta), encoding="utf-8")

        try:
            cargador.Modelo(directorio)
        except cargador.ContratoRoto as exc:
            assert "paridad" in str(exc)
        else:
            raise AssertionError("sirvio un modelo distinto del que se evaluo")


def test_avisa_que_el_artefacto_no_esta_en_vez_de_fallar_raro():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            cargador.Modelo(Path(tmp))
        except cargador.ContratoRoto as exc:
            assert "exportar" in str(exc)
        else:
            raise AssertionError("no aviso que falta el artefacto")


# -- punto de operación ---------------------------------------------------------------


def test_cada_respuesta_trae_su_punto_de_operacion():
    with _cliente() as c:
        r = c.post("/prediccion", json={"observacion": OBSERVACION})
        assert r.status_code == 200, r.text
        punto = r.json()["punto_de_operacion"]
        assert punto["sensibilidad_objetivo"] == main.SENSIBILIDAD_POR_DEFECTO
        assert punto["umbral"] > 0
        assert punto["tasa_de_alertas_esperada"] is not None


def test_distingue_el_umbral_elegido_del_que_quedo_por_defecto():
    with _cliente() as c:
        omitido = c.post("/prediccion", json={"observacion": OBSERVACION}).json()
        elegido = c.post(
            "/prediccion",
            json={"observacion": OBSERVACION, "sensibilidad_objetivo": 0.80},
        ).json()

    assert omitido["punto_de_operacion"]["elegido_por"] == "valor_por_defecto"
    assert elegido["punto_de_operacion"]["elegido_por"] == "cliente"


def test_una_sensibilidad_mas_alta_nunca_baja_el_umbral():
    """Más sensibilidad es menos umbral y más alertas. Si se invirtiera, la curva estaría mal leída."""
    m = cargador.Modelo(MODELOS)
    umbrales = [m.punto(s).umbral for s in m.sensibilidades_disponibles]
    assert umbrales == sorted(umbrales, reverse=True)


def test_rechaza_una_sensibilidad_que_no_esta_calibrada():
    """Interpolar daría un umbral que nunca se midió y una tasa de alertas inventada."""
    with _cliente() as c:
        r = c.post(
            "/prediccion",
            json={"observacion": OBSERVACION, "sensibilidad_objetivo": 0.65},
        )
    assert r.status_code == 422
    assert "calibrada" in r.json()["detail"]


# -- validación de entrada -------------------------------------------------------------


def test_rechaza_una_medicion_fisiologicamente_imposible():
    """
    Una SpO2 de 10 % es un error de registro, no un paciente grave. Si entrara, el modelo
    devolvería una probabilidad alta con total seguridad.
    """
    with _cliente() as c:
        r = c.post(
            "/prediccion",
            json={"observacion": {**OBSERVACION, "spo2": 10}},
        )
    assert r.status_code == 422


def test_rechaza_una_observacion_incompleta():
    incompleta = {k: v for k, v in OBSERVACION.items() if k != "temperatura"}
    with _cliente() as c:
        assert c.post("/prediccion", json={"observacion": incompleta}).status_code == 422


# -- lo que el servicio promete ---------------------------------------------------------


def test_la_salud_responde_200_y_dice_si_el_modelo_esta():
    with _cliente() as c:
        r = c.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"
    assert r.json()["modelo_cargado"] is True


def test_la_advertencia_sobre_la_evidencia_viaja_en_cada_prediccion():
    """
    La reducción de alertas contra NEWS2 no está demostrada. Quien integre el servicio
    tiene que leerlo sin ir a buscarlo.
    """
    with _cliente() as c:
        cuerpo = c.post("/prediccion", json={"observacion": OBSERVACION}).json()
    assert cuerpo["es_estimacion"] is True
    assert "NO esta demostrada" in cuerpo["advertencia"]


def test_la_api_no_calcula_news2():
    """
    NEWS2 se calcula en la base. Un endpoint acá invitaría a depender de este servicio
    para la escala, y rompería la degradación elegante de SCRUM-65.
    """
    with _cliente() as c:
        rutas = c.get("/openapi.json").json()["paths"]
    assert not [r for r in rutas if "news" in r.lower()]


def test_el_modelo_expone_su_sidecar_completo():
    with _cliente() as c:
        meta = c.get("/modelo").json()
    assert meta["features_en_orden"]
    assert meta["entrenado_sobre"]["cohorte"]
    assert meta["umbral"]["curva"]


PRUEBAS = [
    test_los_rangos_de_la_api_son_los_de_la_tuberia,
    test_la_api_y_el_exportador_leen_igual_la_salida_onnx,
    test_el_vector_se_arma_en_el_orden_del_sidecar_y_no_en_el_del_json,
    test_se_niega_a_cargar_si_el_grafo_y_el_sidecar_no_coinciden,
    test_se_niega_a_servir_un_modelo_cuya_paridad_fallo,
    test_avisa_que_el_artefacto_no_esta_en_vez_de_fallar_raro,
    test_cada_respuesta_trae_su_punto_de_operacion,
    test_distingue_el_umbral_elegido_del_que_quedo_por_defecto,
    test_una_sensibilidad_mas_alta_nunca_baja_el_umbral,
    test_rechaza_una_sensibilidad_que_no_esta_calibrada,
    test_rechaza_una_medicion_fisiologicamente_imposible,
    test_rechaza_una_observacion_incompleta,
    test_la_salud_responde_200_y_dice_si_el_modelo_esta,
    test_la_advertencia_sobre_la_evidencia_viaja_en_cada_prediccion,
    test_la_api_no_calcula_news2,
    test_el_modelo_expone_su_sidecar_completo,
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
    print(f"OK: {len(PRUEBAS)} pruebas de la API de inferencia")
