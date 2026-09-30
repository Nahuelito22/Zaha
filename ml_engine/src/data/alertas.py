"""
La regla de alerta de NEWS2 y su tasa de referencia (SCRUM-80).

QUÉ RESUELVE
La tesis afirma *"igualo la sensibilidad de NEWS2 reduciendo la tasa de alertas"*. Para
que esa frase signifique algo hace falta un número contra el cual comparar, y ese número
tiene que salir **de la misma cohorte**, no de la literatura. El 37,6 alertas por 100
pacientes-día que se cita habitualmente se midió en **sala general** y sobre otra
población: comparar el modelo propio contra él sería comparar contra otra cosa.

LA DEFINICIÓN DE ALERTA NO ES "NEWS2 >= 5"
Es el error que este módulo existe para evitar. La regla que **realmente** dispara una
alerta en producción está en el trigger `emit_news2_alert` de la migración
`20260521000100_news2_engine.sql`, y es:

    risk_level IN ('Medio Bajo', 'Medio', 'Alto')

es decir, **cualquier nivel que no sea Bajo**. Eso incluye el caso del *rojo aislado*: un
solo parámetro en 3 puntos alerta aunque el score total sea bajo, porque un paciente con
una frecuencia respiratoria de 6 necesita que alguien lo mire ya, sume lo que sume el
resto. Es una decisión clínica de NEWS2, no un detalle de implementación.

Medido sobre el demo, la diferencia entre las dos definiciones **no es menor**:

    regla real del sistema (riesgo != Bajo)   62 de 553 tomas   11,2 %
    regla equivocada (score >= 5)             29 de 553 tomas    5,2 %

Más del doble. Una comparativa calibrada contra el 5,2 % estaría midiendo contra un NEWS2
que el sistema no implementa, y todo `SCRUM-58` quedaría mal anclado.

POR QUÉ HAY TRES DENOMINADORES Y NO UNO
- **Por toma**: es el único que no depende de cada cuánto se mide. Es el que debe usarse
  para la comparativa a sensibilidad igualada, porque el modelo puntúa las mismas tomas.
- **Por episodio**: responde "¿a qué fracción de pacientes el sistema le grita alguna
  vez?", que es la pregunta que hace un jefe de guardia.
- **Por 100 pacientes-día**: es el único comparable con la literatura, y **es el más
  engañoso de los tres**. Ver el caveat de `tasa()`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Espejo exacto del trigger `emit_news2_alert`. Si algún día cambia el trigger, cambia
# acá, y al revés: son la misma regla escrita dos veces porque viven en dos runtimes.
# Un desacuerdo entre ambas hace que la referencia de la tesis no describa al sistema.
RIESGOS_QUE_ALERTAN = ("Medio Bajo", "Medio", "Alto")

# La referencia de la literatura, para tenerla al lado del número propio. Medida en SALA
# GENERAL, no en guardia, y sobre otra población: NO es un objetivo ni un umbral, es
# contexto. Compararse contra ella directamente es justo lo que este módulo evita.
REFERENCIA_LITERATURA_POR_100_PACIENTE_DIA = 37.6


@dataclass
class TasaAlertas:
    tomas_puntuables: int
    tomas_con_alerta: int
    episodios_puntuables: int
    episodios_con_alerta: int
    episodios_totales: int
    pacientes_dia: float

    @property
    def por_toma(self) -> float:
        return self.tomas_con_alerta / self.tomas_puntuables if self.tomas_puntuables else 0.0

    @property
    def por_episodio(self) -> float:
        return (
            self.episodios_con_alerta / self.episodios_puntuables
            if self.episodios_puntuables
            else 0.0
        )

    @property
    def por_100_pacientes_dia(self) -> float:
        return 100 * self.tomas_con_alerta / self.pacientes_dia if self.pacientes_dia else 0.0

    @property
    def tomas_por_paciente_dia(self) -> float:
        """
        Frecuencia de medición **puntuable**. Sin esto, `por_100_pacientes_dia` no se
        interpreta: son las tomas que efectivamente pudieron disparar una alerta.
        """
        return self.tomas_puntuables / self.pacientes_dia if self.pacientes_dia else 0.0

    @property
    def episodios_sin_toma_puntuable(self) -> int:
        """
        Episodios que consumen tiempo de guardia sin que el sistema pueda evaluarlos.

        Entran en el denominador de `por_100_pacientes_dia` a propósito: representan
        tiempo real de paciente en el que NEWS2 no emitió nada porque no tenía con qué.
        Sacarlos subiría la tasa y describiría un sistema que no es el que se despliega.
        """
        return self.episodios_totales - self.episodios_puntuables


def marcar(observaciones: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega la columna `alerta` aplicando la regla real del sistema.

    Sólo las tomas puntuables pueden alertar: una toma sin los cinco parámetros no tiene
    NEWS2, y en producción tampoco dispararía nada porque el trigger corre sobre el score
    que la base calculó. Marcar una toma incompleta como "sin alerta" sería contarla en
    el denominador como si el sistema la hubiera evaluado y hubiera decidido callarse.
    """
    df = observaciones.copy()
    # `astype(bool)` no es cosmético: sobre una tabla vacía estas columnas quedan en
    # dtype object, y pandas interpreta una máscara object como una LISTA DE NOMBRES DE
    # COLUMNA en vez de como máscara booleana. El filtrado devuelve entonces un
    # DataFrame sin ninguna columna y el fallo aparece después, lejos de la causa.
    df["alerta"] = (
        df["puntuable"].astype(bool) & df["news2_riesgo"].isin(RIESGOS_QUE_ALERTAN)
    ).astype(bool)
    return df


def tasa(observaciones: pd.DataFrame, episodios: pd.DataFrame) -> TasaAlertas:
    """
    Calcula la tasa de alertas en los tres denominadores.

    CAVEAT del denominador por paciente-día, que hay que declarar siempre que se cite:
    **depende de cada cuánto se mide, no sólo de cuánto alerta NEWS2.** En guardia se
    controla mucho más seguido que en sala —en el demo son ~14 tomas por paciente-día,
    contra 2 a 4 en una sala con control cada 6 o 12 h—, así que la tasa por paciente-día
    sale inflada por la frecuencia antes de que NEWS2 haga nada. Citarla contra el 37,6 de
    la literatura sin decir esto es comparar dos cosas distintas y presentarlas como una.

    El denominador honesto para la comparativa de `SCRUM-58` es **por toma**: el modelo
    puntúa exactamente las mismas tomas que NEWS2, así que la frecuencia se cancela.

    Segunda asimetría, deliberada: `pacientes_dia` suma la estadía de **todos** los
    episodios, incluidos los que no tienen ni una toma puntuable, mientras que las
    alertas sólo pueden salir de los que sí. Es a propósito — ese tiempo es tiempo real
    de paciente en guardia durante el cual el sistema no emitió nada. Excluirlo subiría
    la tasa y describiría un sistema más ruidoso que el que se despliega.
    """
    marcadas = marcar(observaciones)
    puntuables = marcadas[marcadas["puntuable"].astype(bool)]

    por_episodio = puntuables.groupby("episodio_id")["alerta"].any()
    horas = episodios["horas_en_guardia"].dropna()

    return TasaAlertas(
        tomas_puntuables=len(puntuables),
        tomas_con_alerta=int(puntuables["alerta"].sum()),
        episodios_puntuables=len(por_episodio),
        episodios_con_alerta=int(por_episodio.sum()),
        episodios_totales=len(episodios),
        pacientes_dia=float(horas.sum() / 24),
    )


def desglose_rojo_aislado(observaciones: pd.DataFrame) -> pd.Series:
    """
    Qué parámetro dispara el rojo aislado, y cuántas veces.

    Interesa porque es la diferencia entre la regla real y "score >= 5": si el rojo
    aislado lo dispara mayormente un parámetro que en guardia se mide mal o falta mucho,
    esa fracción de las alertas es frágil y hay que decirlo.
    """
    rojos = observaciones[observaciones["puntuable"] & observaciones["news2_rojo_aislado"]]
    columnas = [c for c in rojos.columns if c.startswith("sub_") and c != "sub_consciencia"]

    conteo = {c.replace("sub_", ""): int((rojos[c] == 3).sum()) for c in columnas}
    serie = pd.Series(conteo, name="tomas con ese parámetro en 3")
    return serie[serie > 0].sort_values(ascending=False)


def construir(procesados: Path) -> TasaAlertas:
    observaciones = pd.read_parquet(procesados / "observaciones_particionadas.parquet")
    episodios = pd.read_parquet(procesados / "episodios.parquet")
    return tasa(observaciones, episodios)


def main() -> None:
    raiz_ml = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Tasa de alertas de referencia (SCRUM-80)")
    parser.add_argument(
        "--procesados",
        type=Path,
        default=raiz_ml / "data" / "processed" / "mimic-iv-ed-demo-2.2",
    )
    args = parser.parse_args()

    t = construir(args.procesados)
    print(f"procesados : {args.procesados}")
    print()
    print(f"  regla aplicada: riesgo in {RIESGOS_QUE_ALERTAN}")
    print(f"  (espejo del trigger emit_news2_alert; NO es 'score >= 5')")
    print()
    print(f"  por toma       : {t.tomas_con_alerta} de {t.tomas_puntuables}  ({t.por_toma:.1%})")
    print(
        f"  por episodio   : {t.episodios_con_alerta} de {t.episodios_puntuables}"
        f"  ({t.por_episodio:.1%})"
    )
    print(f"  por 100 pac-dia: {t.por_100_pacientes_dia:.1f}")
    print()
    print(f"  frecuencia de medicion: {t.tomas_por_paciente_dia:.1f} tomas puntuables por paciente-dia")
    print(f"  episodios sin ninguna toma puntuable: {t.episodios_sin_toma_puntuable}"
          f" de {t.episodios_totales} (cuentan en el denominador por paciente-dia)")
    print(f"  referencia de literatura (SALA, otra poblacion): "
          f"{REFERENCIA_LITERATURA_POR_100_PACIENTE_DIA}")
    print()
    print("  Ojo: la tasa por paciente-dia depende de cada cuanto se mide, no solo de")
    print("  cuanto alerta NEWS2. En guardia se mide mucho mas seguido que en sala, asi")
    print("  que ese numero sale inflado antes de que NEWS2 haga nada. Para la")
    print("  comparativa de SCRUM-58 el denominador honesto es POR TOMA.")


if __name__ == "__main__":
    main()


# =============================================================================
# Curva de operación — la primitiva de comparación de SCRUM-58
# =============================================================================
def curva_operacion(y: "pd.Series | np.ndarray", puntaje: "pd.Series | np.ndarray") -> pd.DataFrame:
    """
    Tasa de alertas y sensibilidad para cada umbral posible de `puntaje`.

    Es la forma honesta de comparar dos sistemas de alerta que no comparten escala: NEWS2
    puntúa 0-20 y un modelo devuelve una probabilidad entre 0 y 1, así que sus umbrales no
    se pueden comparar directamente. Lo que sí se compara es **a cuánta sensibilidad, a qué
    costo de alertas** llega cada uno.

    Devuelve una fila por umbral, ordenada de la más exigente a la más laxa.
    """
    import numpy as np

    y = np.asarray(y).astype(bool)
    puntaje = np.asarray(puntaje, dtype=float)

    # Se evalúan los umbrales que efectivamente cambian algo: los valores observados.
    umbrales = np.unique(puntaje)
    filas = []
    for u in umbrales:
        alerta = puntaje >= u
        filas.append(
            {
                "umbral": float(u),
                "tasa_alertas": float(alerta.mean()),
                "sensibilidad": float(alerta[y].mean()) if y.any() else float("nan"),
                "especificidad": float((~alerta[~y]).mean()) if (~y).any() else float("nan"),
            }
        )
    return pd.DataFrame(filas).sort_values("umbral", ascending=False).reset_index(drop=True)


def tasa_para_sensibilidad(
    curva: pd.DataFrame, objetivo: float, tolerancia: float = 1e-9
) -> float:
    """
    La tasa de alertas MÁS BARATA que alcanza al menos `objetivo` de sensibilidad.

    Es la comparación de `SCRUM-58` en una línea: fijada una sensibilidad, ¿cuántas alertas
    cuesta? Gana el sistema que devuelva el número más chico.

    `tolerancia` existe por una trampa real: la sensibilidad de NEWS2 sale de una división
    entera —29 de 54 es 0,537037…— y si el llamador pasa el valor redondeado a 0,537, la
    comparación `>=` descarta justo el umbral que empata y devuelve el siguiente, que es más
    caro. El sistema comparado quedaría injustamente favorecido. Con la tolerancia por
    defecto, un objetivo redondeado a 3 decimales sigue sin empatar; pasar el valor exacto
    es lo correcto, y la tolerancia cubre el error de punto flotante de ese valor exacto.

    Devuelve NaN si ningún umbral llega a esa sensibilidad — que es un resultado, no un
    error: significa que ese sistema no puede operar a esa sensibilidad.
    """
    alcanzan = curva[curva["sensibilidad"] >= objetivo - tolerancia]
    return float(alcanzan["tasa_alertas"].min()) if len(alcanzan) else float("nan")


def tasa_alertas_a_sensibilidad(
    y: "np.ndarray", puntaje: "np.ndarray", objetivo: float, tolerancia: float = 1e-9
) -> float:
    """
    Igual que `tasa_para_sensibilidad`, pero sin construir la curva intermedia.

    Existe por velocidad: el bootstrap de `SCRUM-58` la llama miles de veces, y armar un
    DataFrame por réplica hace que una simulación tarde horas en vez de segundos. Devuelve
    exactamente lo mismo que la versión sobre la curva, y hay una prueba que lo verifica.
    """
    import numpy as np

    y = np.asarray(y).astype(bool)
    puntaje = np.asarray(puntaje, dtype=float)

    orden = np.argsort(-puntaje, kind="stable")
    y_ord, p_ord = y[orden], puntaje[orden]

    positivos = y_ord.sum()
    if positivos == 0:
        return float("nan")

    sensibilidad = np.cumsum(y_ord) / positivos
    # Sólo se puede cortar DESPUÉS del último elemento de cada valor repetido: un umbral
    # no puede separar dos pacientes con el mismo puntaje.
    ultimo_del_empate = np.r_[p_ord[1:] != p_ord[:-1], True]

    alcanza = (sensibilidad >= objetivo - tolerancia) & ultimo_del_empate
    if not alcanza.any():
        return float("nan")
    return float((np.argmax(alcanza) + 1) / len(y_ord))


# El rango de sensibilidad sobre el que se compara. No es un punto único a propósito: ver
# `reduccion_relativa`.
GRILLA_SENSIBILIDAD = (0.50, 0.60, 0.70, 0.80)


def reduccion_relativa(
    y: "np.ndarray",
    puntaje_rival: "np.ndarray",
    puntaje_propio: "np.ndarray",
    grilla: "tuple[float, ...]" = GRILLA_SENSIBILIDAD,
    remuestreos: int = 3000,
    semilla: int = 20260930,
) -> "tuple[float, float, float]":
    """
    Reducción relativa media de la tasa de alertas sobre un RANGO de sensibilidades.

    POR QUÉ UN RANGO Y NO UN PUNTO — es la decisión metodológica de `SCRUM-58`.
    El score de NEWS2 es entero y tiene pocos niveles efectivos, así que su curva de
    operación avanza a **escalones grandes**. Comparar en una sensibilidad única cae, según
    la suerte, justo antes o justo después de un escalón, y el resultado se mueve muchísimo:
    medido sobre esta cohorte, en el punto en que opera hoy el sistema la reducción da
    +2,7 %, mientras que el promedio sobre 50-80 % da +29,8 %. **No es que un número sea el
    bueno y el otro el malo: es que el punto único no es un estimador estable** cuando el
    rival es discreto.

    El rango 50-80 % no es arbitrario: por debajo del 50 % una escala de alerta temprana no
    cumple su función, y por encima del 80 % la tasa de alertas se dispara hasta volverse
    inaplicable en una guardia real.

    Devuelve (reducción media, límite inferior, límite superior) del bootstrap al 95 %.
    """
    import numpy as np

    y = np.asarray(y).astype(bool)
    puntaje_rival = np.asarray(puntaje_rival, dtype=float)
    puntaje_propio = np.asarray(puntaje_propio, dtype=float)

    def media(indices: "np.ndarray") -> float:
        yy = y[indices]
        reducciones = []
        for objetivo in grilla:
            a = tasa_alertas_a_sensibilidad(yy, puntaje_rival[indices], objetivo)
            b = tasa_alertas_a_sensibilidad(yy, puntaje_propio[indices], objetivo)
            if a and a == a and b == b:
                reducciones.append(1 - b / a)
        return float(np.mean(reducciones)) if reducciones else float("nan")

    puntual = media(np.arange(len(y)))

    rng = np.random.default_rng(semilla)
    replicas = np.array(
        [media(rng.integers(0, len(y), len(y))) for _ in range(remuestreos)]
    )
    validas = replicas[~np.isnan(replicas)]
    if len(validas) < remuestreos * 0.5:
        return puntual, float("nan"), float("nan")

    return puntual, float(np.percentile(validas, 2.5)), float(np.percentile(validas, 97.5))
