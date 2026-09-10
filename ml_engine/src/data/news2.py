"""
Motor NEWS2 en Python — espejo del motor de PostgreSQL.

POR QUÉ EXISTE UN SEGUNDO MOTOR
En producción NEWS2 lo calcula la base de datos y nadie más (ADR-001): el score de
un paciente no puede depender del dispositivo que lo cargó. Pero la tubería de datos
históricos no puede llamar a la base — son cientos de miles de filas de un dataset
que nunca se va a insertar en `vital_records`, que es append-only y de pacientes reales
del hospital.

Así que hay dos motores, y el riesgo obvio es que diverjan. Por eso:

1. Los umbrales de acá son una transcripción literal de
   `supabase/migrations/20260521000100_news2_engine.sql`. Si uno cambia, cambian los dos.
2. `ml_engine/tests/test_news2.py` corre **los mismos 21 casos clínicos** que
   `supabase/tests/news2_cases.sql`. Si los dos motores no dan idéntico, el test falla.

La fuente es el estándar RCP 2017. Ningún umbral de este archivo es una decisión nuestra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ACVPU = Literal["A", "C", "V", "P", "U"]
NivelRiesgo = Literal["Bajo", "Medio Bajo", "Medio", "Alto"]


def puntaje_frecuencia_respiratoria(rr: float) -> int:
    if rr <= 8:
        return 3
    if rr <= 11:
        return 1
    if rr <= 20:
        return 0
    if rr <= 24:
        return 2
    return 3


def puntaje_spo2(spo2: float, escala: int, con_oxigeno: bool) -> int:
    """
    La escala es una PRESCRIPCIÓN médica, no se infiere del oxígeno suplementario.

    Escala 2 es el paciente con insuficiencia respiratoria hipercápnica, cuyo objetivo
    prescrito es 88-92 %. Para él, un 90 % respirando aire está en objetivo y puntúa 0,
    mientras que un 98 % con oxígeno puesto es hiperoxia y puntúa 3. Al revés de lo que
    diría la intuición.
    """
    if escala == 1:
        if spo2 <= 91:
            return 3
        if spo2 <= 93:
            return 2
        if spo2 <= 95:
            return 1
        return 0

    # Escala 2
    if spo2 <= 83:
        return 3
    if spo2 <= 85:
        return 2
    if spo2 <= 87:
        return 1
    if spo2 <= 92:
        return 0
    if not con_oxigeno:
        return 0  # >= 93 respirando aire ambiente: no es hiperoxia iatrogénica
    if spo2 <= 94:
        return 1
    if spo2 <= 96:
        return 2
    return 3


def puntaje_oxigeno_suplementario(con_oxigeno: bool) -> int:
    return 2 if con_oxigeno else 0


def puntaje_temperatura(temp: float) -> int:
    if temp <= 35.0:
        return 3
    if temp <= 36.0:
        return 1
    if temp <= 38.0:
        return 0
    if temp <= 39.0:
        return 1
    return 2


def puntaje_presion_sistolica(tas: float) -> int:
    if tas <= 90:
        return 3
    if tas <= 100:
        return 2
    if tas <= 110:
        return 1
    if tas <= 219:
        return 0
    return 3


def puntaje_frecuencia_cardiaca(fc: float) -> int:
    if fc <= 40:
        return 3
    if fc <= 50:
        return 1
    if fc <= 90:
        return 0
    if fc <= 110:
        return 1
    if fc <= 130:
        return 2
    return 3


def puntaje_consciencia(acvpu: str) -> int:
    """A = Alerta (0). Todo lo demás —C, V, P, U— puntúa 3."""
    return 0 if acvpu == "A" else 3


def nivel_riesgo(score: int, rojo_aislado: bool) -> NivelRiesgo:
    """
    El orden importa: un score >= 5 ya es Medio o Alto aunque tenga un parámetro en
    rojo, así que el rojo aislado se evalúa último. Evaluarlo antes sobre-escalaba
    pacientes, que es el bug que documentan los casos de regresión del SQL.
    """
    if score >= 7:
        return "Alto"
    if score >= 5:
        return "Medio"
    if rojo_aislado:
        return "Medio Bajo"
    return "Bajo"


@dataclass(frozen=True)
class ResultadoNEWS2:
    score: int
    riesgo: NivelRiesgo
    rojo_aislado: bool
    sub: dict[str, int]
    imputado: bool
    puntos_imputados: int
    """Cuántos puntos NO se pudieron evaluar por falta de datos. Ver ADR-007."""


def calcular(
    *,
    frecuencia_respiratoria: float,
    spo2: float,
    temperatura: float,
    presion_sistolica: float,
    frecuencia_cardiaca: float,
    consciencia: ACVPU | None = None,
    oxigeno_suplementario: bool | None = None,
    escala_spo2: int = 1,
) -> ResultadoNEWS2:
    """
    NEWS2 completo. Los 5 primeros parámetros son obligatorios.

    `consciencia` y `oxigeno_suplementario` aceptan None porque MIMIC-IV-ED **no los
    tiene** — no es un descuido del dataset, no existen en la base (ADR-007). Cuando
    faltan se imputa el valor de MENOR riesgo: "A" y aire ambiente.

    Eso sesga el score hacia abajo hasta 5 puntos (2 del oxígeno + 3 de la consciencia),
    siempre en la misma dirección: **nunca sobreestima el riesgo**. Para la tesis, que
    compara el modelo contra NEWS2, un baseline conservador juega en contra de la
    hipótesis y no a favor, así que si el modelo igual le gana el resultado es más fuerte.

    `imputado` y `puntos_imputados` viajan con cada fila para poder medir el efecto.

    En la app clínica esto NO pasa: ahí los 7 parámetros son obligatorios y sin ellos no
    se guarda. La asimetría es deliberada — al pie de la cama el dato se pide, en un
    dataset histórico no se puede.
    """
    imputado = consciencia is None or oxigeno_suplementario is None
    puntos_imputados = (3 if consciencia is None else 0) + (
        2 if oxigeno_suplementario is None else 0
    )

    acvpu = consciencia if consciencia is not None else "A"
    con_o2 = bool(oxigeno_suplementario)

    sub = {
        "frecuencia_respiratoria": puntaje_frecuencia_respiratoria(frecuencia_respiratoria),
        "spo2": puntaje_spo2(spo2, escala_spo2, con_o2),
        "oxigeno_suplementario": puntaje_oxigeno_suplementario(con_o2),
        "temperatura": puntaje_temperatura(temperatura),
        "presion_sistolica": puntaje_presion_sistolica(presion_sistolica),
        "frecuencia_cardiaca": puntaje_frecuencia_cardiaca(frecuencia_cardiaca),
        "consciencia": puntaje_consciencia(acvpu),
    }

    score = sum(sub.values())

    # El oxígeno suplementario queda FUERA del rojo aislado: puntúa 2 como máximo, así
    # que nunca puede ser el parámetro en 3. Se excluye igual que en el SQL.
    rojo_aislado = max(v for k, v in sub.items() if k != "oxigeno_suplementario") == 3

    return ResultadoNEWS2(
        score=score,
        riesgo=nivel_riesgo(score, rojo_aislado),
        rojo_aislado=rojo_aislado,
        sub=sub,
        imputado=imputado,
        puntos_imputados=puntos_imputados,
    )
