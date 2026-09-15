"""
Tubería de ingesta de MIMIC-IV-ED al esquema canónico de Zaha (SCRUM-50).

QUÉ HACE
Toma los CSV crudos de MIMIC-IV-ED —el demo abierto de 222 episodios o la base completa
de ~425.000, que tienen el MISMO esquema— y produce dos tablas limpias:

    observaciones.parquet   una fila por toma de signos vitales, con NEWS2 calculado
    episodios.parquet       una fila por episodio, con su desenlace

POR QUÉ CONTRA EL DEMO
`SCRUM-48` (credencial de PhysioNet) sigue bloqueado desde el 30/08. El demo se descarga
sin trámite, con licencia ODbL, y tiene el esquema idéntico: este código no cambia cuando
llegue la credencial, solo se le apunta a otra carpeta. Ver el README de la carpeta de datos.

LO QUE ESTE ARCHIVO NO HACE
No arma ventanas temporales ni features de modelado (`SCRUM-54`, `SCRUM-56`), y no entrena
nada. 64 pacientes no entrenan nada. Esto construye y prueba la tubería.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import news2
from ..validation import esquemas

# Los 5 parámetros que MIMIC-IV-ED sí tiene. Los otros 2 se imputan (ADR-007).
PARAMETROS_PRESENTES = ["resprate", "o2sat", "temperature", "sbp", "heartrate"]

# Rangos de plausibilidad fisiológica.
#
# Definidos en `validation/esquemas.py`, que es la fuente única. Se reexportan acá
# porque este módulo los usa para anular valores imposibles, y porque el nombre ya
# estaba publicado. Tienen que seguir siendo los mismos que los CHECK de la base
# (migración 20260521000000) y que `RANGOS` en `app/clinical/src/lib/tipos.ts`: si la
# base rechaza una SpO2 de 10 % pero la tubería la acepta, el NEWS2 histórico y el de
# producción se calculan sobre universos distintos y la comparativa de tasa de alertas
# (SCRUM-58) deja de significar algo.
#
# En el demo hay exactamente 2 filas fuera de rango: una SpO2 de 10 % y una sistólica de
# 11 mmHg. No son pacientes, son errores de registro — y las dos sumaban 3 puntos de
# NEWS2 cada una. A escala de la base completa van a ser cientos.
RANGOS_PLAUSIBLES = esquemas.RANGOS_PLAUSIBLES

# El desenlace. `disposition` es lo que pasó al terminar el episodio de guardia.
# ADMITTED (internación) es el proxy de deterioro; EXPIRED no aparece en el demo pero
# sí en la base completa, y también cuenta como desenlace adverso.
DISPOSICIONES_ADVERSAS = {"ADMITTED", "EXPIRED"}


@dataclass
class Resumen:
    episodios: int
    pacientes: int
    observaciones: int
    puntuables: int
    con_desenlace_adverso: int


def _fahrenheit_a_celsius(serie: pd.Series) -> pd.Series:
    """
    MIMIC registra la temperatura en FAHRENHEIT y NEWS2 se define en Celsius.

    Convertir a ciegas es peligroso: si alguna fila ya viniera en Celsius, un 36.5 se
    volvería 2.5 °C y puntuaría 3 sin que nada falle de forma visible. Por eso se
    convierte fila por fila, solo lo que está en rango plausible de Fahrenheit (86-113 °F
    = 30-45 °C). Lo que ya parece Celsius se deja como está, y lo que no es plausible en
    ninguna de las dos escalas queda en nulo: un dato imposible no es un dato.
    """
    valores = pd.to_numeric(serie, errors="coerce")
    parece_fahrenheit = valores.between(86, 113)
    parece_celsius = valores.between(30, 45)

    convertida = pd.Series(pd.NA, index=valores.index, dtype="Float64")
    convertida[parece_fahrenheit] = (valores[parece_fahrenheit] - 32) * 5 / 9
    convertida[parece_celsius] = valores[parece_celsius]
    return convertida


def cargar(raiz: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lee los CSV crudos. Acepta `.csv` y `.csv.gz` indistintamente."""
    ed = raiz / "ed"

    def leer(nombre: str) -> pd.DataFrame:
        for sufijo in (".csv.gz", ".csv"):
            ruta = ed / f"{nombre}{sufijo}"
            if ruta.exists():
                return pd.read_csv(ruta, low_memory=False)
        raise FileNotFoundError(f"No encontré {ed / nombre}.csv[.gz]")

    return leer("edstays"), leer("vitalsign")


def normalizar_observaciones(vitalsign: pd.DataFrame) -> pd.DataFrame:
    """Pasa `vitalsign` al vocabulario del proyecto y calcula NEWS2 por fila."""
    df = pd.DataFrame(
        {
            "episodio_id": vitalsign["stay_id"],
            "paciente_id": vitalsign["subject_id"],
            "medido_en": pd.to_datetime(vitalsign["charttime"], errors="coerce"),
            "frecuencia_respiratoria": pd.to_numeric(vitalsign["resprate"], errors="coerce"),
            "spo2": pd.to_numeric(vitalsign["o2sat"], errors="coerce"),
            "temperatura": _fahrenheit_a_celsius(vitalsign["temperature"]),
            "presion_sistolica": pd.to_numeric(vitalsign["sbp"], errors="coerce"),
            "frecuencia_cardiaca": pd.to_numeric(vitalsign["heartrate"], errors="coerce"),
        }
    )

    # Un valor fisiológicamente imposible NO es un valor: se anula, igual que lo haría
    # el CHECK de la base. Se anula el parámetro y no la fila entera, porque el resto de
    # la toma sigue siendo dato bueno; lo que pasa es que la toma deja de ser puntuable.
    df["valores_descartados"] = 0
    for parametro, (minimo, maximo) in RANGOS_PLAUSIBLES.items():
        valores = df[parametro]
        fuera = valores.notna() & ~valores.between(minimo, maximo)
        df.loc[fuera, parametro] = pd.NA
        df["valores_descartados"] += fuera.astype(int)

    # Una toma es puntuable si tiene los 5 parámetros que el dataset puede tener.
    # Las otras NO se imputan ni se descartan del archivo: se marcan. Descartarlas acá
    # escondería cuánto falta, y en este dataset la temperatura falta en el 44 % de las
    # tomas — es información sobre cómo se registra en guardia, no ruido.
    columnas = [
        "frecuencia_respiratoria",
        "spo2",
        "temperatura",
        "presion_sistolica",
        "frecuencia_cardiaca",
    ]
    df["puntuable"] = df[columnas].notna().all(axis=1)

    resultados = [
        news2.calcular(
            frecuencia_respiratoria=fila.frecuencia_respiratoria,
            spo2=fila.spo2,
            temperatura=fila.temperatura,
            presion_sistolica=fila.presion_sistolica,
            frecuencia_cardiaca=fila.frecuencia_cardiaca,
            # consciencia y oxigeno_suplementario van en None a propósito: MIMIC-IV-ED
            # no los tiene. El motor imputa el valor de menor riesgo y lo marca (ADR-007).
        )
        if fila.puntuable
        else None
        for fila in df.itertuples()
    ]

    df["news2_score"] = [r.score if r else pd.NA for r in resultados]
    df["news2_riesgo"] = [r.riesgo if r else pd.NA for r in resultados]
    df["news2_rojo_aislado"] = [r.rojo_aislado if r else pd.NA for r in resultados]
    df["news2_imputado"] = [r.imputado if r else pd.NA for r in resultados]
    df["news2_puntos_imputados"] = [r.puntos_imputados if r else pd.NA for r in resultados]

    for parametro in news2.calcular(
        frecuencia_respiratoria=16, spo2=98, temperatura=36.5,
        presion_sistolica=120, frecuencia_cardiaca=72,
    ).sub:
        df[f"sub_{parametro}"] = [r.sub[parametro] if r else pd.NA for r in resultados]

    df["news2_score"] = df["news2_score"].astype("Int64")
    return df.sort_values(["episodio_id", "medido_en"]).reset_index(drop=True)


def normalizar_episodios(edstays: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "episodio_id": edstays["stay_id"],
            "paciente_id": edstays["subject_id"],
            "ingreso_en": pd.to_datetime(edstays["intime"], errors="coerce"),
            "egreso_en": pd.to_datetime(edstays["outtime"], errors="coerce"),
            "llegada": edstays["arrival_transport"],
            "disposicion": edstays["disposition"],
        }
    )
    df["desenlace_adverso"] = df["disposicion"].isin(DISPOSICIONES_ADVERSAS)
    df["horas_en_guardia"] = (
        (df["egreso_en"] - df["ingreso_en"]).dt.total_seconds() / 3600
    ).round(2)
    return df


def construir(raiz_datos: Path, destino: Path) -> Resumen:
    """
    Corre la tubería completa, validando el esquema en CADA paso (SCRUM-52).

    Se valida a la entrada y a la salida, no solo al final: si el CSV crudo ya viene
    con una columna que cambió de nombre, el error tiene que decir eso y no aparecer
    doscientas líneas después como un tipo raro en el parquet.
    """
    edstays, vitalsign = cargar(raiz_datos)
    esquemas.validar(esquemas.VITALSIGN_CRUDO, vitalsign, "lectura de vitalsign")
    esquemas.validar(esquemas.EDSTAYS_CRUDO, edstays, "lectura de edstays")

    observaciones = normalizar_observaciones(vitalsign)
    episodios = normalizar_episodios(edstays)

    esquemas.validar(esquemas.OBSERVACIONES, observaciones, "observaciones normalizadas")
    esquemas.validar(esquemas.EPISODIOS, episodios, "episodios normalizados")

    destino.mkdir(parents=True, exist_ok=True)
    observaciones.to_parquet(destino / "observaciones.parquet", index=False)
    episodios.to_parquet(destino / "episodios.parquet", index=False)

    return Resumen(
        episodios=len(episodios),
        pacientes=episodios["paciente_id"].nunique(),
        observaciones=len(observaciones),
        puntuables=int(observaciones["puntuable"].sum()),
        con_desenlace_adverso=int(episodios["desenlace_adverso"].sum()),
    )


def main() -> None:
    # .../ml_engine/src/data/mimic_ed.py -> parents[2] es ml_engine
    raiz_ml = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Ingesta de MIMIC-IV-ED (SCRUM-50)")
    parser.add_argument(
        "--origen",
        type=Path,
        default=raiz_ml / "data" / "raw" / "mimic-iv-ed-demo-2.2",
        help="Carpeta que contiene ed/. Apuntar acá la base completa cuando llegue la credencial.",
    )
    parser.add_argument(
        "--destino",
        type=Path,
        default=raiz_ml / "data" / "processed" / "mimic-iv-ed-demo-2.2",
    )
    args = parser.parse_args()

    r = construir(args.origen, args.destino)
    print(f"origen  : {args.origen}")
    print(f"destino : {args.destino}")
    print(f"  episodios     : {r.episodios} ({r.pacientes} pacientes)")
    print(f"  observaciones : {r.observaciones} ({r.puntuables} puntuables)")
    print(f"  con desenlace adverso: {r.con_desenlace_adverso}")


if __name__ == "__main__":
    main()
