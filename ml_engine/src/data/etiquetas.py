"""
Definición de la etiqueta v2 (SCRUM-53).

QUÉ ES LA ETIQUETA
Para cada toma de signos vitales hecha en el instante `t`:

    y = 1  si el desenlace adverso del episodio ocurre en (t + 1 h, t + 24 h]
    y = 0  si no ocurre en ese intervalo
    (descartada)  si ocurre DENTRO de la primera hora

Tres decisiones, y las tres importan:

**1. El horizonte es de 24 h.** Alertar con más anticipación que eso deja de ser útil
   clínicamente: nadie sostiene una vigilancia reforzada durante dos días por una alerta.

**2. Hay una ventana ciega de 1 h, y las tomas que caen ahí se DESCARTAN, no se ponen
   en 0.** Es la decisión menos obvia y la más importante. Una toma hecha veinte minutos
   antes de que al paciente lo suban a terapia intensiva es trivial de clasificar —el
   deterioro ya es evidente en los propios signos vitales— y dejarla dentro inflaría
   cualquier métrica sin que el modelo haya aprendido nada. Peor: un modelo entrenado
   con esas filas aprende a *confirmar* el deterioro en curso, que es justo lo que NEWS2
   ya hace bien y no lo que este proyecto quiere aportar. Marcarlas como 0 sería todavía
   peor, porque sería enseñarle al modelo que un paciente que se está descompensando
   está sano.

**3. La etiqueta NO mira el NEWS2.** Se construye únicamente con `disposition` y los
   tiempos del episodio. Usar "NEWS2 >= 7" como etiqueta sería circular: el modelo
   aprendería a reproducir la escala que se quiere superar, y la comparativa de tasa de
   alertas (`SCRUM-58`) no significaría nada.

CAVEAT MEDIDO SOBRE EL DEMO — LEER ANTES DE INTERPRETAR CUALQUIER MÉTRICA
En el demo de 222 episodios el horizonte de 24 h **no discrimina prácticamente nada**:
la estadía mediana en guardia es de 5,8 h, sólo 6 episodios superan las 24 h, y apenas
**2 tomas de 749** quedan fuera del horizonte. Es decir que, con este dataset, la
etiqueta colapsa a *"¿este episodio terminó en internación?"* — una etiqueta a nivel de
episodio disfrazada de etiqueta a nivel de toma. La prevalencia resultante es del 66,8 %,
que no es una prevalencia clínica sino el reflejo de que el 67,6 % de los episodios del
demo terminan en ADMITTED.

La definición implementada acá es la correcta y es la que hay que usar; lo que no sirve
es el demo para medir con ella. Sobre la base completa de ~425.000 episodios, y sobre
todo en datos de sala general —donde la estadía se mide en días y no en horas—, el
horizonte sí separa. **Ninguna métrica de modelado calculada sobre el demo con esta
etiqueta es interpretable**, y eso hay que declararlo junto al caveat del ADR-006.

QUÉ CUENTA COMO DESENLACE ADVERSO
`disposition in {ADMITTED, EXPIRED}` al cierre del episodio, que es lo que define
`mimic_ed.DISPOSICIONES_ADVERSAS`. **Es un proxy, y conviene decirlo de frente:**
MIMIC-IV-ED registra el desenlace al final de la estadía en guardia, no un evento de
ingreso a UCI con su propia marca de tiempo. Por eso el instante del evento se toma como
`egreso_en`. Es la mejor aproximación disponible en este dataset y la limitación va
declarada en la tesis, igual que el caveat del ADR-006.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# El horizonte de predicción y la ventana ciega, en horas. Cambiar estos dos números
# cambia la definición del problema, no un detalle de implementación.
HORIZONTE_HORAS = 24
VENTANA_CIEGA_HORAS = 1


@dataclass
class ResumenEtiquetado:
    observaciones: int
    posteriores_al_evento: int
    en_ventana_ciega: int
    etiquetables: int
    positivas: int

    @property
    def prevalencia(self) -> float:
        return self.positivas / self.etiquetables if self.etiquetables else 0.0


def etiquetar(observaciones: pd.DataFrame, episodios: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega la etiqueta v2 a cada observación.

    Devuelve el DataFrame con tres columnas nuevas:

        horas_al_evento        horas entre la toma y el desenlace adverso (nulo si no hubo)
        posterior_al_evento    True si la toma quedó registrada DESPUÉS del egreso
        en_ventana_ciega       True si la toma cae en la última hora antes del evento
        y                      la etiqueta; nula en los dos casos anteriores

    No filtra nada: marca. Descartar acá escondería cuántas filas se pierden, y ese
    número es parte del resultado — se filtra al momento de entrenar.

    Los dos motivos de descarte se separan a propósito, porque no son lo mismo: la
    ventana ciega es una **decisión metodológica**, y las tomas posteriores al egreso son
    un **defecto del dato** (en el demo hay 65, alguna con 35 h de desfasaje). Mezclarlos
    en un solo contador escondería la calidad real del dataset.
    """
    evento = episodios.loc[
        episodios["desenlace_adverso"], ["episodio_id", "egreso_en"]
    ].rename(columns={"egreso_en": "evento_en"})

    df = observaciones.merge(evento, on="episodio_id", how="left")

    horas = (df["evento_en"] - df["medido_en"]).dt.total_seconds() / 3600
    df["horas_al_evento"] = horas.round(3)

    # Tomas registradas después del egreso: no es que el evento esté cerca, es que el
    # dato está mal. No se pueden usar para predecir nada.
    df["posterior_al_evento"] = horas.notna() & (horas < 0)

    # Ventana ciega: el evento ocurre dentro de la hora siguiente a la toma.
    df["en_ventana_ciega"] = horas.notna() & (horas >= 0) & (horas <= VENTANA_CIEGA_HORAS)

    positiva = horas.notna() & (horas > VENTANA_CIEGA_HORAS) & (horas <= HORIZONTE_HORAS)

    df["y"] = pd.array(positiva.astype("Int64"), dtype="Int64")
    df.loc[df["posterior_al_evento"] | df["en_ventana_ciega"], "y"] = pd.NA

    return df.drop(columns=["evento_en"])


def resumir(etiquetadas: pd.DataFrame) -> ResumenEtiquetado:
    return ResumenEtiquetado(
        observaciones=len(etiquetadas),
        posteriores_al_evento=int(etiquetadas["posterior_al_evento"].sum()),
        en_ventana_ciega=int(etiquetadas["en_ventana_ciega"].sum()),
        etiquetables=int(etiquetadas["y"].notna().sum()),
        positivas=int((etiquetadas["y"] == 1).sum()),
    )


def construir(procesados: Path) -> ResumenEtiquetado:
    """Lee los parquet de la tubería, etiqueta y escribe `observaciones_etiquetadas`."""
    observaciones = pd.read_parquet(procesados / "observaciones.parquet")
    episodios = pd.read_parquet(procesados / "episodios.parquet")

    etiquetadas = etiquetar(observaciones, episodios)

    # El mismo contrato de SCRUM-52, extendido con las columnas de la etiqueta.
    from ..validation import esquemas

    esquemas.validar(esquemas.OBSERVACIONES_ETIQUETADAS, etiquetadas, "etiquetado v2")

    etiquetadas.to_parquet(procesados / "observaciones_etiquetadas.parquet", index=False)
    return resumir(etiquetadas)


def main() -> None:
    raiz_ml = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Etiqueta v2 (SCRUM-53)")
    parser.add_argument(
        "--procesados",
        type=Path,
        default=raiz_ml / "data" / "processed" / "mimic-iv-ed-demo-2.2",
        help="Carpeta con observaciones.parquet y episodios.parquet",
    )
    args = parser.parse_args()

    r = construir(args.procesados)
    print(f"procesados : {args.procesados}")
    print(f"  observaciones               : {r.observaciones}")
    print(f"  descartadas, dato posterior : {r.posteriores_al_evento}")
    print(f"  descartadas, ventana ciega  : {r.en_ventana_ciega}")
    print(f"  etiquetables                : {r.etiquetables}")
    print(f"  positivas (y=1)             : {r.positivas}  ({r.prevalencia:.1%})")
    print()
    print("  Ojo: sobre el demo esta prevalencia NO es interpretable — la estadia")
    print("  mediana es de 5,8 h, asi que el horizonte de 24 h no separa nada y la")
    print("  etiqueta colapsa a 'el episodio termino en internacion'. Ver el modulo.")


if __name__ == "__main__":
    main()
