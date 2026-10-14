"""
API de inferencia de Zaha (SCRUM-62).

QUÉ ES ESTE SERVICIO DENTRO DEL SISTEMA
Es un sidecar opcional. El puntaje NEWS2 se calcula en la base de datos y no pasa por
acá; este servicio sólo agrega la estimación del modelo. Si el proceso está caído, la
aplicación clínica pierde la predicción y conserva la escala — esa es la degradación
elegante de `SCRUM-65`, y es la razón por la que la API no tiene ningún endpoint que
calcule NEWS2: tenerlo invitaría a depender de él.

TRES DECISIONES QUE SE VEN EN EL CONTRATO

1. **El punto de operación viaja en cada respuesta.** El sidecar del modelo dice que
   elegir el umbral es una decisión clínica, no técnica: depende de cuántas alertas por
   turno tolera la guardia. Así que la respuesta nunca trae una alerta suelta; trae la
   alerta junto a la sensibilidad objetivo, el umbral y la tasa de alertas que hay que
   esperar. Y declara si esa sensibilidad la eligió quien llamó o si quedó el valor por
   defecto, para que "nadie la eligió" no se confunda con "alguien la eligió así".

2. **Los rangos fisiológicos se validan acá y son los mismos de la tubería.** Vienen de
   `src/rangos.py`, el mismo diccionario que usa la ingesta y que replican los CHECK de
   la base. Una SpO₂ de 10 % no es un paciente grave: es un error de registro, y el
   modelo le pondría una probabilidad alta con total seguridad.

3. **La advertencia sobre la evidencia viaja con el modelo.** `GET /modelo` devuelve el
   sidecar completo, con el intervalo de confianza que incluye el cero. Quien integre
   este servicio tiene que poder leer, sin buscarlo, que la reducción de alertas todavía
   no está demostrada.

Para levantarlo:

    cd ml_engine && .venv/Scripts/python -m uvicorn src.api.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .. import rangos
from . import modelo as cargador

SENSIBILIDAD_POR_DEFECTO = 0.70

_estado: dict[str, object] = {"modelo": None, "error": None}


def obtener_modelo() -> cargador.Modelo:
    m = _estado.get("modelo")
    if m is None:
        raise HTTPException(
            status_code=503,
            detail=f"el modelo no esta cargado: {_estado.get('error')}",
        )
    return m  # type: ignore[return-value]


def cargar_modelo() -> None:
    """
    Carga el artefacto una vez. Normalmente la llama el ciclo de vida.

    Es pública y separada porque esta API **también se monta como sub-aplicación** dentro
    del servidor de Gradio en el Space (ver `deploy/hf_space/app.py`), y Starlette no
    ejecuta el ciclo de vida de una aplicación montada: sin esto, `/salud` responderia
    `degradado` para siempre aunque el artefacto estuviera perfecto.

    Si falla, no levanta excepción. El proceso tiene que arrancar igual para que `/salud`
    pueda explicar la causa, en vez de un contenedor que reinicia en bucle sin decir nada.
    """
    try:
        _estado["modelo"] = cargador.Modelo()
        _estado["error"] = None
    except Exception as exc:  # noqa: BLE001 — se reporta por /salud
        _estado["modelo"] = None
        _estado["error"] = f"{type(exc).__name__}: {exc}"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """El artefacto se carga una vez al arrancar, no por pedido."""
    cargar_modelo()
    yield
    _estado["modelo"] = None


app = FastAPI(
    title="Zaha ML Engine API",
    description=(
        "Estimacion de deterioro clinico. NO calcula NEWS2: la escala es deterministica "
        "y se calcula en la base de datos."
    ),
    version="1.0.0",
    lifespan=ciclo_de_vida,
)


# -- esquemas ----------------------------------------------------------------------


def _rango(parametro: str) -> tuple[float, float]:
    return rangos.RANGOS_PLAUSIBLES[parametro]


class Observacion(BaseModel):
    """
    Una toma de signos vitales al pie de la cama.

    Los límites salen de `src/rangos.py`. No se aceptan valores fuera de rango ni se
    imputan: una medición imposible es un error de registro y tiene que volver como 422,
    no como una probabilidad.
    """

    frecuencia_respiratoria: Annotated[
        float, Field(ge=_rango("frecuencia_respiratoria")[0], le=_rango("frecuencia_respiratoria")[1])
    ]
    spo2: Annotated[float, Field(ge=_rango("spo2")[0], le=_rango("spo2")[1])]
    temperatura: Annotated[
        float, Field(ge=_rango("temperatura")[0], le=_rango("temperatura")[1])
    ]
    presion_sistolica: Annotated[
        float, Field(ge=_rango("presion_sistolica")[0], le=_rango("presion_sistolica")[1])
    ]
    frecuencia_cardiaca: Annotated[
        float, Field(ge=_rango("frecuencia_cardiaca")[0], le=_rango("frecuencia_cardiaca")[1])
    ]
    confusion: Annotated[
        int,
        Field(
            ge=0,
            le=1,
            description=(
                "La 'C' de NEWS2: confusion NUEVA, no un deterioro cronico previo. "
                "1 = confusion nueva."
            ),
        ),
    ]
    edad: Annotated[float, Field(ge=0, le=120)]


class PedidoDePrediccion(BaseModel):
    observacion: Observacion
    sensibilidad_objetivo: float | None = Field(
        default=None,
        description=(
            "Punto de operacion. Si se omite se usa 0.70 y la respuesta lo declara como "
            "valor por defecto. Solo se aceptan los puntos calibrados."
        ),
    )


class PuntoDeOperacionRespuesta(BaseModel):
    sensibilidad_objetivo: float
    umbral: float
    tasa_de_alertas_esperada: float | None
    elegido_por: Literal["cliente", "valor_por_defecto"]


class ContribucionRespuesta(BaseModel):
    parametro: str
    valor: float
    contribucion: float = Field(
        description="En log-odds. Positivo empuja hacia la alerta, negativo la aleja."
    )
    direccion: Literal["aumenta", "reduce", "neutro"]


class ExplicacionRespuesta(BaseModel):
    """
    La descomposición del logit, ordenada de mayor a menor influencia.

    `reconstruye_la_probabilidad` tiene que ser `true` para mostrarla. Si fuera `false`,
    la explicación no describe al modelo servido y mostrarla sería peor que no explicar
    nada: señalaría el parámetro equivocado en una alerta clínica.
    """

    exacta: Literal[True] = True
    intercepto: float
    contribuciones: list[ContribucionRespuesta]
    logit: float
    probabilidad_reconstruida: float
    reconstruye_la_probabilidad: bool


class RespuestaDePrediccion(BaseModel):
    probabilidad: float
    alerta: bool
    punto_de_operacion: PuntoDeOperacionRespuesta
    es_estimacion: Literal[True] = True
    explicacion: ExplicacionRespuesta | None = Field(
        default=None,
        description=(
            "Ausente si el modelo servido no admite descomposicion exacta. En ese caso no "
            "hay explicacion: no se sustituye por una aproximada."
        ),
    )
    advertencia: str


class RespuestaDeSalud(BaseModel):
    estado: Literal["ok", "degradado"]
    modelo_cargado: bool
    detalle: str | None = None


# -- endpoints ---------------------------------------------------------------------


# La salud vive SOLO en /salud. Antes estaba tambien en la raiz, y la raiz quedo
# reservada: en el Space, `deploy/hf_space/app.py` monta ahi la pantalla de demostracion,
# porque es lo que Hugging Face muestra en la pestaña App. Dejar un JSON de salud en la
# raiz haria que la Space se presentara como un volcado de texto.
@app.get("/salud", response_model=RespuestaDeSalud, tags=["salud"])
def salud() -> RespuestaDeSalud:
    """
    Responde 200 aunque el modelo no haya cargado.

    El cliente decide: `estado: degradado` significa "segui mostrando NEWS2 y no esperes
    prediccion". Un 503 acá haria que un orquestador reiniciara el contenedor en bucle
    por un problema que es del artefacto, no del proceso.
    """
    cargado = _estado.get("modelo") is not None
    return RespuestaDeSalud(
        estado="ok" if cargado else "degradado",
        modelo_cargado=cargado,
        detalle=None if cargado else str(_estado.get("error")),
    )


@app.get("/modelo", tags=["modelo"])
def describir_modelo() -> dict:
    """El sidecar completo: features, cohorte de entrenamiento, curva de umbrales y la advertencia."""
    return obtener_modelo().metadatos


@app.post("/prediccion", response_model=RespuestaDePrediccion, tags=["modelo"])
def predecir(pedido: PedidoDePrediccion) -> RespuestaDePrediccion:
    m = obtener_modelo()

    elegido_por: Literal["cliente", "valor_por_defecto"] = (
        "cliente" if pedido.sensibilidad_objetivo is not None else "valor_por_defecto"
    )
    sensibilidad = (
        pedido.sensibilidad_objetivo
        if pedido.sensibilidad_objetivo is not None
        else SENSIBILIDAD_POR_DEFECTO
    )

    try:
        resultado = m.predecir(pedido.observacion.model_dump(), sensibilidad)
    except cargador.PuntoNoCalibrado as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    explicacion = None
    if resultado.explicacion is not None:
        explicacion = ExplicacionRespuesta(
            intercepto=round(resultado.explicacion.intercepto, 6),
            contribuciones=[
                ContribucionRespuesta(
                    parametro=c.parametro,
                    valor=c.valor,
                    contribucion=round(c.contribucion, 6),
                    direccion=c.direccion,
                )
                for c in resultado.explicacion.contribuciones
            ],
            logit=round(resultado.explicacion.logit, 6),
            probabilidad_reconstruida=round(
                resultado.explicacion.probabilidad_reconstruida, 6
            ),
            reconstruye_la_probabilidad=resultado.explicacion.reconstruye_la_probabilidad,
        )

    return RespuestaDePrediccion(
        probabilidad=round(resultado.probabilidad, 6),
        alerta=resultado.alerta,
        punto_de_operacion=PuntoDeOperacionRespuesta(
            sensibilidad_objetivo=resultado.punto.sensibilidad_objetivo,
            umbral=resultado.punto.umbral,
            tasa_de_alertas_esperada=resultado.punto.tasa_de_alertas_esperada,
            elegido_por=elegido_por,
        ),
        explicacion=explicacion,
        advertencia=str(m.metadatos.get("advertencia", "")),
    )
