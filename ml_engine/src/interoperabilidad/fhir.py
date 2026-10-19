"""
Exportador del esquema propio a HL7 FHIR R4 (SCRUM-71, cierra la HU-05 / SCRUM-70).

QUÉ HACE
Arma el Bundle FHIR R4 de un paciente a partir de las filas de la base, tal como las
devuelve Supabase: `Patient`, una `Observation` por signo vital, el puntaje NEWS2 y dos
`RiskAssessment` —la escala y, si la hay, la estimación del modelo—. No toca la base ni
producción: recibe diccionarios y devuelve JSON. Las pruebas validan el resultado contra el
esquema JSON oficial de FHIR R4 publicado por HL7 (`fhir.schema.json.zip`, al lado de este
archivo).

EL MAPEO ESTÁ EXPLICADO EN `Plan/epica_06_regulatorio/03_mapeo_fhir.md`. Las decisiones que
más pesan, para quien lea sólo el código:

- **Los códigos LOINC están verificados, no recordados.** Los cinco signos vitales salen del
  perfil Vital Signs de FHIR R4; el oxígeno suplementario y la consciencia, del servidor de
  terminología oficial (`tx.fhir.org`, LOINC 2.82).
- **NEWS2 no tiene código LOINC**, y la "C" de ACVPU (confusión nueva) no existe en la escala
  AVPU que codifica LOINC. Los dos van en un sistema de códigos propio y declarado como tal.
  Inventar un código estándar sería peor que admitir que no existe.
- **La escala y el modelo no se confunden tampoco acá.** NEWS2 es un `RiskAssessment` con
  estado `final`, porque es determinístico. La estimación del modelo es `preliminary` y
  lleva su advertencia en `note`: es lo mismo que la app separa con violeta y "no es NEWS2".
- **Se exporta el valor vigente.** Una toma enmendada sale como `corrected`, con el motivo
  en `note`. El historial completo de versiones (`Provenance`) queda fuera de este alcance.
"""

from __future__ import annotations

import json
import uuid
import zipfile
from pathlib import Path
from typing import Any, Iterable

# Sistema de códigos propio, para lo que no tiene código estándar. Es una URI que identifica
# al proyecto; FHIR no exige que resuelva a una página.
SISTEMA_ZAHA = "https://zahasalud.com.ar/fhir/CodeSystem/zaha"
SISTEMA_ACVPU = "https://zahasalud.com.ar/fhir/CodeSystem/acvpu"
SISTEMA_MRN = "https://zahasalud.com.ar/fhir/NamingSystem/historia-clinica"

LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
CATEGORIA = "http://terminology.hl7.org/CodeSystem/observation-category"
AUSENCIA = "http://terminology.hl7.org/CodeSystem/data-absent-reason"
PERFIL = "http://hl7.org/fhir/StructureDefinition/"

# Espacio de nombres para derivar identificadores estables: la misma toma produce siempre
# la misma Observation, así que un reenvío no la duplica en el sistema que la recibe.
_NS = uuid.UUID("6f1c2a52-5b0e-4f7c-9f0a-7a1d2c3e4b5a")

# (columna, LOINC, nombre, unidad UCUM, perfil de FHIR R4). Fuente: perfil Vital Signs de
# FHIR R4, https://hl7.org/fhir/R4/observation-vitalsigns.html
VITALES = [
    ("respiratory_rate", "9279-1", "Respiratory rate", "/min", "resprate"),
    ("heart_rate", "8867-4", "Heart rate", "/min", "heartrate"),
    ("oxygen_saturation", "2708-6", "Oxygen saturation in Arterial blood", "%", "oxygensat"),
    ("temperature", "8310-5", "Body temperature", "Cel", "bodytemp"),
]

ACVPU = {
    "A": "Alerta",
    "C": "Confusión nueva",
    "V": "Responde a la voz",
    "P": "Responde al dolor",
    "U": "No responde",
}


def _id(*partes: Any) -> str:
    return str(uuid.uuid5(_NS, "/".join(str(p) for p in partes)))


def _urn(i: str) -> str:
    return f"urn:uuid:{i}"


def _instante(valor: Any) -> str:
    """Las fechas de Supabase llegan como texto ISO; FHIR exige zona horaria."""
    s = str(valor).replace(" ", "T")
    return s if ("+" in s[10:] or s.endswith("Z") or "-" in s[19:]) else s + "Z"


def _categoria(codigo: str) -> list[dict]:
    return [{"coding": [{"system": CATEGORIA, "code": codigo}]}]


def paciente(p: dict) -> dict:
    return {
        "resourceType": "Patient",
        "id": str(p["id"]),
        "identifier": [{"system": SISTEMA_MRN, "value": p["mrn"]}],
        "active": bool(p.get("active", True)),
        "name": [{"family": p["last_name"], "given": [p["first_name"]]}],
        # El esquema propio usa los mismos cuatro valores que FHIR: male, female, other, unknown.
        "gender": p.get("gender", "unknown"),
        "birthDate": str(p["date_of_birth"])[:10],
    }


def _observacion(toma: dict, sufijo: str, paciente_ref: str, **cuerpo) -> dict:
    estado = "corrected" if toma.get("amends_id") else "final"
    obs = {
        "resourceType": "Observation",
        "id": _id(toma["id"], sufijo),
        "status": estado,
        "subject": {"reference": paciente_ref},
        "effectiveDateTime": _instante(toma["recorded_at"]),
        **cuerpo,
    }
    if toma.get("created_at"):
        obs["issued"] = _instante(toma["created_at"])
    if estado == "corrected":
        obs["note"] = [{"text": f"Enmienda: {toma.get('amendment_reason', '')}".strip()}]
    return obs


def observaciones(toma: dict, paciente_ref: str) -> list[dict]:
    """Las observaciones de UNA toma: los vitales, la presión, el oxígeno y la consciencia."""
    salida = []
    for columna, loinc, nombre, unidad, perfil in VITALES:
        salida.append(_observacion(
            toma, columna, paciente_ref,
            meta={"profile": [PERFIL + perfil]},
            category=_categoria("vital-signs"),
            code={"coding": [{"system": LOINC, "code": loinc, "display": nombre}], "text": nombre},
            valueQuantity={"value": float(toma[columna]) if columna == "temperature"
                           else int(toma[columna]),
                           "unit": unidad, "system": UCUM, "code": unidad},
        ))

    # El perfil de presión exige las dos componentes. La diastólica no se registra —NEWS2
    # no la usa—, así que va con su motivo de ausencia en vez de omitirse o inventarse.
    salida.append(_observacion(
        toma, "blood_pressure", paciente_ref,
        meta={"profile": [PERFIL + "bp"]},
        category=_categoria("vital-signs"),
        code={"coding": [{"system": LOINC, "code": "85354-9",
                          "display": "Blood pressure panel with all children optional"}],
              "text": "Presión arterial"},
        component=[
            {"code": {"coding": [{"system": LOINC, "code": "8480-6",
                                  "display": "Systolic blood pressure"}]},
             "valueQuantity": {"value": int(toma["systolic_bp"]), "unit": "mm[Hg]",
                               "system": UCUM, "code": "mm[Hg]"}},
            {"code": {"coding": [{"system": LOINC, "code": "8462-4",
                                  "display": "Diastolic blood pressure"}]},
             "dataAbsentReason": {"coding": [{"system": AUSENCIA, "code": "not-performed"}],
                                  "text": "No se registra: NEWS2 no la usa"}},
        ],
    ))

    # LOINC 88658-0, verificado en tx.fhir.org (LOINC 2.82).
    salida.append(_observacion(
        toma, "supplemental_oxygen", paciente_ref,
        category=_categoria("vital-signs"),
        code={"coding": [{"system": LOINC, "code": "88658-0",
                          "display": "Use of supplemental oxygen"}],
              "text": "Oxígeno suplementario"},
        valueBoolean=bool(toma["supplemental_oxygen"]),
    ))

    # LOINC 67775-7 "Level of responsiveness" codifica AVPU. La C de ACVPU no está en esa
    # escala, así que el VALOR va en el sistema propio, con su texto legible.
    nivel = toma.get("consciousness_level", "A")
    salida.append(_observacion(
        toma, "consciousness_level", paciente_ref,
        category=_categoria("exam"),
        code={"coding": [{"system": LOINC, "code": "67775-7",
                          "display": "Level of responsiveness"}],
              "text": "Nivel de consciencia (ACVPU)"},
        valueCodeableConcept={"coding": [{"system": SISTEMA_ACVPU, "code": nivel,
                                          "display": ACVPU[nivel]}],
                              "text": ACVPU[nivel]},
    ))
    return salida


def puntaje_news2(toma: dict, paciente_ref: str, base: list[dict]) -> dict:
    """El total de NEWS2 como Observation propia: no tiene código LOINC."""
    return _observacion(
        toma, "news2_score", paciente_ref,
        category=_categoria("survey"),
        code={"coding": [{"system": SISTEMA_ZAHA, "code": "news2-score",
                          "display": "Puntaje NEWS2 (RCP 2017)"}],
              "text": "Puntaje NEWS2"},
        valueInteger=int(toma["news2_score"]),
        derivedFrom=[{"reference": _urn(o["id"])} for o in base],
    )


def riesgo_news2(toma: dict, paciente_ref: str, puntaje: dict) -> dict:
    rojo = bool(toma.get("single_red_flag"))
    recurso = {
        "resourceType": "RiskAssessment",
        "id": _id(toma["id"], "riesgo_news2"),
        # Determinístico: el mismo puntaje da siempre el mismo nivel.
        "status": "final",
        "subject": {"reference": paciente_ref},
        "occurrenceDateTime": _instante(toma["recorded_at"]),
        "method": {"coding": [{"system": SISTEMA_ZAHA, "code": "news2",
                               "display": "National Early Warning Score 2"}],
                   "text": "NEWS2, calculado por la base de datos"},
        "basis": [{"reference": _urn(puntaje["id"])}],
        "prediction": [{
            "outcome": {"text": "Deterioro clínico"},
            "qualitativeRisk": {"coding": [{"system": SISTEMA_ZAHA,
                                            "code": "news2-" + _slug(toma["risk_level"]),
                                            "display": toma["risk_level"]}],
                                "text": toma["risk_level"]},
        }],
    }
    if rojo:
        recurso["prediction"][0]["rationale"] = (
            "Un parámetro puntúa 3 (rojo aislado): requiere evaluación aunque el total sea bajo."
        )
    return recurso


def riesgo_modelo(prediccion: dict, toma: dict, paciente_ref: str, base: list[dict]) -> dict:
    """La estimación del modelo. Es `preliminary`: no es la escala, y lo declara."""
    punto = prediccion["punto_de_operacion"]
    return {
        "resourceType": "RiskAssessment",
        "id": _id(toma["id"], "riesgo_modelo"),
        "status": "preliminary",
        "subject": {"reference": paciente_ref},
        "occurrenceDateTime": _instante(toma["recorded_at"]),
        "method": {"coding": [{"system": SISTEMA_ZAHA, "code": "modelo-zaha",
                               "display": "Estimación del modelo de Zaha (no es NEWS2)"}],
                   "text": "Regresión logística sobre los parámetros de cabecera"},
        "basis": [{"reference": _urn(o["id"])} for o in base],
        "prediction": [{
            "outcome": {"text": "Muerte a 30 días"},
            "probabilityDecimal": round(float(prediccion["probabilidad"]), 6),
            "qualitativeRisk": {"coding": [{"system": SISTEMA_ZAHA,
                                            "code": "alerta" if prediccion["alerta"] else "sin-alerta",
                                            "display": "Alerta" if prediccion["alerta"] else "Sin alerta"}]},
            "rationale": (f"Umbral {punto['umbral']} para una sensibilidad objetivo de "
                          f"{punto['sensibilidad_objetivo']:.0%}."),
        }],
        "note": [{"text": prediccion["advertencia"]}],
    }


def _slug(texto: str) -> str:
    return texto.lower().replace(" ", "-")


def bundle(p: dict, tomas: Iterable[dict], prediccion: dict | None = None) -> dict:
    """
    El Bundle de un paciente. `tomas` son las filas VIGENTES de `vital_records`
    (`superseded_by IS NULL`); `prediccion`, si se pasa, es la respuesta de la API para la
    toma más reciente.
    """
    pac = paciente(p)
    ref = _urn(pac["id"])
    recursos: list[dict] = [pac]

    tomas = sorted(tomas, key=lambda t: str(t["recorded_at"]))
    for toma in tomas:
        if toma.get("superseded_by"):
            raise ValueError(
                f"la toma {toma['id']} fue enmendada: se exporta la versión vigente, no esta"
            )
        base = observaciones(toma, ref)
        puntaje = puntaje_news2(toma, ref, base)
        recursos += base + [puntaje, riesgo_news2(toma, ref, puntaje)]

    if prediccion is not None and tomas:
        ultima = tomas[-1]
        recursos.append(riesgo_modelo(prediccion, ultima, ref, observaciones(ultima, ref)))

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"fullUrl": _urn(r["id"]), "resource": r} for r in recursos],
    }


def esquema_oficial() -> dict:
    """El esquema JSON de FHIR R4 publicado por HL7 (hl7.org/fhir/R4/fhir.schema.json.zip)."""
    ruta = Path(__file__).with_name("fhir.schema.json.zip")
    with zipfile.ZipFile(ruta) as z:
        return json.loads(z.read("fhir.schema.json"))
