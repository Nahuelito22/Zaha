"""
La tasa de alertas del sistema PUBLICADO, contra la de la investigación (SCRUM-69).

QUÉ PREGUNTA CONTESTA
La tesis se midió en la investigación: `news2.py` replica la escala, `alertas.py` replica la
regla de alerta y el notebook 08 compara el modelo contra NEWS2. Pero lo que usa una
enfermera no es eso: es la base de datos de Supabase, que calcula NEWS2 con sus propias
funciones SQL, y la API de Hugging Face, que sirve el modelo exportado. Son la misma lógica
escrita dos veces, en dos lenguajes, y nada garantiza que coincidan.

Este módulo pasa la cohorte TRIAGE entera por **el sistema tal como está publicado** y
verifica, paciente por paciente, que dé lo mismo que la investigación. Si no coincidiera, la
tesis estaría describiendo un sistema que no existe.

POR QUÉ NO SE MIDE SOBRE LOS DATOS DE LA APLICACIÓN
Porque son ocho pacientes ficticios cargados para desarrollo. Una tasa de alertas sobre
ellos no significa nada clínicamente, y presentarla como "la tasa real" sería engañoso.

CÓMO SE MIDE SIN ENSUCIAR LA BASE
`vital_records` no admite borrado: insertar la cohorte para medir la dejaría para siempre en
producción. Las funciones de puntaje (`news2_score_*`, `news2_risk_level`) son `IMMUTABLE`,
así que se las llama directamente sobre una lista de valores, sin insertar una sola fila. El
redondeo de la temperatura a un decimal es el de la columna (`NUMERIC(4,1)`): es lo que le
pasa a una toma real al guardarse.

LOS TRES PASOS
    python -m src.evaluacion.tasa_produccion sql      > consulta.sql
        Genera la consulta. Se corre contra la base de producción (con el SQL editor de
        Supabase o su MCP) y su resultado se guarda en `data/interim/produccion_news2.json`.
        Devuelve sólo los desacuerdos y los totales, no las 1.300 filas.

    python -m src.evaluacion.tasa_produccion api
        Consulta la API publicada por la misma ruta que usa la landing
        (`zahasalud.com.ar/api/motor`), una vez por paciente, y guarda las respuestas.

    python -m src.evaluacion.tasa_produccion informe
        Compara todo contra la investigación e imprime el informe.

UNA ADVERTENCIA QUE VA CON LOS NÚMEROS DEL MODELO
El modelo publicado se entrenó con **toda** la cohorte TRIAGE. Medirlo sobre esa misma
cohorte es una medición *dentro de la muestra*: su sensibilidad y su tasa salen optimistas.
Lo que este módulo verifica del modelo es que la API devuelva lo mismo que el artefacto, no
cuánto rinde; cuánto rinde está medido fuera de fold en el notebook 08 y publicado en el
sidecar.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ..api.modelo import Modelo

RAIZ_ML = Path(__file__).resolve().parents[2]
PARQUET = RAIZ_ML / "data" / "processed" / "triage-zenodo" / "triage.parquet"
INTERIM = RAIZ_ML / "data" / "interim"
RESULTADO_SQL = INTERIM / "produccion_news2.json"
CACHE_API = INTERIM / "produccion_modelo.json"

URL_MOTOR = "https://zahasalud.com.ar/api/motor/prediccion"
# El valor por defecto de la API, y el que usa la aplicación: la Edge Function no elige.
SENSIBILIDAD = 0.70
# Diferencia tolerada entre la probabilidad de la API y la del artefacto local. La API
# redondea a seis decimales; más que eso sería otro modelo.
TOLERANCIA = 1e-5


def cohorte() -> pd.DataFrame:
    d = pd.read_parquet(PARQUET)
    return d[d.puntuable].reset_index(drop=True)


def observacion(fila) -> dict[str, float]:
    """La toma en el vocabulario de la API. La "C" de NEWS2 es la confusión nueva."""
    return {
        "frecuencia_respiratoria": float(fila.frecuencia_respiratoria),
        "spo2": float(fila.spo2),
        "temperatura": round(float(fila.temperatura), 1),
        "presion_sistolica": float(fila.presion_sistolica),
        "frecuencia_cardiaca": float(fila.frecuencia_cardiaca),
        "confusion": 0 if fila.consciencia == "A" else 1,
        "edad": float(fila.edad),
    }


# -- paso 1: NEWS2 en la base de producción -----------------------------------------


# Parámetro de la cohorte -> función de producción que lo puntúa. Escala 1 de SpO2 y aire
# ambiente: es lo que la ingesta de TRIAGE imputa (ADR-007), y lo mismo recibe la base.
FUNCIONES = {
    "frecuencia_respiratoria": "public.news2_score_respiratory_rate(v::int)",
    "spo2": "public.news2_score_spo2(v::int, 1::smallint, false)",
    # La columna de producción es NUMERIC(4,1): el redondeo es el que sufre una toma real.
    "temperatura": "public.news2_score_temperature(v::numeric(4,1))",
    "presion_sistolica": "public.news2_score_systolic_bp(v::int)",
    "frecuencia_cardiaca": "public.news2_score_heart_rate(v::int)",
}


def _clave(v: float) -> str:
    """Cómo viaja un valor a la consulta y vuelve como clave del JSON: idéntico en ambos."""
    return repr(float(v))


def sql_news2(d: pd.DataFrame) -> str:
    """
    Una consulta que puntúa con las funciones de producción cada valor DISTINTO de cada
    parámetro, más la tabla completa de niveles de riesgo.

    No hace falta mandar los 1.300 pacientes: el trigger de producción calcula NEWS2 como la
    suma de siete subpuntajes independientes, marca rojo aislado si alguno vale 3, y le pide
    el nivel a `news2_risk_level`. Con el subpuntaje de producción de cada valor y esa tabla,
    el puntaje de cada paciente se reconstruye exacto. Son unos cientos de valores en vez de
    1.300 filas, y la consulta entra en un pedido.
    """
    bloques = []
    for parametro, funcion in FUNCIONES.items():
        valores = ", ".join(f"({_clave(v)}::float8)" for v in sorted(d[parametro].unique()))
        bloques.append(
            f"  '{parametro}', (SELECT json_object_agg(v::text, {funcion})\n"
            f"                  FROM (VALUES {valores}) AS t(v))"
        )
    bloques.append(
        "  'consciencia', (SELECT json_object_agg(v, public.news2_score_consciousness(v))\n"
        "                  FROM (VALUES ('A'), ('C')) AS t(v))"
    )
    bloques.append(
        "  'oxigeno', public.news2_score_supplemental_oxygen(false)"
    )
    bloques.append(
        "  'riesgo', (SELECT json_object_agg(s || '|' || r, public.news2_risk_level(s, r))\n"
        "             FROM generate_series(0, 20) s, (VALUES (true), (false)) AS b(r))"
    )
    return (
        "-- Generado por src/evaluacion/tasa_produccion.py (SCRUM-69).\n"
        "-- Sólo llama funciones IMMUTABLE de producción: no lee ni escribe ninguna tabla.\n"
        "SELECT json_build_object(\n" + ",\n".join(bloques) + "\n) AS resultado;\n"
    )


def news2_produccion(d: pd.DataFrame, tablas: dict) -> pd.DataFrame:
    """Reconstruye puntaje, rojo aislado y nivel de cada paciente con las tablas de producción."""
    sub = pd.DataFrame({
        p: d[p].map(lambda v: tablas[p][_clave_pg(v)]) for p in FUNCIONES
    })
    sub["consciencia"] = d.consciencia.map(tablas["consciencia"])
    sub["oxigeno"] = tablas["oxigeno"]
    score = sub.sum(axis=1).astype(int)
    rojo = (sub == 3).any(axis=1)
    riesgo = [tablas["riesgo"][f"{s}|{str(r).lower()}"] for s, r in zip(score, rojo)]
    return pd.DataFrame({"score": score, "rojo": rojo, "riesgo": riesgo})


def _clave_pg(v: float) -> str:
    """
    La clave tal como la devuelve Postgres. En esta base `float8::text` escribe 15 dígitos
    significativos (`34.5999984741211`, `12`), no la representación más corta de Python.
    Medido sobre la respuesta real, no supuesto.
    """
    return f"{float(v):.15g}"


# -- paso 2: el modelo en la API publicada ------------------------------------------


def _consultar(obs: dict[str, float]) -> dict:
    cuerpo = json.dumps({"observacion": obs}).encode()
    pedido = urllib.request.Request(
        URL_MOTOR, data=cuerpo, headers={"Content-Type": "application/json"}, method="POST"
    )
    for intento in range(4):
        try:
            with urllib.request.urlopen(pedido, timeout=120) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError):
            # El Space gratuito se duerme: el primer pedido puede tardar o fallar.
            if intento == 3:
                raise
    raise RuntimeError("inalcanzable")


def consultar_api(d: pd.DataFrame, hilos: int = 4) -> list[dict]:
    """Una consulta por paciente, por la misma ruta que usa la landing."""
    _consultar(observacion(next(d.itertuples())))  # despierta el Space antes de la ráfaga
    with ThreadPoolExecutor(hilos) as ex:
        respuestas = list(ex.map(lambda r: _consultar(observacion(r)), d.itertuples()))
    return [
        {"id": int(r.paciente_id), "probabilidad": a["probabilidad"], "alerta": a["alerta"],
         "umbral": a["punto_de_operacion"]["umbral"],
         "tasa_esperada": a["punto_de_operacion"]["tasa_de_alertas_esperada"]}
        for r, a in zip(d.itertuples(), respuestas)
    ]


# -- paso 3: el informe -------------------------------------------------------------


@dataclass
class Informe:
    pacientes: int
    eventos: int
    news2_desacuerdos: int
    news2_alertas_prod: int
    news2_alertas_inv: int
    news2_eventos_alertados: int
    modelo_max_diferencia: float
    modelo_desacuerdos_alerta: int
    modelo_alertas: int
    modelo_eventos_alertados: int
    modelo_tasa_fuera_de_fold: float
    umbral: float

    def lineas(self) -> list[str]:
        n, e = self.pacientes, self.eventos
        pct = lambda a, b: f"{a} de {b} ({100 * a / b:.1f} %)"  # noqa: E731
        return [
            f"Cohorte TRIAGE puntuable: {n} pacientes, {e} muertes a 30 días.",
            "",
            "NEWS2 — base de datos de producción contra news2.py",
            f"  pacientes con puntaje o nivel distinto: {self.news2_desacuerdos}",
            f"  alertas (riesgo distinto de Bajo): producción {pct(self.news2_alertas_prod, n)}"
            f" · investigación {pct(self.news2_alertas_inv, n)}",
            f"  sensibilidad para muerte a 30 días: {pct(self.news2_eventos_alertados, e)}",
            "",
            f"Modelo — API publicada contra el artefacto local (sensibilidad objetivo {SENSIBILIDAD:.0%},"
            f" umbral {self.umbral:.3f})",
            f"  diferencia máxima de probabilidad: {self.modelo_max_diferencia:.2e}",
            f"  pacientes con distinta decisión de alerta: {self.modelo_desacuerdos_alerta}",
            f"  alertas: {pct(self.modelo_alertas, n)}  (dentro de la muestra: optimista)",
            f"  sensibilidad para muerte a 30 días: {pct(self.modelo_eventos_alertados, e)}"
            "  (ídem)",
            f"  tasa esperada publicada, medida fuera de fold: {100 * self.modelo_tasa_fuera_de_fold:.1f} %",
        ]


def informe(d: pd.DataFrame, sql: dict, api: list[dict]) -> Informe:
    modelo = Modelo()
    por_id = {a["id"]: a for a in api}
    locales, prod, alerta_prod = [], [], []
    for r in d.itertuples():
        a = por_id[int(r.paciente_id)]
        locales.append(modelo.predecir(observacion(r), SENSIBILIDAD).probabilidad)
        prod.append(a["probabilidad"])
        alerta_prod.append(a["alerta"])
    locales, prod = np.array(locales), np.array(prod)
    umbral = api[0]["umbral"]
    alerta_local = locales >= umbral
    alerta_prod = np.array(alerta_prod)
    y = d.muerte_30d.to_numpy().astype(bool)

    prod_n2 = news2_produccion(d, sql)
    desacuerdo = (prod_n2.score.to_numpy() != d.news2_score.to_numpy()) | (
        prod_n2.riesgo.to_numpy() != d.news2_riesgo.to_numpy()
    )
    alerta_n2_prod = prod_n2.riesgo.to_numpy() != "Bajo"
    alerta_n2_inv = d.news2_riesgo.to_numpy() != "Bajo"

    return Informe(
        pacientes=len(d),
        eventos=int(y.sum()),
        news2_desacuerdos=int(desacuerdo.sum()),
        news2_alertas_prod=int(alerta_n2_prod.sum()),
        news2_alertas_inv=int(alerta_n2_inv.sum()),
        news2_eventos_alertados=int((alerta_n2_prod & y).sum()),
        modelo_max_diferencia=float(np.max(np.abs(locales - prod))),
        modelo_desacuerdos_alerta=int(np.sum(alerta_local != alerta_prod)),
        modelo_alertas=int(alerta_prod.sum()),
        modelo_eventos_alertados=int((alerta_prod & y).sum()),
        modelo_tasa_fuera_de_fold=float(api[0]["tasa_esperada"]),
        umbral=float(umbral),
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("paso", choices=["sql", "api", "informe"])
    paso = p.parse_args().paso
    d = cohorte()

    if paso == "sql":
        sys.stdout.write(sql_news2(d))
    elif paso == "api":
        INTERIM.mkdir(parents=True, exist_ok=True)
        CACHE_API.write_text(json.dumps(consultar_api(d)), encoding="utf-8")
        print(f"{len(d)} respuestas en {CACHE_API}")
    else:
        sql = json.loads(RESULTADO_SQL.read_text(encoding="utf-8"))
        api = json.loads(CACHE_API.read_text(encoding="utf-8"))
        print("\n".join(informe(d, sql, api).lineas()))


if __name__ == "__main__":
    main()
