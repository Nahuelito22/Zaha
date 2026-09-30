"""
Exportación del modelo elegido a ONNX (SCRUM-59).

QUÉ EXPORTA, Y POR QUÉ NO ES XGBOOST
El ADR-004 planeaba "PyTorch → ONNX" y el ADR-005 daba por sentado que el modelo principal
sería XGBoost. **Ninguna de las dos cosas resultó cierta.** Con 54 eventos la familia que
gana es una **regresión logística** —lo eligieron los 5 folds de la CV anidada de
`SCRUM-56`, sin excepción— así que es la que se exporta. Ver el hallazgo completo en
`baseline.py`.

SE EXPORTA EL PIPELINE COMPLETO, NO SÓLO EL CLASIFICADOR
El artefacto incluye imputación, escalado y regresión en un solo grafo. Es la decisión más
importante de este módulo: si la API tuviera que reimplementar el escalado por su cuenta,
cualquier diferencia en la media o el desvío usados produciría predicciones distintas **sin
que nada falle**. El modelo servido y el modelo evaluado dejarían de ser el mismo, y ninguna
métrica de la tesis describiría lo que corre en producción.

EL ORDEN DE LAS COLUMNAS ES PARTE DEL CONTRATO
ONNX recibe un tensor, no un DataFrame: las columnas viajan por posición y nadie valida los
nombres. Mandar la frecuencia cardíaca donde el modelo espera la temperatura no produce un
error, produce un número. Por eso el orden se congela en `FEATURES` y se escribe en el
sidecar de metadatos que acompaña al `.onnx`.

LA PARIDAD SE VERIFICA, NO SE ASUME
Convertir a ONNX puede cambiar los resultados: scikit-learn calcula en float64 y la
conversión por defecto usa tensores float32. La diferencia es chica pero no es cero, y cerca
del umbral de decisión puede cambiar de qué lado cae un paciente. `verificar_paridad()`
compara las dos implementaciones sobre **toda** la cohorte y reporta la desviación máxima y
cuántas decisiones cambiarían. Un export que diverge en silencio es el modo de falla clásico
de este paso.

EL UMBRAL NO SE ELIGE ACÁ
El modelo devuelve una probabilidad. Convertirla en alerta requiere un umbral, y **cuál es
el correcto es una decisión clínica, no técnica**: depende de cuántas alertas por turno
tolera la guardia. El sidecar publica la curva de operación —qué umbral da qué sensibilidad
a qué costo de alertas— y deja la elección al que despliega.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import alertas
from . import baseline

# Umbrales cuya sensibilidad se publica en el sidecar. Es la misma grilla sobre la que
# `SCRUM-58` compara contra NEWS2, para que las dos cosas hablen de lo mismo.
SENSIBILIDADES_PUBLICADAS = alertas.GRILLA_SENSIBILIDAD


@dataclass
class Paridad:
    filas: int
    desviacion_maxima: float
    decisiones_cambiadas: dict[float, int] = field(default_factory=dict)

    @property
    def aceptable(self) -> bool:
        """
        Tolerancia de 1e-5 sobre la probabilidad.

        No es un número mágico: float32 tiene ~7 dígitos decimales de precisión, así que
        una diferencia mayor que ésta no se explica por el cambio de tipo y significa que
        la conversión alteró el modelo.
        """
        return self.desviacion_maxima < 1e-5


def exportar(modelo, n_features: int, destino: Path) -> Path:
    """Convierte el pipeline entrenado a ONNX y lo escribe en disco."""
    from skl2onnx import to_onnx

    # Entrada float32: es lo que el runtime de inferencia usa y lo que la API va a mandar.
    # Declararlo explícito evita que la conversión infiera float64 y el Space falle al
    # recibir float32.
    muestra = np.zeros((1, n_features), dtype=np.float32)
    onx = to_onnx(modelo, muestra, target_opset=None)

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(onx.SerializeToString())
    return destino


def _probabilidades_onnx(ruta: Path, X: np.ndarray) -> np.ndarray:
    import onnxruntime as ort

    sesion = ort.InferenceSession(str(ruta), providers=["CPUExecutionProvider"])
    entrada = sesion.get_inputs()[0].name
    salidas = sesion.run(None, {entrada: X.astype(np.float32)})

    # skl2onnx devuelve [etiqueta, probabilidades]. Las probabilidades pueden venir como
    # arreglo o como lista de diccionarios {clase: prob} segun el conversor.
    probas = salidas[1]
    if isinstance(probas, list):
        return np.array([p[1] for p in probas], dtype=float)
    return np.asarray(probas)[:, 1].astype(float)


def verificar_paridad(modelo, ruta_onnx: Path, X: np.ndarray) -> Paridad:
    """
    Compara scikit-learn contra ONNX sobre todas las filas.

    Además de la desviación numérica se cuenta, para cada umbral publicado, **cuántos
    pacientes cambiarían de lado**. Es la métrica que importa de verdad: una diferencia de
    1e-7 en la probabilidad es irrelevante salvo que caiga justo sobre el umbral.
    """
    p_sklearn = modelo.predict_proba(X)[:, 1]
    p_onnx = _probabilidades_onnx(ruta_onnx, X)

    desviacion = float(np.max(np.abs(p_sklearn - p_onnx)))

    cambiadas: dict[float, int] = {}
    for objetivo in SENSIBILIDADES_PUBLICADAS:
        umbral = float(np.quantile(p_sklearn, 1 - objetivo))
        cambiadas[objetivo] = int(np.sum((p_sklearn >= umbral) != (p_onnx >= umbral)))

    return Paridad(filas=len(X), desviacion_maxima=desviacion, decisiones_cambiadas=cambiadas)


def metadatos(
    df: pd.DataFrame, modelo, evento: str, paridad: Paridad, fuera_de_fold=None
) -> dict:
    """
    El sidecar que viaja con el `.onnx`.

    Un `.onnx` suelto no dice qué espera en cada columna, sobre qué se entrenó, ni qué
    umbral usar. Sin esto el archivo es inservible en seis meses, y la API no tendría cómo
    validar que está mandando las features en el orden correcto.
    """
    X = baseline.matriz(df).to_numpy(dtype=float)
    y = df[evento].to_numpy().astype(int)
    probas = modelo.predict_proba(X)[:, 1]

    # El UMBRAL sale del modelo final, que es el que se despliega: su distribucion de
    # puntajes es la que la API va a ver. Pero la TASA DE ALERTAS esperada se reporta
    # fuera de fold, no in-sample: el modelo final vio a estos pacientes, asi que su tasa
    # in-sample es optimista y quien elija un umbral leyendo este archivo subestimaria la
    # carga real de alertas. Sobre esta cohorte la diferencia es de 4 a 5 puntos.
    curva = []
    for objetivo in SENSIBILIDADES_PUBLICADAS:
        umbral = float(np.quantile(probas, 1 - objetivo))
        tasa_in = alertas.tasa_alertas_a_sensibilidad(y.astype(bool), probas, objetivo)
        tasa_oof = (
            alertas.tasa_alertas_a_sensibilidad(y.astype(bool), fuera_de_fold, objetivo)
            if fuera_de_fold is not None else float("nan")
        )
        curva.append(
            {
                "sensibilidad_objetivo": objetivo,
                "umbral": round(umbral, 6),
                "tasa_de_alertas_esperada": round(float(tasa_oof), 4) if tasa_oof == tasa_oof else None,
                "tasa_de_alertas_in_sample_optimista": round(float(tasa_in), 4) if tasa_in == tasa_in else None,
            }
        )

    return {
        "modelo": "regresion_logistica",
        "por_que_no_xgboost": (
            "Con 54 eventos la regresion logistica gana; los 5 folds de la CV anidada de "
            "SCRUM-56 la eligieron. El ADR-005 supone XGBoost y necesita enmienda."
        ),
        "pipeline": "SimpleImputer -> StandardScaler -> LogisticRegression(class_weight=balanced)",
        "features_en_orden": baseline.FEATURES,
        "features_excluidas": {
            "cuales": list(baseline.EXCLUIDAS_POR_NO_ESTAR_AL_PIE_DE_LA_CAMA),
            "por_que": "no estan disponibles al pie de la cama; incluirlas haria el modelo indesplegable",
        },
        "entrenado_sobre": {
            "cohorte": "triage-zenodo",
            "n": int(len(df)),
            "evento": evento,
            "eventos": int(y.sum()),
            "prevalencia": round(float(y.mean()), 4),
        },
        "umbral": {
            "elegir_es_decision_clinica": True,
            "nota": "depende de cuantas alertas por turno tolera la guardia",
            "usar_tasa_de_alertas_esperada": (
                "es la estimacion fuera de fold. La in_sample se incluye solo para mostrar "
                "cuanto optimismo tendria confiar en ella; NO usarla para dimensionar la carga."
            ),
            "curva": curva,
        },
        "paridad_onnx_vs_sklearn": {
            "filas_verificadas": paridad.filas,
            "desviacion_maxima": paridad.desviacion_maxima,
            "decisiones_cambiadas_por_umbral": {
                str(k): v for k, v in paridad.decisiones_cambiadas.items()
            },
            "aceptable": paridad.aceptable,
        },
        "advertencia": (
            "La reduccion de alertas contra NEWS2 NO esta demostrada con esta cohorte: "
            "+29,8 % con IC95 [-8,5 %, +44,7 %], que incluye el cero. Ver SCRUM-58."
        ),
        "generado": date.today().isoformat(),
    }


def construir(procesados: Path, destino: Path, evento: str = "muerte_30d"):
    df = pd.read_parquet(procesados / "triage.parquet")
    df = df[df["puntuable"]]

    modelo = baseline.entrenar(df, evento=evento)
    X = baseline.matriz(df).to_numpy(dtype=float)

    ruta_onnx = destino / "zaha_baseline.onnx"
    exportar(modelo, X.shape[1], ruta_onnx)

    paridad = verificar_paridad(modelo, ruta_onnx, X)

    # Los puntajes fuera de fold son los unicos que dan una tasa de alertas honesta.
    oof = baseline.evaluar_anidada(df, evento=evento).puntajes
    meta = metadatos(df, modelo, evento, paridad, fuera_de_fold=oof)

    ruta_meta = destino / "zaha_baseline.metadata.json"
    ruta_meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return ruta_onnx, ruta_meta, paridad


def main() -> None:
    raiz_ml = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Exportar el modelo a ONNX (SCRUM-59)")
    parser.add_argument(
        "--procesados", type=Path,
        default=raiz_ml / "data" / "processed" / "triage-zenodo",
    )
    parser.add_argument("--destino", type=Path, default=raiz_ml / "models")
    parser.add_argument("--evento", default="muerte_30d")
    args = parser.parse_args()

    ruta_onnx, ruta_meta, paridad = construir(args.procesados, args.destino, args.evento)

    print(f"  modelo    : {ruta_onnx}  ({ruta_onnx.stat().st_size:,} bytes)")
    print(f"  metadatos : {ruta_meta}")
    print()
    print(f"  paridad sklearn vs ONNX sobre {paridad.filas} filas:")
    print(f"    desviacion maxima de la probabilidad: {paridad.desviacion_maxima:.2e}")
    for objetivo, n in paridad.decisiones_cambiadas.items():
        print(f"    decisiones que cambian a sensibilidad {objetivo:.0%}: {n}")
    print()
    if paridad.aceptable:
        print("  OK: el modelo servido y el evaluado son el mismo.")
    else:
        print("  ATENCION: la desviacion supera la tolerancia. NO desplegar.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
