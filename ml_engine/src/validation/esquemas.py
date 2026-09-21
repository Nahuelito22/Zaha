"""
Validación estricta de la tubería de datos (SCRUM-52).

QUÉ HACE
Define el contrato de cada tabla que entra y sale de la tubería de ingesta, y lo hace
cumplir. Dos herramientas, cada una donde sirve:

    Pandera   valida TABLAS enteras: columnas, tipos, rangos e invariantes entre
              columnas. Es lo que corre en `mimic_ed.construir()`.
    Pydantic  valida UNA toma suelta. Es el contrato que después consume la API de
              inferencia (`SCRUM-62`), donde no hay DataFrame sino un JSON por request.

POR QUÉ ESTO EXISTE
La tubería ya limpiaba datos —anulaba valores imposibles, convertía Fahrenheit,
marcaba las tomas no puntuables—, pero nada verificaba que el resultado de esa limpieza
fuera el esperado. Si un cambio futuro rompiera la conversión de temperatura, o si la
base completa trajera una columna con otro tipo, el parquet se escribiría igual y el
error aparecería mucho más tarde, en la comparativa de tasa de alertas (`SCRUM-58`),
donde ya es casi imposible de rastrear.

La regla es la misma que la del Sprint 2: el modo de falla que hay que evitar no es el
que rompe, es el que sigue andando y miente. Un esquema que falla ruidosamente al
escribir el parquet es preferible a un número mal calculado que nadie cuestiona.

FUENTE ÚNICA DE LOS RANGOS
`RANGOS_PLAUSIBLES` vive acá y `mimic_ed` lo importa de este módulo. Antes estaba
definido en `mimic_ed`, y tener el rango en un solo lugar es justamente lo que evita
que la tubería y su validación se desincronicen. Estos valores tienen que seguir siendo
los mismos que los CHECK de la migración `20260521000000` y que `RANGOS` en
`app/clinical/src/lib/tipos.ts`.
"""

from __future__ import annotations

from typing import Optional, get_args

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaError, SchemaErrors
from pydantic import BaseModel, Field, model_validator

from ..data import news2

# =============================================================================
# Rangos de plausibilidad fisiológica — la fuente única del proyecto en Python.
# =============================================================================
RANGOS_PLAUSIBLES: dict[str, tuple[float, float]] = {
    "frecuencia_respiratoria": (0, 80),
    "spo2": (50, 100),
    "temperatura": (25, 45),
    "presion_sistolica": (30, 300),
    "frecuencia_cardiaca": (0, 300),
}

# Los 5 parámetros que MIMIC-IV-ED sí tiene. Los otros 2 se imputan (ADR-007).
PARAMETROS_MEDIDOS = list(RANGOS_PLAUSIBLES)

# NEWS2 va de 0 a 20: siete parámetros de 0 a 3 puntos, menos el techo real de la escala.
SCORE_MAXIMO = 20

# Los cuatro niveles, tomados del propio motor y no copiados a mano: `news2.NivelRiesgo`
# es la definición, y duplicar acá las cadenas sería crear una segunda fuente de verdad
# que puede desincronizarse en silencio — exactamente lo que este módulo existe para
# evitar. (La primera versión de este esquema las copió mal y la validación lo detectó
# en la primera corrida, que es la prueba de que el control sirve.)
NIVELES_RIESGO = list(get_args(news2.NivelRiesgo))


def _columna_medida(parametro: str) -> pa.Column:
    """Columna de un parámetro vital ya normalizado: flotante, nullable, en rango."""
    minimo, maximo = RANGOS_PLAUSIBLES[parametro]
    return pa.Column(
        float,
        checks=pa.Check.in_range(minimo, maximo),
        nullable=True,
        required=True,
        description=f"{parametro} en rango fisiológico plausible [{minimo}, {maximo}]",
    )


# =============================================================================
# Entrada: los CSV crudos de MIMIC-IV-ED.
#
# `strict=False` a propósito: los CSV traen más columnas de las que la tubería usa
# (dolor, nivel de triage, etc.) y no es tarea de este esquema prohibirlas. Lo que sí
# exige es que las columnas que la tubería LEE estén presentes. `coerce=False` porque
# acá el dato viene sucio por definición: la tubería lo limpia después, y forzar tipos
# antes de limpiar escondería exactamente lo que queremos ver.
# =============================================================================
VITALSIGN_CRUDO = pa.DataFrameSchema(
    {
        "stay_id": pa.Column(nullable=False),
        "subject_id": pa.Column(nullable=False),
        "charttime": pa.Column(nullable=True),
        "resprate": pa.Column(nullable=True),
        "o2sat": pa.Column(nullable=True),
        "temperature": pa.Column(nullable=True),
        "sbp": pa.Column(nullable=True),
        "heartrate": pa.Column(nullable=True),
    },
    strict=False,
    name="vitalsign (crudo)",
)

EDSTAYS_CRUDO = pa.DataFrameSchema(
    {
        "stay_id": pa.Column(nullable=False, unique=True),
        "subject_id": pa.Column(nullable=False),
        "intime": pa.Column(nullable=True),
        "outtime": pa.Column(nullable=True),
        "arrival_transport": pa.Column(nullable=True),
        "disposition": pa.Column(nullable=True),
    },
    strict=False,
    name="edstays (crudo)",
)


# =============================================================================
# Salida: las dos tablas que se escriben a parquet.
# =============================================================================
def _score_sii_puntuable(df: pd.DataFrame) -> bool:
    """
    Invariante central de la tubería: una toma tiene score si y solo si es puntuable.

    Si esto falla hay un score calculado sobre datos incompletos —que es justo lo que la
    interfaz de carga se niega a hacer— o una toma completa que quedó sin puntuar.
    """
    return bool((df["news2_score"].notna() == df["puntuable"]).all())


SCORE_SII_PUNTUABLE = pa.Check(
    _score_sii_puntuable,
    name="score_sii_puntuable",
    error="hay tomas puntuables sin score, o tomas con score que no son puntuables",
)


OBSERVACIONES = pa.DataFrameSchema(
    {
        "episodio_id": pa.Column(nullable=False),
        "paciente_id": pa.Column(nullable=False),
        "medido_en": pa.Column("datetime64[ns]", nullable=False),
        **{p: _columna_medida(p) for p in PARAMETROS_MEDIDOS},
        "valores_descartados": pa.Column(
            int,
            checks=pa.Check.in_range(0, len(PARAMETROS_MEDIDOS)),
            description="cuántos valores se anularon por imposibles en esta toma",
        ),
        "puntuable": pa.Column(bool, nullable=False),
        "news2_score": pa.Column(
            "Int64", checks=pa.Check.in_range(0, SCORE_MAXIMO), nullable=True
        ),
        "news2_riesgo": pa.Column(
            object, checks=pa.Check.isin(NIVELES_RIESGO), nullable=True
        ),
        # Estas tres van SIN dtype a propósito: en memoria son `object` (enteros y
        # booleanos mezclados con el nulo de las tomas no puntuables), pero al volver
        # del parquet pyarrow las devuelve como float64. Fijar el tipo haría que el
        # mismo dato fallara según por dónde entró, que es exactamente el tipo de
        # falsa alarma que vuelve inútil a un esquema. Lo que sí importa —el score, el
        # nivel de riesgo y `puntuable`— sigue tipado arriba.
        "news2_rojo_aislado": pa.Column(nullable=True),
        "news2_imputado": pa.Column(nullable=True),
        "news2_puntos_imputados": pa.Column(nullable=True),
    },
    checks=[SCORE_SII_PUNTUABLE],
    strict=False,  # las columnas sub_* se agregan dinámicamente desde news2.calcular
    name="observaciones",
)

EPISODIOS = pa.DataFrameSchema(
    {
        "episodio_id": pa.Column(nullable=False, unique=True),
        "paciente_id": pa.Column(nullable=False),
        "ingreso_en": pa.Column("datetime64[ns]", nullable=True),
        "egreso_en": pa.Column("datetime64[ns]", nullable=True),
        "llegada": pa.Column(object, nullable=True),
        "disposicion": pa.Column(object, nullable=True),
        "desenlace_adverso": pa.Column(bool, nullable=False),
        # Una estadía negativa sería un egreso anterior al ingreso. El techo de 30 días
        # es generoso a propósito: en guardia lo normal son horas, pero MIMIC tiene
        # estadías largas reales y no queremos rechazarlas, solo las imposibles.
        "horas_en_guardia": pa.Column(
            float, checks=pa.Check.in_range(0, 24 * 30), nullable=True
        ),
    },
    strict=False,
    name="episodios",
)


# =============================================================================
# La tabla etiquetada (SCRUM-53). Es `OBSERVACIONES` más las tres columnas de la
# etiqueta v2, y se construye a partir de aquélla para que no puedan divergir.
# =============================================================================
def _y_nula_sii_descartada(df: pd.DataFrame) -> bool:
    """
    La etiqueta falta exactamente en las filas descartadas, y en ninguna otra.

    Descartada es ventana ciega o dato posterior al egreso. Si esto falla, o se coló una
    fila sin etiquetar en el conjunto de entrenamiento, o se etiquetó una toma de la
    última hora antes del evento — que es justo la que hay que descartar para que el
    modelo no aprenda a confirmar lo obvio.
    """
    descartada = df["en_ventana_ciega"] | df["posterior_al_evento"]
    return bool((df["y"].isna() == descartada).all())


Y_NULA_SII_DESCARTADA = pa.Check(
    _y_nula_sii_descartada,
    name="y_nula_sii_descartada",
    error="la etiqueta y los motivos de descarte no se corresponden",
)

OBSERVACIONES_ETIQUETADAS = OBSERVACIONES.add_columns(
    {
        "horas_al_evento": pa.Column(
            float,
            nullable=True,
            description="horas entre la toma y el desenlace adverso; nulo si no hubo",
        ),
        "posterior_al_evento": pa.Column(bool, nullable=False),
        "en_ventana_ciega": pa.Column(bool, nullable=False),
        "y": pa.Column(
            "Int64",
            checks=pa.Check.isin([0, 1]),
            nullable=True,
            description="etiqueta v2; nula en las filas de ventana ciega",
        ),
    }
)
OBSERVACIONES_ETIQUETADAS.checks = [SCORE_SII_PUNTUABLE, Y_NULA_SII_DESCARTADA]
OBSERVACIONES_ETIQUETADAS.name = "observaciones etiquetadas"


# La misma tabla ya repartida en train/validación/prueba (SCRUM-54).
#
# El contrato NO puede expresar el invariante que importa —que un paciente no cruce
# particiones—, porque es una propiedad del conjunto y no de la fila. Eso lo verifica
# `particiones.auditar()`. Acá sólo se asegura que la columna exista y que no tenga
# valores inventados: una partición mal escrita mandaría filas a ninguna parte.
OBSERVACIONES_PARTICIONADAS = OBSERVACIONES_ETIQUETADAS.add_columns(
    {
        "particion": pa.Column(
            str,
            checks=pa.Check.isin(["entrenamiento", "validacion", "prueba"]),
            nullable=False,
            description="partición del experimento; se decide por paciente, nunca por fila",
        ),
    }
)
OBSERVACIONES_PARTICIONADAS.checks = [SCORE_SII_PUNTUABLE, Y_NULA_SII_DESCARTADA]
OBSERVACIONES_PARTICIONADAS.name = "observaciones particionadas"


# =============================================================================
# El contrato de UNA toma. Es lo que va a recibir la API de inferencia por JSON.
# =============================================================================
class TomaDeSignosVitales(BaseModel):
    """
    Una toma de signos vitales lista para puntuar.

    Los cinco parámetros medidos son obligatorios: un NEWS2 calculado sobre datos
    incompletos no es un NEWS2 válido, así que no se acepta la toma parcial. Los dos
    que MIMIC-IV-ED no tiene son opcionales y el motor los imputa al valor de menor
    riesgo, marcando la imputación (ADR-007).
    """

    model_config = {"extra": "forbid"}

    frecuencia_respiratoria: float = Field(ge=0, le=80)
    spo2: float = Field(ge=50, le=100)
    temperatura: float = Field(ge=25, le=45)
    presion_sistolica: float = Field(ge=30, le=300)
    frecuencia_cardiaca: float = Field(ge=0, le=300)

    consciencia: Optional[str] = Field(default=None)
    oxigeno_suplementario: Optional[bool] = Field(default=None)

    @model_validator(mode="after")
    def _consciencia_valida(self) -> "TomaDeSignosVitales":
        # AVPU + "alerta". La 'C' de confusión nueva puntúa igual que las tres peores
        # respuestas de la escala; omitirla haría que un paciente confundido puntuara 0.
        permitidas = {"A", "C", "V", "P", "U"}
        if self.consciencia is not None and self.consciencia.upper() not in permitidas:
            raise ValueError(
                f"consciencia debe ser una de {sorted(permitidas)}, no {self.consciencia!r}"
            )
        return self


# =============================================================================
# Helper
# =============================================================================
class ErrorDeEsquema(RuntimeError):
    """Falla de validación, con la etapa de la tubería donde ocurrió."""


def validar(esquema: pa.DataFrameSchema, df: pd.DataFrame, etapa: str) -> pd.DataFrame:
    """
    Valida `df` contra `esquema` y devuelve el DataFrame validado.

    `lazy=True` junta TODAS las fallas antes de levantar: si el esquema de la base
    completa no calza en cuatro columnas, conviene enterarse de las cuatro de una vez y
    no de a una por corrida.
    """
    try:
        return esquema.validate(df, lazy=True)
    except (SchemaError, SchemaErrors) as error:
        raise ErrorDeEsquema(
            f"La tabla no cumple el contrato en la etapa '{etapa}':\n{error}"
        ) from error
