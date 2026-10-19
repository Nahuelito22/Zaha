"""
Pruebas del exportador a FHIR R4 (SCRUM-71).

Lo central es que el Bundle **valide contra el esquema JSON oficial de FHIR R4** publicado
por HL7. Y para que esa validación signifique algo, hay una prueba que rompe un recurso a
propósito y exige que el validador lo rechace.

    cd ml_engine && .venv/Scripts/python -m pytest tests/test_fhir.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && .venv/Scripts/python tests/test_fhir.py
"""
import copy
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jsonschema  # noqa: E402

from src.interoperabilidad import fhir  # noqa: E402

# Datos ficticios, los mismos de la sala de desarrollo (cama CM-07).
PACIENTE = {
    "id": "559ca53c-f847-433f-9bc3-34fcc33eec64",
    "mrn": "10052840",
    "first_name": "Ramón Osvaldo",
    "last_name": "Páez",
    "date_of_birth": "1937-03-02",
    "gender": "male",
    "active": True,
}


def _toma(**cambios):
    t = {
        "id": "8b0d1c7e-1111-4a2b-9c3d-000000000001",
        "recorded_at": "2026-09-14T20:53:00+00:00",
        "created_at": "2026-09-14T20:55:12.481+00:00",
        "respiratory_rate": 80,
        "oxygen_saturation": 90,
        "supplemental_oxygen": False,
        "temperature": 35.0,
        "systolic_bp": 280,
        "heart_rate": 80,
        "consciousness_level": "V",
        "news2_score": 15,
        "risk_level": "Alto",
        "single_red_flag": True,
        "amends_id": None,
        "amendment_reason": None,
        "superseded_by": None,
    }
    t.update(cambios)
    return t


PREDICCION = {
    "probabilidad": 0.994137,
    "alerta": True,
    "punto_de_operacion": {"sensibilidad_objetivo": 0.7, "umbral": 0.517434,
                           "tasa_de_alertas_esperada": 0.3038},
    "advertencia": "La reduccion de alertas contra NEWS2 NO esta demostrada con esta cohorte.",
}


@lru_cache(maxsize=1)
def _validador():
    return jsonschema.Draft6Validator(fhir.esquema_oficial())


def _errores(recurso):
    return sorted(_validador().iter_errors(recurso), key=lambda e: list(e.path))


def _recursos(b, tipo=None):
    return [e["resource"] for e in b["entry"] if tipo is None or e["resource"]["resourceType"] == tipo]


# =============================================================================
# Valida contra el esquema oficial
# =============================================================================
def test_el_bundle_valida_contra_el_esquema_oficial_de_fhir_r4():
    b = fhir.bundle(PACIENTE, [_toma()], PREDICCION)
    errores = _errores(b)
    assert not errores, "\n".join(f"{list(e.path)}: {e.message[:200]}" for e in errores[:5])


def test_el_validador_rechaza_un_recurso_roto():
    """Si el validador aceptara cualquier cosa, la prueba de arriba no probaría nada."""
    b = fhir.bundle(PACIENTE, [_toma()])
    roto = copy.deepcopy(b)
    obs = _recursos(roto, "Observation")[0]
    obs["status"] = "inventado"           # no está en el value set requerido
    assert _errores(roto), "el esquema aceptó un status que no existe"

    roto = copy.deepcopy(b)
    _recursos(roto, "Patient")[0]["gender"] = "masculino"
    assert _errores(roto), "el esquema aceptó un genero fuera del value set"


def test_valida_con_varias_tomas_y_una_enmienda():
    tomas = [
        _toma(),
        _toma(id="8b0d1c7e-1111-4a2b-9c3d-000000000002", recorded_at="2026-09-15T08:00:00+00:00",
              respiratory_rate=18, oxygen_saturation=97, temperature=36.8, systolic_bp=125,
              consciousness_level="A", news2_score=0, risk_level="Bajo", single_red_flag=False,
              amends_id="8b0d1c7e-1111-4a2b-9c3d-0000000000ff",
              amendment_reason="Se cargó la frecuencia en la cama equivocada"),
    ]
    b = fhir.bundle(PACIENTE, tomas, PREDICCION)
    assert not _errores(b)


# =============================================================================
# El contenido clínico
# =============================================================================
def test_los_vitales_llevan_su_codigo_loinc_y_su_unidad_ucum():
    b = fhir.bundle(PACIENTE, [_toma()])
    por_codigo = {o["code"]["coding"][0]["code"]: o for o in _recursos(b, "Observation")}
    for columna, loinc, _, unidad, perfil in fhir.VITALES:
        o = por_codigo[loinc]
        assert o["valueQuantity"]["code"] == unidad and o["valueQuantity"]["system"] == fhir.UCUM
        assert o["meta"]["profile"] == [fhir.PERFIL + perfil]
        assert o["category"][0]["coding"][0]["code"] == "vital-signs"
    bp = por_codigo["85354-9"]
    sistolica, diastolica = bp["component"]
    assert sistolica["valueQuantity"]["value"] == 280
    assert "dataAbsentReason" in diastolica, "la diastolica no se registra: va con su motivo"


def test_la_c_de_acvpu_no_se_pierde():
    """La confusión nueva puntúa 3 en NEWS2; exportarla como 'alerta' sería un error grave."""
    b = fhir.bundle(PACIENTE, [_toma(consciousness_level="C")])
    cons = next(o for o in _recursos(b, "Observation") if o["code"]["coding"][0]["code"] == "67775-7")
    valor = cons["valueCodeableConcept"]["coding"][0]
    assert valor == {"system": fhir.SISTEMA_ACVPU, "code": "C", "display": "Confusión nueva"}


def test_news2_es_final_y_el_modelo_es_preliminar_con_su_advertencia():
    b = fhir.bundle(PACIENTE, [_toma()], PREDICCION)
    news2, modelo = _recursos(b, "RiskAssessment")
    assert news2["status"] == "final"
    assert news2["prediction"][0]["qualitativeRisk"]["text"] == "Alto"
    assert "rojo aislado" in news2["prediction"][0]["rationale"]
    assert modelo["status"] == "preliminary"
    assert modelo["prediction"][0]["probabilityDecimal"] == 0.994137
    assert "NO esta demostrada" in modelo["note"][0]["text"]
    assert "no es NEWS2" in modelo["method"]["coding"][0]["display"]


def test_el_puntaje_news2_deriva_de_sus_observaciones():
    b = fhir.bundle(PACIENTE, [_toma()])
    puntaje = next(o for o in _recursos(b, "Observation")
                   if o["code"]["coding"][0]["code"] == "news2-score")
    assert puntaje["valueInteger"] == 15
    assert len(puntaje["derivedFrom"]) == 7


def test_todas_las_referencias_resuelven_dentro_del_bundle():
    b = fhir.bundle(PACIENTE, [_toma()], PREDICCION)
    urls = {e["fullUrl"] for e in b["entry"]}

    def refs(x):
        if isinstance(x, dict):
            if "reference" in x:
                yield x["reference"]
            for v in x.values():
                yield from refs(v)
        elif isinstance(x, list):
            for v in x:
                yield from refs(v)

    sueltas = [r for r in refs(b) if r not in urls]
    assert not sueltas, f"referencias que no apuntan a nada del Bundle: {sueltas[:3]}"


def test_una_enmienda_sale_como_corrected_con_su_motivo():
    t = _toma(amends_id="x", amendment_reason="Error de tipeo en la saturación")
    b = fhir.bundle(PACIENTE, [t])
    for o in _recursos(b, "Observation"):
        assert o["status"] == "corrected"
        assert "Error de tipeo" in o["note"][0]["text"]


def test_no_se_exporta_una_version_reemplazada():
    try:
        fhir.bundle(PACIENTE, [_toma(superseded_by="otra")])
    except ValueError as e:
        assert "vigente" in str(e)
    else:
        raise AssertionError("exportó una toma ya enmendada como si fuera el valor vigente")


def test_los_identificadores_son_estables():
    """Reenviar la misma toma no tiene que duplicarla en el sistema que la recibe."""
    a = fhir.bundle(PACIENTE, [_toma()], PREDICCION)
    b = fhir.bundle(PACIENTE, [_toma()], PREDICCION)
    assert [e["fullUrl"] for e in a["entry"]] == [e["fullUrl"] for e in b["entry"]]


if __name__ == "__main__":
    pruebas = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    fallas = []
    for p in pruebas:
        try:
            p()
        except AssertionError as e:
            fallas.append(f"  - {p.__name__}: {e}")
    if fallas:
        print("FALLAS:\n" + "\n".join(fallas))
        sys.exit(1)
    print(f"OK: {len(pruebas)} pruebas del exportador FHIR")
