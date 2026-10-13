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
class Contribucion:
    """Cuánto empujó un parámetro, en log-odds, y hacia dónde."""

    parametro: str
    valor: float
    contribucion: float

    @property
    def direccion(self) -> str:
        if self.contribucion > 0:
            return "aumenta"
        if self.contribucion < 0:
            return "reduce"
        return "neutro"


@dataclass(frozen=True)
class Explicacion:
    """
    La descomposición exacta del logit (SCRUM-66).

    `contribuciones` viene ordenada por magnitud: lo primero de la lista es lo que más
    empujó la predicción. `reconstruye_la_probabilidad` es la verificación de que esta
    explicación describe el modelo que se está sirviendo y no una aproximación paralela —
    si diera False, la explicación estaría mintiendo y no hay que mostrarla.
    """

    intercepto: float
    contribuciones: list[Contribucion]
    logit: float
    probabilidad_reconstruida: float
    reconstruye_la_probabilidad: bool


@dataclass(frozen=True)
class Prediccion:
    probabilidad: float
    alerta: bool
    punto: PuntoDeOperacion
    explicacion: Explicacion | None


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
                    f"falta {ruta.name} en {directorio}. Los dos archivos del par estan "
                    f"versionados; si falta alguno se regeneran juntos con "
                    f"`python -m src.models.exportar`."
                )

        self.ruta_onnx = ruta_onnx
        self.metadatos: dict = json.loads(ruta_meta.read_text(encoding="utf-8"))
        self.features: list[str] = list(self.metadatos["features_en_orden"])
        # Ausente o `null` si el modelo dejó de ser lineal: ver `explicar`.
        self.explicabilidad: dict | None = self.metadatos.get("explicabilidad")

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

    def explicar(self, valores: dict[str, float]) -> Explicacion | None:
        """
        Descompone el logit parámetro por parámetro (SCRUM-66).

        Devuelve `None` cuando el sidecar no trae el bloque de explicabilidad, que es lo
        que pasa si el modelo deja de ser lineal. Antes de mostrar nada hay que mirar
        `reconstruye_la_probabilidad`: una explicación que no reproduce la probabilidad
        servida no describe a este modelo, y una explicación equivocada de una alerta
        clínica manda a enfermería a mirar el parámetro que no es.
        """
        bloque = self.explicabilidad
        if bloque is None:
            return None

        intercepto = float(bloque["intercepto"])
        coeficientes = bloque["coeficientes"]
        medias = bloque["escalado_media"]
        escalas = bloque["escalado_escala"]

        contribuciones = []
        for f in self.features:
            x = float(valores[f])
            escala = float(escalas[f]) or 1.0
            z = (x - float(medias[f])) / escala
            contribuciones.append(
                Contribucion(parametro=f, valor=x, contribucion=float(coeficientes[f]) * z)
            )

        contribuciones.sort(key=lambda c: abs(c.contribucion), reverse=True)

        logit = intercepto + sum(c.contribucion for c in contribuciones)
        reconstruida = float(1.0 / (1.0 + np.exp(-logit)))

        X = np.array([[float(valores[f]) for f in self.features]], dtype=float)
        servida = float(_probabilidades(self.sesion, X)[0])

        return Explicacion(
            intercepto=intercepto,
            contribuciones=contribuciones,
            logit=float(logit),
            probabilidad_reconstruida=reconstruida,
            # La tolerancia es la misma que la de la paridad ONNX: float32 tiene ~7
            # digitos y el grafo corre en float32.
            reconstruye_la_probabilidad=bool(abs(reconstruida - servida) < 1e-5),
        )

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
            explicacion=self.explicar(valores),
        )
