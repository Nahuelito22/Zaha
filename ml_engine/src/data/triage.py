"""
Ingesta de la cohorte TRIAGE al vocabulario del proyecto (ADR-009).

QUÉ ES ESTA COHORTE
El dataset del estudio TRIAGE (`zenodo.org/records/4963759`, CC0): 1.303 pacientes adultos
de guardia de tres centros terciarios —EE.UU. 940, Francia 355, Suiza 8—, con los
componentes de NEWS medidos **al ingreso** y dos desenlaces reales: mortalidad a 30 días e
ingreso a UCI.

POR QUÉ EXISTE ESTE MÓDULO, SI YA ESTÁ `mimic_ed.py`
Porque sobre el demo de MIMIC-IV-ED la tesis **no se puede medir**. Ahí se puede calcular la
tasa de alertas de NEWS2 (`SCRUM-80`) pero no su **sensibilidad**: el horizonte de 24 h de
la etiqueta v2 no discrimina —estadía mediana 5,8 h— y la etiqueta colapsa a "el episodio
terminó en internación", con una prevalencia del 66,8 % que no es clínica. Sin sensibilidad
no hay "comparativa a sensibilidad igualada", que es `SCRUM-58` y es la tesis.

Acá sí hay desenlace real con prevalencia real: **4,2 % de mortalidad a 30 días**.

LO QUE ESTA COHORTE NO PUEDE HACER — leer antes de usarla
- **Una sola fila por paciente.** No hay serie temporal, así que la hipótesis de la LSTM
  (`SCRUM-57`) NO se puede probar con esto. Sigue dependiendo de MIMIC.
- **El desenlace es otro.** Mortalidad a 30 días e ingreso a UCI desde el snapshot de
  admisión, **no** la ventana `(t+1h, t+24h]` de `etiquetas.py`. Son dos definiciones
  distintas y **no se mezclan en una misma métrica**. Es el encuadre snapshot del ADR-005.
- **La población es otra.** 72 % de un único hospital de EE.UU. Generalizar a una guardia
  argentina es una limitación declarada, no un resultado.
- **Es NEWS, no NEWS2.** Difieren en la escala 2 de SpO₂ para hipercápnicos y en el
  tratamiento de la confusión. Toda comparación se acota a los componentes compartidos.

EL HUECO DE PARÁMETROS ES MÁS CHICO QUE EN MIMIC
MIMIC no tiene ni consciencia ni oxígeno suplementario: imputa 2 de 7 (ADR-007). Acá la
columna `confusion` **es** la "C" de NEWS2, así que se imputa **uno solo**, el oxígeno. El
sesgo del ADR-007 sigue yendo en la misma dirección —el score nunca sobreestima— pero pesa
la mitad.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import news2
from ..validation import esquemas

# Fuente única, la misma que usan `mimic_ed.py`, los CHECK de la base y `tipos.ts`. Si esta
# cohorte aceptara valores que la base rechaza, los NEWS2 de las dos se calcularían sobre
# universos distintos y dejarían de ser comparables.
RANGOS_PLAUSIBLES = esquemas.RANGOS_PLAUSIBLES

# Los cinco parámetros medidos, en el vocabulario del proyecto -> nombre en el archivo.
PARAMETROS = {
    "frecuencia_respiratoria": "resp_rate",
    "spo2": "SpO2",
    "temperatura": "temp",
    "presion_sistolica": "BPS",
    "frecuencia_cardiaca": "HR",
}

# Los dos desenlaces disponibles. Se conservan los DOS y no se elige uno acá: cuál es el
# evento a predecir es una decisión del análisis, no de la ingesta.
DESENLACES = ("muerte_30d", "ingreso_uci")


@dataclass
class Resumen:
    pacientes: int
    puntuables: int
    valores_descartados: int
    con_confusion: int
    muertes_30d: int
    ingresos_uci: int

    @property
    def prevalencia_muerte(self) -> float:
        return self.muertes_30d / self.pacientes if self.pacientes else 0.0

    @property
    def prevalencia_uci(self) -> float:
        return self.ingresos_uci / self.pacientes if self.pacientes else 0.0


def cargar(ruta: Path) -> pd.DataFrame:
    """Lee el `.xls` legacy. Necesita `xlrd` (está en requirements-dev.txt)."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No encontré {ruta}. Se baja de https://zenodo.org/records/4963759 "
            "(CC0, sin registro ni DUA). Ver el README de la carpeta."
        )
    return pd.read_excel(ruta)


def normalizar(crudo: pd.DataFrame) -> pd.DataFrame:
    """
    Pasa el archivo al vocabulario del proyecto y calcula NEWS2 por fila.

    La consciencia sale de `confusion` y NO se imputa: es el dato real del estudio. El
    oxígeno suplementario sí se imputa a aire ambiente, porque el estudio no lo registra.
    """
    df = pd.DataFrame(
        {
            destino: pd.to_numeric(crudo[origen], errors="coerce")
            for destino, origen in PARAMETROS.items()
        }
    )
    df["paciente_id"] = np.arange(1, len(crudo) + 1)
    df["pais"] = crudo["country"].astype(str)
    df["edad"] = pd.to_numeric(crudo["age"], errors="coerce")

    # "C" es confusión NUEVA, que en NEWS2 puntúa 3 igual que V, P y U. "A" es alerta.
    df["consciencia"] = np.where(crudo["confusion"] == 1, "C", "A")

    df["muerte_30d"] = crudo["death30d"].astype(int)
    df["ingreso_uci"] = crudo["ICU"].astype(int)

    # Un valor fisiológicamente imposible no es un valor: se anula el parámetro, no la
    # fila. Mismo criterio que `mimic_ed.normalizar_observaciones`.
    df["valores_descartados"] = 0
    for parametro, (minimo, maximo) in RANGOS_PLAUSIBLES.items():
        if parametro not in df:
            continue
        fuera = df[parametro].notna() & ~df[parametro].between(minimo, maximo)
        df.loc[fuera, parametro] = np.nan
        df["valores_descartados"] += fuera.astype(int)

    df["puntuable"] = df[list(PARAMETROS)].notna().all(axis=1)

    resultados = [
        news2.calcular(
            frecuencia_respiratoria=fila.frecuencia_respiratoria,
            spo2=fila.spo2,
            temperatura=fila.temperatura,
            presion_sistolica=fila.presion_sistolica,
            frecuencia_cardiaca=fila.frecuencia_cardiaca,
            consciencia=fila.consciencia,
            # oxigeno_suplementario va en None: el estudio no lo registra, y el motor lo
            # imputa a aire ambiente marcándolo (ADR-007).
        )
        if fila.puntuable
        else None
        for fila in df.itertuples()
    ]

    df["news2_score"] = pd.array(
        [r.score if r else pd.NA for r in resultados], dtype="Int64"
    )
    df["news2_riesgo"] = [r.riesgo if r else pd.NA for r in resultados]
    df["news2_rojo_aislado"] = [r.rojo_aislado if r else pd.NA for r in resultados]
    df["news2_imputado"] = [r.imputado if r else pd.NA for r in resultados]
    df["news2_puntos_imputados"] = [r.puntos_imputados if r else pd.NA for r in resultados]

    for parametro in news2.calcular(
        frecuencia_respiratoria=16, spo2=98, temperatura=36.5,
        presion_sistolica=120, frecuencia_cardiaca=72,
    ).sub:
        df[f"sub_{parametro}"] = [r.sub[parametro] if r else pd.NA for r in resultados]

    return df


def resumir(normalizado: pd.DataFrame) -> Resumen:
    return Resumen(
        pacientes=len(normalizado),
        puntuables=int(normalizado["puntuable"].sum()),
        valores_descartados=int(normalizado["valores_descartados"].sum()),
        con_confusion=int((normalizado["consciencia"] == "C").sum()),
        muertes_30d=int(normalizado["muerte_30d"].sum()),
        ingresos_uci=int(normalizado["ingreso_uci"].sum()),
    )


def construir(origen: Path, destino: Path) -> Resumen:
    """Corre la ingesta completa, validando el esquema a la entrada."""
    crudo = cargar(origen)
    esquemas.validar(esquemas.TRIAGE_CRUDO, crudo, "lectura de TRIAGE")

    normalizado = normalizar(crudo)

    destino.mkdir(parents=True, exist_ok=True)
    normalizado.to_parquet(destino / "triage.parquet", index=False)
    return resumir(normalizado)


def main() -> None:
    raiz_ml = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Ingesta de la cohorte TRIAGE (ADR-009)")
    parser.add_argument(
        "--origen",
        type=Path,
        default=raiz_ml / "data" / "raw" / "triage-zenodo" / "NEWS_datafile.xls",
    )
    parser.add_argument(
        "--destino",
        type=Path,
        default=raiz_ml / "data" / "processed" / "triage-zenodo",
    )
    args = parser.parse_args()

    r = construir(args.origen, args.destino)
    print(f"origen  : {args.origen}")
    print(f"destino : {args.destino}")
    print(f"  pacientes            : {r.pacientes}")
    print(f"  puntuables           : {r.puntuables}")
    print(f"  valores anulados     : {r.valores_descartados}")
    print(f"  con confusion ('C')  : {r.con_confusion}   <- MIMIC no tiene este dato")
    print(f"  muerte a 30 dias     : {r.muertes_30d}  ({r.prevalencia_muerte:.1%})")
    print(f"  ingreso a UCI        : {r.ingresos_uci}  ({r.prevalencia_uci:.1%})")
    print()
    print("  Ojo: una fila por paciente. Sirve para el encuadre snapshot (ADR-005) y NO")
    print("  para la LSTM ni para la etiqueta v2, que siguen dependiendo de MIMIC.")


if __name__ == "__main__":
    main()
