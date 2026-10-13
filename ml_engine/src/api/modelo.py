"""
Carga del artefacto ONNX e inferencia (SCRUM-62).

QUÉ SIRVE Y QUÉ NO
Sirve la probabilidad del modelo y la decisión de alerta en un punto de operación
declarado. **No** calcula NEWS2: la escala es determinística, se calcula en la base de
datos y sigue funcionando aunque este servicio no exista. Esa separación es deliberada y
es la que permite `SCRUM-65` (degradación elegante) — ver también la decisión del Sprint 2
de que la predicción se muestre separada visualmente del puntaje determinístico.

EL ARTEFACTO NO SE CARGA A CIEGAS
`zaha_baseline.onnx` sin su sidecar es inservible: el grafo no dice en qué orden espera
las columnas ni qué umbral usar. Por eso acá se carga **el par**, y el arranque falla
ruidosamente si no se corresponden. Las tres verificaciones:

  1. El ancho de la entrada del grafo coincide con `features_en_orden`. Si el modelo se
     reentrenara con una feature más y alguien copiara sólo el `.onnx`, las columnas
     quedarían corridas y el servicio devolvería probabilidades plausibles de otro
     paciente. Es exactamente el modo de falla que el Sprint 2 dejó anotado: el error que
     no se ve.
  2. La paridad ONNX↔scikit-learn registrada en el sidecar es aceptable. Servir un
     artefacto cuya verificación de paridad falló sería servir un modelo distinto del que
     se evaluó, y las métricas de la tesis describirían otra cosa.
  3. Hay al menos un punto de operación en la curva.

SOBRE LA COPIA DE `_probabilidades_onnx`
La extracción de la probabilidad desde la salida de skl2onnx está duplicada respecto de
`src/models/exportar.py`. No es un descuido: `exportar` importa pandas y scikit-learn, que
no están en el contenedor de producción. La duplicación se mantiene honesta con
`tests/test_api.py::test_la_api_y_el_exportador_leen_igual_la_salida_onnx`, que compara
las dos implementaciones sobre las mismas filas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort

RAIZ_ML = Path(__file__).resolve().parents[2]
DIRECTORIO_MODELOS = RAIZ_ML / "models"

NOMBRE_ONNX = "zaha_baseline.onnx"
NOMBRE_METADATOS = "zaha_baseline.metadata.json"


class ContratoRoto(RuntimeError):
    """
    El artefacto y su sidecar no se corresponden, o el artefacto no es servible.

    Se levanta al cargar, no al predecir: un servicio que arranca con un modelo roto y
    falla recién con el primer paciente es peor que uno que no arranca.
    """


class PuntoNoCalibrado(ValueError):
    """Se pidió una sensibilidad que no está en la curva publicada."""


@dataclass(frozen=True)
class PuntoDeOperacion:
    """
    Un umbral con su consecuencia declarada.

    `tasa_de_alertas_esperada` es la estimación **fuera de fold**: es la que dimensiona la
    carga real de trabajo. El sidecar incluye además una in-sample, más optimista, que no
    se expone acá justamente para que nadie la use para planificar un turno.
    """

    sensibilidad_objetivo: float
    umbral: float
    tasa_de_alertas_esperada: float | None


@dataclass(frozen=True)
class Prediccion:
    probabilidad: float
    alerta: bool
    punto: PuntoDeOperacion


def _probabilidades(sesion: ort.InferenceSession, X: np.ndarray) -> np.ndarray:
    entrada = sesion.get_inputs()[0].name
    salidas = sesion.run(None, {entrada: X.astype(np.float32)})

    # skl2onnx devuelve [etiqueta, probabilidades]. Las probabilidades pueden venir como
    # arreglo o como lista de diccionarios {clase: prob} segun el conversor.
    probas = salidas[1]
    if isinstance(probas, list):
        return np.array([p[1] for p in probas], dtype=float)
    return np.asarray(probas)[:, 1].astype(float)


class Modelo:
    """El artefacto cargado una sola vez, al arrancar el proceso."""

    def __init__(self, directorio: Path | None = None) -> None:
        directorio = Path(directorio) if directorio is not None else DIRECTORIO_MODELOS
        ruta_onnx = directorio / NOMBRE_ONNX
        ruta_meta = directorio / NOMBRE_METADATOS

        for ruta in (ruta_onnx, ruta_meta):
            if not ruta.exists():
                raise ContratoRoto(
                    f"falta {ruta.name} en {directorio}. El artefacto no se versiona: "
                    f"se regenera con `python -m src.models.exportar`."
                )

        self.ruta_onnx = ruta_onnx
        self.metadatos: dict = json.loads(ruta_meta.read_text(encoding="utf-8"))
        self.features: list[str] = list(self.metadatos["features_en_orden"])

        self.sesion = ort.InferenceSession(
            str(ruta_onnx), providers=["CPUExecutionProvider"]
        )

        self._verificar_ancho_de_entrada()
        self._verificar_paridad()
        self.puntos = self._leer_puntos()

    # -- verificaciones de arranque ------------------------------------------------

    def _verificar_ancho_de_entrada(self) -> None:
        forma = self.sesion.get_inputs()[0].shape
        ancho = forma[-1] if len(forma) >= 2 else None
        if isinstance(ancho, int) and ancho != len(self.features):
            raise ContratoRoto(
                f"el grafo espera {ancho} columnas y el sidecar declara "
                f"{len(self.features)} ({', '.join(self.features)}). El .onnx y su "
                f"metadata.json no son del mismo entrenamiento."
            )

    def _verificar_paridad(self) -> None:
        paridad = self.metadatos.get("paridad_onnx_vs_sklearn", {})
        if paridad.get("aceptable") is not True:
            raise ContratoRoto(
                "la paridad ONNX vs scikit-learn registrada no es aceptable "
                f"(desviacion maxima {paridad.get('desviacion_maxima')!r}). Servir esto "
                "seria servir un modelo distinto del que se evaluo."
            )

    def _leer_puntos(self) -> dict[float, PuntoDeOperacion]:
        curva = self.metadatos.get("umbral", {}).get("curva", [])
        puntos = {
            float(fila["sensibilidad_objetivo"]): PuntoDeOperacion(
                sensibilidad_objetivo=float(fila["sensibilidad_objetivo"]),
                umbral=float(fila["umbral"]),
                tasa_de_alertas_esperada=fila.get("tasa_de_alertas_esperada"),
            )
            for fila in curva
        }
        if not puntos:
            raise ContratoRoto("el sidecar no trae ningun punto de operacion en la curva")
        return puntos

    # -- uso -----------------------------------------------------------------------

    @property
    def sensibilidades_disponibles(self) -> list[float]:
        return sorted(self.puntos)

    def punto(self, sensibilidad: float) -> PuntoDeOperacion:
        """
        El umbral calibrado para una sensibilidad objetivo.

        Sólo se aceptan los puntos de la grilla publicada. Interpolar entre ellos daría un
        umbral que nunca se midió, con una tasa de alertas esperada inventada — y el punto
        de operación es justamente lo que define cuánto molesta el sistema.
        """
        try:
            return self.puntos[float(sensibilidad)]
        except KeyError:
            disponibles = ", ".join(str(s) for s in self.sensibilidades_disponibles)
            raise PuntoNoCalibrado(
                f"sensibilidad {sensibilidad} no esta calibrada; disponibles: {disponibles}"
            ) from None

    def predecir(self, valores: dict[str, float], sensibilidad: float) -> Prediccion:
        """
        `valores` se ordena según el sidecar, nunca según el orden en que vino el JSON.
        """
        faltantes = [f for f in self.features if f not in valores]
        if faltantes:
            raise ValueError(f"faltan features: {', '.join(faltantes)}")

        X = np.array([[float(valores[f]) for f in self.features]], dtype=float)
        probabilidad = float(_probabilidades(self.sesion, X)[0])

        punto = self.punto(sensibilidad)
        return Prediccion(
            probabilidad=probabilidad,
            alerta=probabilidad >= punto.umbral,
            punto=punto,
        )
