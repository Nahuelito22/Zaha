"""
Partición por paciente y control de fuga temporal (SCRUM-54).

QUÉ RESUELVE
Antes de entrenar cualquier cosa hay que decidir qué filas son de entrenamiento y cuáles
de prueba. Hacerlo mal no produce un error: produce métricas buenísimas y falsas. Este
módulo es la compuerta por la que pasa todo el modelado posterior (`SCRUM-56`, `57`).

POR QUÉ POR PACIENTE Y NUNCA POR FILA
Un mismo paciente aparece en varias tomas y en varios episodios. Si se parte al azar por
fila, tomas del mismo paciente —a veces del mismo episodio, separadas por minutos— caen
en entrenamiento y en prueba a la vez. El modelo entonces no generaliza a pacientes
nuevos: reconoce pacientes que ya vio. Es la fuga clásica de los datasets clínicos y
infla todas las métricas sin dejar rastro.

En el demo la magnitud es brutal: **222 episodios de apenas 64 pacientes**, y uno solo
tiene 23 episodios. Partir por episodio tampoco alcanza —un paciente con 23 episodios
cae seguro de los dos lados—, así que la unidad de partición es el `paciente_id` y
nada más chico.

POR QUÉ EL SPLIT NO ES TEMPORAL
Lo correcto en un problema de pronóstico suele ser entrenar con el pasado y evaluar con
el futuro. **Acá no se puede, y conviene explicar por qué antes de que un jurado lo
pregunte.** MIMIC-IV desidentifica corriendo las fechas de cada paciente a un offset
futuro distinto y aleatorio. Medido sobre el demo: los ingresos van de **2112 a 2201**,
89 años de rango, cuando la estadía mediana real es de 5,8 h. Esas fechas no son
comparables entre pacientes — el orden cronológico global es un artefacto de la
anonimización, no historia. Ordenar por `ingreso_en` y cortar produciría un split que
*parece* temporal y no lo es.

El tiempo sí es real **dentro** de un episodio, y ahí es donde hay que cuidarlo: eso es
lo que verifica `verificar_orden_temporal`, y es la precondición de las features de
ventana de `SCRUM-56`.

DETERMINISMO
La partición se deriva de un hash de `(semilla, paciente_id)`, no de un shuffle. Dos
corridas dan lo mismo sin depender de la versión de numpy ni del orden de las filas de
entrada. Una tesis que no reparte igual dos veces no se puede reproducir.

CAVEAT MEDIDO SOBRE EL DEMO
**60 de los 64 pacientes tienen algún desenlace adverso.** Quedan 4 pacientes negativos
para repartir entre tres particiones, así que ninguna partición de prueba del demo puede
tener una prevalencia interpretable. La estratificación está implementada y es correcta;
lo que no da es el demo. Es la misma limitación que ya declara `etiquetas.py`: el código
está listo para la base completa, y ninguna métrica sobre el demo se puede defender.
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Los nombres de las tres particiones. Son valores de datos, no de presentación: quedan
# escritos en el parquet y los leen el entrenamiento y la evaluación.
ENTRENAMIENTO = "entrenamiento"
VALIDACION = "validacion"
PRUEBA = "prueba"
PARTICIONES = (ENTRENAMIENTO, VALIDACION, PRUEBA)

PROPORCIONES_POR_DEFECTO = (0.70, 0.15, 0.15)

# Cambiar esta semilla reparte de nuevo a TODOS los pacientes. Queda versionada a
# propósito: es parte de la definición del experimento, no una preferencia local.
SEMILLA_POR_DEFECTO = "zaha-particion-v1"


@dataclass
class ResumenParticion:
    nombre: str
    pacientes: int
    episodios: int
    observaciones: int
    etiquetables: int
    positivas: int

    @property
    def prevalencia(self) -> float:
        return self.positivas / self.etiquetables if self.etiquetables else 0.0


@dataclass
class Violacion:
    """Una falla de integridad del split. `grave=True` invalida el experimento."""

    regla: str
    detalle: str
    grave: bool


def _rango_hash(semilla: str, paciente_id: object) -> float:
    """
    Mapea un paciente a un número estable en [0, 1).

    Se usa sha256 y no `hash()` de Python, que está aleatorizado por proceso
    (`PYTHONHASHSEED`) y daría una partición distinta en cada corrida.
    """
    digest = hashlib.sha256(f"{semilla}:{paciente_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def asignar_pacientes(
    pacientes: pd.DataFrame,
    proporciones: tuple[float, float, float] = PROPORCIONES_POR_DEFECTO,
    semilla: str = SEMILLA_POR_DEFECTO,
) -> pd.Series:
    """
    Reparte pacientes en las tres particiones, estratificando por desenlace.

    `pacientes` necesita dos columnas: `paciente_id` y `tuvo_desenlace_adverso`.
    Devuelve una Serie indexada por `paciente_id`.

    La estratificación se hace por paciente y no por toma: lo que se quiere es que las
    tres particiones tengan una mezcla parecida de pacientes que se deterioraron y
    pacientes que no. Dentro de cada estrato el corte es por el orden del hash, así que
    las proporciones salen exactas por estrato y el resultado no depende del orden de
    llegada de las filas.
    """
    if abs(sum(proporciones) - 1.0) > 1e-9:
        raise ValueError(f"Las proporciones tienen que sumar 1, suman {sum(proporciones)}")

    asignacion: dict[object, str] = {}

    for _, estrato in pacientes.groupby("tuvo_desenlace_adverso", dropna=False):
        ids = sorted(estrato["paciente_id"], key=lambda p: _rango_hash(semilla, p))
        total = len(ids)

        # round() y no int(): con estratos chicos, truncar siempre hacia abajo vacía
        # las particiones de validación y prueba.
        corte_entrenamiento = round(total * proporciones[0])
        corte_validacion = corte_entrenamiento + round(total * proporciones[1])

        for i, paciente_id in enumerate(ids):
            if i < corte_entrenamiento:
                asignacion[paciente_id] = ENTRENAMIENTO
            elif i < corte_validacion:
                asignacion[paciente_id] = VALIDACION
            else:
                asignacion[paciente_id] = PRUEBA

    return pd.Series(asignacion, name="particion")


def particionar(
    observaciones: pd.DataFrame,
    episodios: pd.DataFrame,
    proporciones: tuple[float, float, float] = PROPORCIONES_POR_DEFECTO,
    semilla: str = SEMILLA_POR_DEFECTO,
) -> pd.DataFrame:
    """
    Agrega la columna `particion` a cada observación, decidida por su paciente.

    El desenlace del paciente se lee de `episodios` y no de la etiqueta `y`, porque `y`
    es nula en las filas descartadas (ventana ciega y dato posterior al egreso) y un
    paciente cuyas tomas quedaron todas descartadas seguiría siendo un paciente que se
    deterioró. Estratificar sobre `y` lo contaría como negativo.
    """
    pacientes = (
        episodios.groupby("paciente_id")["desenlace_adverso"]
        .any()
        .rename("tuvo_desenlace_adverso")
        .reset_index()
    )

    asignacion = asignar_pacientes(pacientes, proporciones, semilla)

    df = observaciones.copy()
    df["particion"] = df["paciente_id"].map(asignacion)

    sin_asignar = int(df["particion"].isna().sum())
    if sin_asignar:
        raise ValueError(
            f"{sin_asignar} observaciones de pacientes que no están en episodios.parquet. "
            "Las dos tablas tienen que venir de la misma corrida de la tubería."
        )

    return df


def verificar_orden_temporal(observaciones: pd.DataFrame) -> list[Violacion]:
    """
    Verifica la precondición de cualquier feature de ventana (`SCRUM-56`).

    El tiempo entre pacientes es un artefacto de la anonimización, pero DENTRO de un
    episodio es real. Una feature de ventana calculada sobre tomas desordenadas mira al
    futuro sin que nada falle: un "promedio de las últimas 3 tomas" sobre una serie mal
    ordenada promedia tomas que todavía no ocurrieron.

    No verifica las tomas posteriores al egreso: eso ya lo marca `etiquetas.py` en
    `posterior_al_evento`, y son un defecto del dato, no del orden.
    """
    violaciones: list[Violacion] = []

    desordenados = (
        observaciones.groupby("episodio_id")["medido_en"]
        .apply(lambda s: not s.is_monotonic_increasing)
    )
    cuantos = int(desordenados.sum())
    if cuantos:
        violaciones.append(
            Violacion(
                regla="orden temporal dentro del episodio",
                detalle=(
                    f"{cuantos} episodios tienen sus tomas fuera de orden cronológico. "
                    "Ordenar por (episodio_id, medido_en) antes de armar ventanas."
                ),
                grave=True,
            )
        )

    return violaciones


def auditar(observaciones: pd.DataFrame) -> list[Violacion]:
    """
    Audita un DataFrame ya particionado. Lista vacía = el split se puede defender.

    Es deliberadamente una auditoría a posteriori y no una aserción dentro de
    `particionar`: el invariante tiene que poder verificarse sobre el parquet que
    realmente se entrenó, no sobre la buena intención del código que lo escribió.
    """
    violaciones: list[Violacion] = []

    # El invariante central. Si esto falla, todas las métricas están infladas.
    por_paciente = observaciones.groupby("paciente_id")["particion"].nunique()
    repetidos = por_paciente[por_paciente > 1]
    if len(repetidos):
        violaciones.append(
            Violacion(
                regla="un paciente, una sola partición",
                detalle=(
                    f"{len(repetidos)} pacientes aparecen en más de una partición: "
                    f"{sorted(repetidos.index)[:10]}. Hay fuga entre train y test."
                ),
                grave=True,
            )
        )

    # Implicado por lo anterior salvo que el dato esté roto: un mismo episodio_id
    # atribuido a dos pacientes distintos. Se chequea aparte porque el síntoma sería
    # idéntico y la causa, otra.
    por_episodio = observaciones.groupby("episodio_id")["particion"].nunique()
    partidos = por_episodio[por_episodio > 1]
    if len(partidos):
        violaciones.append(
            Violacion(
                regla="un episodio, una sola partición",
                detalle=(
                    f"{len(partidos)} episodios quedaron repartidos: "
                    f"{sorted(partidos.index)[:10]}. Revisar paciente_id en el crudo."
                ),
                grave=True,
            )
        )

    for nombre in PARTICIONES:
        if not (observaciones["particion"] == nombre).any():
            violaciones.append(
                Violacion(
                    regla="ninguna partición vacía",
                    detalle=f"La partición '{nombre}' quedó sin observaciones.",
                    grave=True,
                )
            )

    # Deriva de prevalencia: aviso, no falla. Con pocos pacientes es esperable, y
    # convertirlo en error haría que el demo no pasara nunca.
    resumenes = [r for r in resumir(observaciones) if r.etiquetables]
    if len(resumenes) > 1:
        prevalencias = [r.prevalencia for r in resumenes]
        deriva = max(prevalencias) - min(prevalencias)
        if deriva > 0.15:
            violaciones.append(
                Violacion(
                    regla="prevalencia comparable entre particiones",
                    detalle=(
                        f"La prevalencia varía {deriva:.1%} entre particiones "
                        f"({', '.join(f'{r.nombre} {r.prevalencia:.1%}' for r in resumenes)}). "
                        "Con pocos pacientes es esperable; sobre la base completa no."
                    ),
                    grave=False,
                )
            )

    return violaciones


def resumir(observaciones: pd.DataFrame) -> list[ResumenParticion]:
    return [
        ResumenParticion(
            nombre=nombre,
            pacientes=grupo["paciente_id"].nunique(),
            episodios=grupo["episodio_id"].nunique(),
            observaciones=len(grupo),
            etiquetables=int(grupo["y"].notna().sum()),
            positivas=int((grupo["y"] == 1).sum()),
        )
        for nombre in PARTICIONES
        if len(grupo := observaciones[observaciones["particion"] == nombre])
    ]


def construir(
    procesados: Path,
    proporciones: tuple[float, float, float] = PROPORCIONES_POR_DEFECTO,
    semilla: str = SEMILLA_POR_DEFECTO,
) -> tuple[list[ResumenParticion], list[Violacion]]:
    """Lee las observaciones etiquetadas, particiona, audita y escribe el parquet."""
    observaciones = pd.read_parquet(procesados / "observaciones_etiquetadas.parquet")
    episodios = pd.read_parquet(procesados / "episodios.parquet")

    particionadas = particionar(observaciones, episodios, proporciones, semilla)

    from ..validation import esquemas

    esquemas.validar(esquemas.OBSERVACIONES_PARTICIONADAS, particionadas, "partición")

    violaciones = verificar_orden_temporal(particionadas) + auditar(particionadas)

    # Un paciente puede tener episodio y ninguna toma de signos vitales. Se reparte
    # igual —el reparto es de pacientes, no de filas—, pero después no aparece en
    # ningún resumen, y entonces los totales no cierran contra episodios.parquet. En el
    # demo son 10 de 64. Es calidad del dato, no un error del split, pero si no se
    # declara parece un bug de conteo.
    sin_tomas = set(episodios["paciente_id"]) - set(particionadas["paciente_id"])
    if sin_tomas:
        violaciones.append(
            Violacion(
                regla="pacientes sin ninguna toma registrada",
                detalle=(
                    f"{len(sin_tomas)} de {episodios['paciente_id'].nunique()} pacientes "
                    "no tienen ni una observación de signos vitales, así que se reparten "
                    "pero no suman filas a ninguna partición."
                ),
                grave=False,
            )
        )

    # Se escribe igual: el parquet es el insumo de la auditoría, y esconderlo cuando
    # falla obligaría a adivinar qué se repartió mal. Lo que no se puede es entrenar
    # sobre él, y para eso está el código de salida del CLI.
    particionadas.to_parquet(procesados / "observaciones_particionadas.parquet", index=False)

    return resumir(particionadas), violaciones


def main() -> None:
    raiz_ml = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Partición por paciente (SCRUM-54)")
    parser.add_argument(
        "--procesados",
        type=Path,
        default=raiz_ml / "data" / "processed" / "mimic-iv-ed-demo-2.2",
    )
    parser.add_argument("--semilla", default=SEMILLA_POR_DEFECTO)
    args = parser.parse_args()

    resumenes, violaciones = construir(args.procesados, semilla=args.semilla)

    print(f"procesados : {args.procesados}")
    print(f"semilla    : {args.semilla}")
    print()
    print(f"  {'particion':<15} {'pac':>4} {'epis':>5} {'obs':>5} {'etiq':>5} {'y=1':>5}  prev")
    for r in resumenes:
        print(
            f"  {r.nombre:<15} {r.pacientes:>4} {r.episodios:>5} {r.observaciones:>5} "
            f"{r.etiquetables:>5} {r.positivas:>5}  {r.prevalencia:.1%}"
        )
    print()

    graves = [v for v in violaciones if v.grave]
    for v in violaciones:
        print(f"  [{'GRAVE' if v.grave else 'aviso'}] {v.regla}: {v.detalle}")
    if not violaciones:
        print("  Sin violaciones: ningun paciente cruza particiones.")

    if graves:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
