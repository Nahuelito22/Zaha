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
