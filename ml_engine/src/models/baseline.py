"""
Baseline XGBoost sobre el snapshot de admisión (SCRUM-56).

QUÉ ES
El modelo que, según el ADR-005, es el principal: gradient boosting sobre el *snapshot* de
signos vitales, no sobre la serie temporal. La literatura muestra que iguala a LSTM y
Transformers sobre series de 48 h, y es órdenes de magnitud más barato de servir.

Se entrena sobre la cohorte TRIAGE (ADR-009), que es donde el desenlace es real y por lo
tanto donde la comparación contra NEWS2 significa algo.

LAS FEATURES SON SOLO LAS QUE HAY AL PIE DE LA CAMA — y esto no es negociable
El archivo de TRIAGE trae biomarcadores inflamatorios (procalcitonina, MR-proADM) que son
justamente lo que el estudio original quería evaluar, y que **mejorarían el modelo**. Están
deliberadamente excluidos, por dos razones que se sostienen solas:

1. **El sistema no los tiene.** Una enfermera cargando una toma en `/app` ingresa siete
   signos vitales, no una procalcitonina. Un modelo entrenado con biomarcadores no se puede
   desplegar en Zaha: sería un resultado de papel.
2. **La comparación sería tramposa.** NEWS2 usa únicamente signos vitales. Darle al modelo
   propio información que el rival no tiene y después anunciar que le gana no prueba nada
   sobre el modelo; prueba que los biomarcadores informan, que ya se sabía.

Las features son exactamente lo que `vital_records` guarda, más la edad. Esa restricción
hace al resultado **desplegable y defendible**, no más débil.

POR QUÉ VALIDACIÓN CRUZADA Y NO UN SPLIT ÚNICO
Hay **54 muertes en 1.303 pacientes**. Un test del 15 % contendría unas 8 muertes, y una
sensibilidad estimada sobre 8 eventos tiene un intervalo de confianza de ±17 puntos: con
eso no se puede afirmar nada. La validación cruzada estratificada usa cada paciente una vez
como evaluación y da un estimador con varianza mucho menor.

`particiones.py` (SCRUM-54) sigue siendo la herramienta correcta para MIMIC, donde hay
miles de pacientes y un paciente aparece en varias filas. **Acá no hace falta y no aplica**:
hay exactamente una fila por paciente, así que no existe la fuga que ese módulo previene.
La estratificación por desenlace sí se mantiene.

HALLAZGO QUE CONTRADICE AL ADR-005 — leer antes de tocar los hiperparámetros
Con **54 eventos**, el modelo más simple es el mejor. Medido con CV repetida:

    XGBoost 300 árboles, profundidad 3    AUROC 0,613   <- sobreajusta feo
    XGBoost  60 árboles, profundidad 2    AUROC 0,728
    XGBoost  30 árboles, profundidad 1    AUROC 0,733
    Regresión logística (sin ajustar)     AUROC 0,759
    NEWS2 (el rival)                      AUROC 0,728

El ADR-005 da por sentado que XGBoost sobre snapshot es el modelo principal, y a este
tamaño de muestra **no lo es**: hay que bajarle la capacidad hasta casi nada para que
empate con NEWS2, mientras que una regresión logística sin ajustar le gana.

Y hay una asimetría que conviene explicitar, porque si no el resultado se lee al revés:
**NEWS2 no se ajustó sobre estos datos**, así que su 0,728 es insesgado, mientras que
cualquier configuración elegida mirando el CV está inflada. Un modelo que sólo *empata* con
NEWS2 después de ajustarlo es, en realidad, **peor** que NEWS2. Por eso el estimador que
este módulo reporta sale de **CV anidada**: la selección de modelo ocurre dentro del bucle,
sobre datos que la evaluación no ve.

La lectura para la tesis: a este tamaño, **el cuello de botella no es la capacidad del
modelo sino el volumen de datos**. Que es exactamente lo que la base completa de MIMIC
(`SCRUM-48`) resuelve.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold

# Exactamente lo que el sistema tiene cuando una enfermera termina de cargar una toma.
# Cambiar esta lista cambia qué significa el resultado: ver el encabezado del módulo.
FEATURES = [
    "frecuencia_respiratoria",
    "spo2",
    "temperatura",
    "presion_sistolica",
    "frecuencia_cardiaca",
    "confusion",  # derivada de `consciencia`; es la "C" de NEWS2
    "edad",
]

# Los biomarcadores del estudio original, excluidos a propósito. Se nombran acá para que
# quede registro de que la exclusión es una decisión y no un olvido.
EXCLUIDAS_POR_NO_ESTAR_AL_PIE_DE_LA_CAMA = ("MR-proADM", "PCT")

SEMILLA = 20260930


@dataclass
class ResultadoCV:
    evento: str
    n: int
    eventos: int
    puntajes: np.ndarray = field(repr=False)
    y: np.ndarray = field(repr=False)
    repeticiones: int = 1
    modelo: str = "?"
    # Qué familia eligió cada fold externo en la CV anidada. Si los folds no coinciden,
    # la elección es inestable y eso también es un resultado que hay que reportar.
    elegidos: list[str] = field(default_factory=list)

    @property
    def prevalencia(self) -> float:
        return self.eventos / self.n if self.n else 0.0


def matriz(df: pd.DataFrame) -> pd.DataFrame:
    """
    Arma la matriz de features desde la tabla normalizada de TRIAGE.

    `confusion` se reconstruye desde `consciencia` en vez de leerse del crudo, para que la
    feature sea exactamente la misma que el motor NEWS2 usó: si un día cambiara el mapeo,
    el modelo y la escala seguirían viendo lo mismo.
    """
    X = df[[c for c in FEATURES if c != "confusion"]].copy()
    X["confusion"] = (df["consciencia"] == "C").astype(int)
    return X[FEATURES]


def _xgb(semilla: int, escala: float, n: int, profundidad: int, lr: float):
    from xgboost import XGBClassifier

    return XGBClassifier(
        n_estimators=n, max_depth=profundidad, learning_rate=lr,
        subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0,
        # El desenlace es raro (4,2 %). Sin esto el modelo aprende a decir "no" siempre,
        # que acierta el 96 % y no sirve para nada — es la razón por la que el proyecto
        # prohíbe reportar accuracy.
        scale_pos_weight=escala,
        eval_metric="logloss", random_state=semilla, n_jobs=2,
    )


def _logistica(semilla: int, escala: float):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(
        SimpleImputer(),
        StandardScaler(),
        # `class_weight` cumple el mismo papel que `scale_pos_weight` en XGBoost.
        LogisticRegression(max_iter=2000, class_weight="balanced", random_state=semilla),
    )


# El catálogo que la CV anidada recorre en su bucle interno. Se incluye la regresión
# logística a propósito: el ADR-005 supone que gana XGBoost, y a este tamaño de muestra no
# es cierto. Dejar competir al modelo simple es lo que permitió descubrirlo.
MODELOS = {
    "logistica": lambda sem, esc: _logistica(sem, esc),
    "xgb_1": lambda sem, esc: _xgb(sem, esc, n=30, profundidad=1, lr=0.10),
    "xgb_2": lambda sem, esc: _xgb(sem, esc, n=60, profundidad=2, lr=0.05),
    "xgb_3": lambda sem, esc: _xgb(sem, esc, n=300, profundidad=3, lr=0.05),
}


def evaluar_cv(
    df: pd.DataFrame,
    evento: str = "muerte_30d",
    modelo: str = "logistica",
    n_splits: int = 5,
    repeticiones: int = 5,
    semilla: int = SEMILLA,
) -> ResultadoCV:
    """
    Puntajes fuera de fold de UN modelo fijo, promediados sobre varias repeticiones.

    Sirve para explorar y comparar familias. **No** es el estimador que va a la tesis: elegir
    el mejor de estos números es selección sobre la evaluación, y queda inflado. Para el
    número defendible, `evaluar_anidada`.
    """
    X = matriz(df).to_numpy(dtype=float)
    y = df[evento].to_numpy().astype(int)

    acumulado = np.zeros(len(y), dtype=float)
    cv = RepeatedStratifiedKFold(
        n_splits=n_splits, n_repeats=repeticiones, random_state=semilla
    )

    for entrena, evalua in cv.split(X, y):
        escala = (len(entrena) - y[entrena].sum()) / max(y[entrena].sum(), 1)
        m = MODELOS[modelo](semilla, escala)
        m.fit(X[entrena], y[entrena])
        acumulado[evalua] += m.predict_proba(X[evalua])[:, 1]

    return ResultadoCV(
        evento=evento, n=len(y), eventos=int(y.sum()),
        puntajes=acumulado / repeticiones, y=y, repeticiones=repeticiones,
        modelo=modelo,
    )


def evaluar_anidada(
    df: pd.DataFrame,
    evento: str = "muerte_30d",
    n_externo: int = 5,
    n_interno: int = 4,
    semilla: int = SEMILLA,
) -> ResultadoCV:
    """
    El estimador honesto: la SELECCIÓN de modelo ocurre dentro del bucle de evaluación.

    En cada fold externo se elige la familia con mejor AUROC en una CV interna hecha
    **solo** sobre los datos de entrenamiento de ese fold, y recién entonces se puntúa el
    fold externo, que ningún paso vio. Así el número mide *el procedimiento completo* —
    incluida la decisión de qué modelo usar— y no una configuración elegida a posteriori.

    Sin esto, comparar contra NEWS2 sería injusto en favor del modelo: NEWS2 no se ajustó
    sobre estos datos, así que su AUROC es insesgado.
    """
    from sklearn.metrics import roc_auc_score

    X = matriz(df).to_numpy(dtype=float)
    y = df[evento].to_numpy().astype(int)

    puntajes = np.zeros(len(y), dtype=float)
    elegidos: list[str] = []

    externo = StratifiedKFold(n_splits=n_externo, shuffle=True, random_state=semilla)
    for entrena, evalua in externo.split(X, y):
        X_tr, y_tr = X[entrena], y[entrena]

        mejor, mejor_auc = None, -np.inf
        interno = StratifiedKFold(n_splits=n_interno, shuffle=True, random_state=semilla)
        for nombre in MODELOS:
            fuera = np.zeros(len(y_tr), dtype=float)
            for i_tr, i_ev in interno.split(X_tr, y_tr):
                escala = (len(i_tr) - y_tr[i_tr].sum()) / max(y_tr[i_tr].sum(), 1)
                m = MODELOS[nombre](semilla, escala)
                m.fit(X_tr[i_tr], y_tr[i_tr])
                fuera[i_ev] = m.predict_proba(X_tr[i_ev])[:, 1]
            auc = roc_auc_score(y_tr, fuera)
            if auc > mejor_auc:
                mejor, mejor_auc = nombre, auc

        elegidos.append(mejor)
        escala = (len(entrena) - y_tr.sum()) / max(y_tr.sum(), 1)
        final = MODELOS[mejor](semilla, escala)
        final.fit(X_tr, y_tr)
        puntajes[evalua] = final.predict_proba(X[evalua])[:, 1]

    return ResultadoCV(
        evento=evento, n=len(y), eventos=int(y.sum()),
        puntajes=puntajes, y=y, repeticiones=1,
        modelo="anidada", elegidos=elegidos,
    )


def entrenar(
    df: pd.DataFrame,
    evento: str = "muerte_30d",
    modelo: str = "logistica",
    semilla: int = SEMILLA,
):
    """
    Entrena sobre TODOS los datos. Para exportar (`SCRUM-59`), nunca para evaluar.

    El default es `logistica` porque es lo que eligen los 5 folds de `evaluar_anidada`
    a este tamaño de muestra (ADR-010). No está fijado por decreto: si con más eventos
    la CV anidada pasara a elegir otra familia, se cambia acá el default y se reexporta.
    """
    X = matriz(df).to_numpy(dtype=float)
    y = df[evento].to_numpy().astype(int)
    escala = (len(y) - y.sum()) / max(y.sum(), 1)
    estimador = MODELOS[modelo](semilla, escala)
    estimador.fit(X, y)
    return estimador


def construir(procesados: Path, evento: str = "muerte_30d") -> ResultadoCV:
    df = pd.read_parquet(procesados / "triage.parquet")
    return evaluar_cv(df[df["puntuable"]], evento=evento)


def intervalo_reduccion(
    y: np.ndarray,
    puntaje_modelo: np.ndarray,
    puntaje_news2: np.ndarray,
    sensibilidad_objetivo: float,
    remuestreos: int = 2000,
    semilla: int = SEMILLA,
) -> tuple[float, float, float]:
    """
    Intervalo bootstrap del 95 % para la reducción relativa de alertas.

    Por qué hace falta y no es adorno: la sensibilidad objetivo se estima sobre **54
    eventos**. Un punto porcentual de esa curva se mueve casi 2 puntos con que un solo
    paciente cambie de lado. Publicar "14,4 % menos alertas" sin intervalo sería dar
    precisión falsa sobre una muestra que no la tiene.

    Se remuestrea por paciente, recalculando ambas curvas en cada réplica: el intervalo
    recoge la incertidumbre de las dos, no sólo la del modelo.

    Devuelve (reducción puntual, límite inferior, límite superior). Una réplica donde algún
    sistema no alcanza la sensibilidad objetivo aporta NaN y se descarta, y cuántas se
    descartaron importa: si son muchas, el punto de operación está al borde de lo que la
    muestra puede sostener.
    """
    from ..data import alertas

    def reduccion(indices: np.ndarray) -> float:
        yy = y[indices]
        if yy.sum() == 0:
            return float("nan")
        a = alertas.tasa_para_sensibilidad(
            alertas.curva_operacion(yy, puntaje_news2[indices]), sensibilidad_objetivo
        )
        b = alertas.tasa_para_sensibilidad(
            alertas.curva_operacion(yy, puntaje_modelo[indices]), sensibilidad_objetivo
        )
        return 1 - b / a if a and a == a and b == b else float("nan")

    puntual = reduccion(np.arange(len(y)))

    rng = np.random.default_rng(semilla)
    replicas = np.array(
        [reduccion(rng.integers(0, len(y), len(y))) for _ in range(remuestreos)]
    )
    validas = replicas[~np.isnan(replicas)]
    if len(validas) < remuestreos * 0.5:
        return puntual, float("nan"), float("nan")

    return puntual, float(np.percentile(validas, 2.5)), float(np.percentile(validas, 97.5))


def main() -> None:
    from sklearn.metrics import roc_auc_score

    from ..data import alertas

    raiz_ml = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Baseline sobre el snapshot (SCRUM-56)")
    parser.add_argument(
        "--procesados",
        type=Path,
        default=raiz_ml / "data" / "processed" / "triage-zenodo",
    )
    parser.add_argument(
        "--evento", default="muerte_30d", choices=["muerte_30d", "ingreso_uci"]
    )
    args = parser.parse_args()

    df = pd.read_parquet(args.procesados / "triage.parquet")
    df = df[df["puntuable"]]

    r = evaluar_anidada(df, evento=args.evento)
    news2_score = df["news2_score"].astype(int)

    print(f"cohorte  : {args.procesados}")
    print(f"evento   : {r.evento}   ({r.eventos} de {r.n}, {r.prevalencia:.1%})")
    print(f"features : {', '.join(FEATURES)}")
    print("           (biomarcadores excluidos: no estan al pie de la cama)")
    print()
    print(f"  AUROC modelo (CV anidada, insesgado) : {roc_auc_score(r.y, r.puntajes):.3f}")
    print(f"  AUROC NEWS2  (sin ajustar aca)       : {roc_auc_score(r.y, news2_score):.3f}")
    print(f"  familia elegida por fold             : {', '.join(r.elegidos)}")
    print()

    curva_news2 = alertas.curva_operacion(r.y, news2_score)
    curva_modelo = alertas.curva_operacion(r.y, r.puntajes)

    print("  TASA DE ALERTAS NECESARIA PARA CADA SENSIBILIDAD")
    print(f"  {'sensibilidad':>12}  {'NEWS2':>8}  {'modelo':>8}  {'diferencia':>11}")
    for objetivo in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        a = alertas.tasa_para_sensibilidad(curva_news2, objetivo)
        b = alertas.tasa_para_sensibilidad(curva_modelo, objetivo)
        marca = "" if not (a == a and b == b) else ("  modelo" if b < a else "  NEWS2")
        print(f"  {objetivo:>11.0%}  {a:>8.1%}  {b:>8.1%}  {b - a:>+10.1%}{marca}")
    print()

    # El punto que importa: la sensibilidad a la que opera HOY el sistema desplegado.
    alerta_sistema = df["news2_riesgo"].isin(alertas.RIESGOS_QUE_ALERTAN).to_numpy()
    sens_desplegada = float(alerta_sistema[r.y.astype(bool)].mean())
    tasa_desplegada = float(alerta_sistema.mean())

    # DOS rivales, y hay que mirar el segundo. La regla desplegada es la mas debil de las
    # dos formas de usar NEWS2; el mejor umbral de score le gana. Comparar contra la regla
    # desplegada da un numero mas lindo y es el rival equivocado.
    tasa_news2_mejor = alertas.tasa_para_sensibilidad(curva_news2, sens_desplegada)
    tasa_modelo = alertas.tasa_para_sensibilidad(curva_modelo, sens_desplegada)

    print(f"  A LA SENSIBILIDAD EN QUE OPERA HOY EL SISTEMA ({sens_desplegada:.1%})")
    print(f"    NEWS2, regla desplegada    : {tasa_desplegada:.1%} de alertas  (rival debil)")
    print(f"    NEWS2, mejor umbral        : {tasa_news2_mejor:.1%} de alertas  (rival REAL)")
    print(f"    modelo                     : {tasa_modelo:.1%} de alertas")
    print()

    puntual, lo, hi = intervalo_reduccion(
        r.y, r.puntajes, news2_score.to_numpy(), sens_desplegada
    )
    print(f"    Reduccion contra el rival real: {puntual:+.1%}")
    print(f"    IC 95% bootstrap              : [{lo:+.1%}, {hi:+.1%}]")
    print()
    if lo < 0 < hi:
        print("    EL INTERVALO CRUZA EL CERO: con 54 eventos la reduccion de alertas NO")
        print("    esta demostrada, aunque el AUROC del modelo sea mejor. No es un problema")
        print("    de capacidad del modelo sino de cuantos eventos tiene la cohorte. Es el")
        print("    argumento concreto para necesitar la base completa de MIMIC (SCRUM-48).")


if __name__ == "__main__":
    main()
