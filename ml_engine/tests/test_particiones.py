"""
Pruebas de la partición por paciente (SCRUM-54).

Lo que se verifica es el invariante que no tiene síntoma: que ningún paciente cruce de
entrenamiento a prueba. Un split con fuga no falla, no avisa y no se ve — produce
métricas altas y falsas, y el error recién aparece cuando el modelo se usa con pacientes
de verdad.

    cd ml_engine && python -m pytest tests/test_particiones.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && python tests/test_particiones.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.data import particiones  # noqa: E402

INICIO = pd.Timestamp("2112-09-17 10:00")


def _datos(episodios_por_paciente: dict[int, int], adversos: set[int] | None = None):
    """
    Arma un par (observaciones, episodios) sintético.

    `episodios_por_paciente` mapea paciente_id -> cuántos episodios tiene. Cada episodio
    lleva 3 tomas. `adversos` son los pacientes cuyo desenlace es adverso.
    """
    adversos = adversos if adversos is not None else set(episodios_por_paciente)

    filas_obs, filas_epi = [], []
    episodio_id = 0
    for paciente_id, cuantos in episodios_por_paciente.items():
        for _ in range(cuantos):
            episodio_id += 1
            ingreso = INICIO + pd.Timedelta(days=episodio_id)
            egreso = ingreso + pd.Timedelta(hours=6)
            filas_epi.append(
                {
                    "episodio_id": episodio_id,
                    "paciente_id": paciente_id,
                    "ingreso_en": ingreso,
                    "egreso_en": egreso,
                    "desenlace_adverso": paciente_id in adversos,
                }
            )
            for k in range(3):
                filas_obs.append(
                    {
                        "episodio_id": episodio_id,
                        "paciente_id": paciente_id,
                        "medido_en": ingreso + pd.Timedelta(hours=k),
                        "y": 1 if paciente_id in adversos else 0,
                    }
                )

    observaciones = pd.DataFrame(filas_obs)
    observaciones["y"] = observaciones["y"].astype("Int64")
    return observaciones, pd.DataFrame(filas_epi)


def _particionar(episodios_por_paciente, adversos=None, semilla="prueba"):
    observaciones, episodios = _datos(episodios_por_paciente, adversos)
    return particiones.particionar(observaciones, episodios, semilla=semilla)


# =============================================================================
# El invariante central
# =============================================================================
def test_ningun_paciente_cruza_particiones():
    df = _particionar({p: 3 for p in range(30)})
    cruces = df.groupby("paciente_id")["particion"].nunique()
    assert (cruces == 1).all(), "un paciente quedó en más de una partición"


def test_el_paciente_con_muchos_episodios_no_se_parte():
    """El caso del demo: un paciente con 23 episodios. Partir por episodio lo rompería."""
    df = _particionar({1: 23, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3, 7: 3, 8: 3})
    del_paciente_1 = df.loc[df["paciente_id"] == 1, "particion"].unique()
    assert len(del_paciente_1) == 1, f"el paciente 1 quedó en {list(del_paciente_1)}"


def test_la_auditoria_no_encuentra_nada_en_un_split_sano():
    df = _particionar({p: 2 for p in range(40)})
    graves = [v for v in particiones.auditar(df) if v.grave]
    assert graves == [], f"el split sano disparó violaciones: {[v.regla for v in graves]}"


def test_la_auditoria_detecta_una_fuga_inyectada():
    """Si la auditoría no detecta una fuga puesta a mano, no sirve para nada."""
    df = _particionar({p: 2 for p in range(40)})

    paciente = df.loc[df["particion"] == particiones.ENTRENAMIENTO, "paciente_id"].iloc[0]
    indice = df.index[df["paciente_id"] == paciente][0]
    df.loc[indice, "particion"] = particiones.PRUEBA

    graves = [v for v in particiones.auditar(df) if v.grave]
    assert any("una sola partición" in v.regla for v in graves), (
        "la auditoría no detectó un paciente repartido entre entrenamiento y prueba"
    )


# =============================================================================
# Determinismo y proporciones
# =============================================================================
def test_dos_corridas_dan_la_misma_particion():
    a = _particionar({p: 2 for p in range(40)})
    b = _particionar({p: 2 for p in range(40)})
    assert a["particion"].equals(b["particion"]), "la partición no es reproducible"


def test_otra_semilla_reparte_distinto():
    a = _particionar({p: 2 for p in range(40)}, semilla="uno")
    b = _particionar({p: 2 for p in range(40)}, semilla="dos")
    assert not a["particion"].equals(b["particion"]), "la semilla no cambia nada"


def test_el_orden_de_las_filas_no_cambia_la_particion():
    """Si el orden de entrada mueve pacientes de partición, el experimento no se reproduce."""
    observaciones, episodios = _datos({p: 2 for p in range(40)})
    normal = particiones.particionar(observaciones, episodios, semilla="prueba")
    invertido = particiones.particionar(
        observaciones.iloc[::-1].reset_index(drop=True),
        episodios.iloc[::-1].reset_index(drop=True),
        semilla="prueba",
    )
    esperado = normal.set_index(["episodio_id", "medido_en"])["particion"].sort_index()
    obtenido = invertido.set_index(["episodio_id", "medido_en"])["particion"].sort_index()
    assert esperado.equals(obtenido), "el orden de entrada cambió el reparto"


def test_las_tres_particiones_reciben_pacientes():
    df = _particionar({p: 2 for p in range(40)})
    assert set(df["particion"].unique()) == set(particiones.PARTICIONES)


def test_las_proporciones_son_aproximadas_a_lo_pedido():
    df = _particionar({p: 1 for p in range(100)})
    reparto = df.groupby("particion")["paciente_id"].nunique() / 100
    assert abs(reparto[particiones.ENTRENAMIENTO] - 0.70) < 0.05, reparto.to_dict()
    assert abs(reparto[particiones.PRUEBA] - 0.15) < 0.05, reparto.to_dict()


def test_proporciones_que_no_suman_uno_fallan():
    observaciones, episodios = _datos({p: 1 for p in range(10)})
    try:
        particiones.particionar(observaciones, episodios, proporciones=(0.7, 0.2, 0.2))
    except ValueError:
        return
    raise AssertionError("aceptó proporciones que suman 1.1")


# =============================================================================
# Estratificación
# =============================================================================
def test_estratifica_por_desenlace_del_paciente():
    """Los 20 negativos no pueden caer todos en la misma partición."""
    adversos = set(range(20))
    df = _particionar({p: 1 for p in range(40)}, adversos=adversos)

    negativos = df[~df["paciente_id"].isin(adversos)]
    reparto = negativos.groupby("particion")["paciente_id"].nunique()
    assert len(reparto) == 3, f"los negativos quedaron en {reparto.to_dict()}"


def test_un_paciente_con_todas_sus_tomas_descartadas_cuenta_como_adverso():
    """
    Estratificar sobre `y` en vez de sobre el episodio contaría a este paciente como
    negativo: tuvo desenlace adverso pero todas sus tomas quedaron sin etiqueta.
    """
    observaciones, episodios = _datos({1: 1, 2: 1, 3: 1}, adversos={1, 2, 3})
    observaciones["y"] = pd.array([pd.NA] * len(observaciones), dtype="Int64")

    df = particiones.particionar(observaciones, episodios, semilla="prueba")
    assert df["particion"].notna().all(), "quedaron observaciones sin partición"


# =============================================================================
# Fuga temporal
# =============================================================================
def test_orden_temporal_limpio_no_reporta_nada():
    df = _particionar({p: 2 for p in range(10)})
    assert particiones.verificar_orden_temporal(df) == []


def test_detecta_tomas_desordenadas_dentro_del_episodio():
    df = _particionar({p: 2 for p in range(10)})
    # Se adelanta la última toma del primer episodio: la serie deja de ser monótona.
    indice = df.index[df["episodio_id"] == df["episodio_id"].iloc[0]][-1]
    df.loc[indice, "medido_en"] = INICIO - pd.Timedelta(days=5)

    violaciones = particiones.verificar_orden_temporal(df)
    assert violaciones and violaciones[0].grave, "no detectó las tomas fuera de orden"


# =============================================================================
# Consistencia con la tubería
# =============================================================================
def test_observacion_de_un_paciente_desconocido_falla():
    observaciones, episodios = _datos({1: 1, 2: 1, 3: 1})
    observaciones.loc[0, "paciente_id"] = 999
    try:
        particiones.particionar(observaciones, episodios)
    except ValueError as e:
        assert "999" in str(e) or "observaciones" in str(e)
        return
    raise AssertionError("aceptó una observación de un paciente que no está en episodios")


def test_el_resumen_cuadra_con_las_filas():
    df = _particionar({p: 2 for p in range(40)})
    resumenes = particiones.resumir(df)
    assert sum(r.observaciones for r in resumenes) == len(df)
    assert sum(r.pacientes for r in resumenes) == df["paciente_id"].nunique()


PRUEBAS = [
    test_ningun_paciente_cruza_particiones,
    test_el_paciente_con_muchos_episodios_no_se_parte,
    test_la_auditoria_no_encuentra_nada_en_un_split_sano,
    test_la_auditoria_detecta_una_fuga_inyectada,
    test_dos_corridas_dan_la_misma_particion,
    test_otra_semilla_reparte_distinto,
    test_el_orden_de_las_filas_no_cambia_la_particion,
    test_las_tres_particiones_reciben_pacientes,
    test_las_proporciones_son_aproximadas_a_lo_pedido,
    test_proporciones_que_no_suman_uno_fallan,
    test_estratifica_por_desenlace_del_paciente,
    test_un_paciente_con_todas_sus_tomas_descartadas_cuenta_como_adverso,
    test_orden_temporal_limpio_no_reporta_nada,
    test_detecta_tomas_desordenadas_dentro_del_episodio,
    test_observacion_de_un_paciente_desconocido_falla,
    test_el_resumen_cuadra_con_las_filas,
]


if __name__ == "__main__":
    fallos = []
    for prueba in PRUEBAS:
        try:
            prueba()
        except AssertionError as e:
            fallos.append(f"{prueba.__name__}: {e}")

    if fallos:
        print(f"FALLARON {len(fallos)} de {len(PRUEBAS)}:")
        for f in fallos:
            print("  -", f)
        raise SystemExit(1)
    print(f"OK: {len(PRUEBAS)} pruebas de la particion por paciente")
