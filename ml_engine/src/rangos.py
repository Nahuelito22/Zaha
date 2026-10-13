"""
Rangos fisiológicamente plausibles — la única fuente de verdad.

POR QUÉ ESTE MÓDULO EXISTE Y NO VIVE EN `validation/esquemas.py`
Vivía ahí, y conceptualmente es su lugar. El problema es de empaquetado: `esquemas`
importa pandera y pandas, y el contenedor de producción (`requirements.txt`) no los lleva
a propósito — sirve un ONNX ya entrenado y meter pandas le agregaría peso y arranque en
frío que el ADR-004 quiso evitar. Pero la API **necesita** estos rangos: es el borde por
donde entran los datos a la inferencia.

Las dos salidas malas eran duplicar el diccionario en `src/api` —y que algún día los dos
dejen de coincidir sin que nada falle— o arrastrar pandera al contenedor. Este módulo es
la tercera: un archivo sin una sola dependencia de terceros, que importan los dos lados.
`esquemas` lo reexporta, así que `esquemas.RANGOS_PLAUSIBLES` sigue funcionando y ningún
import existente se rompe.

QUÉ PASA SI ESTOS NÚMEROS SE DESINCRONIZAN
Es la trampa que ya se pagó una vez. Si la base de datos rechaza una medición que la
tubería acepta, el NEWS2 histórico y el de producción se calculan sobre universos
distintos, y la comparación de `SCRUM-58` —que es la tesis— deja de significar algo. Lo
mismo con la API: si acepta una SpO₂ de 10 %, devuelve una probabilidad perfectamente
plausible sobre un paciente que no existe.

Estos valores tienen que seguir siendo los mismos que:
  - los CHECK de la migración `20260521000000`
  - `RANGOS` en `app/clinical/src/lib/tipos.ts`
  - `RANGOS_PLAUSIBLES` tal como la usa `src/data/mimic_ed.py`

`tests/test_api.py::test_los_rangos_de_la_api_son_los_de_la_tuberia` lo hace cumplir del
lado de Python. Los otros dos lados se verifican a mano al tocar cualquiera de los tres.
"""

from __future__ import annotations

# Límites inclusivos. Un valor fuera de rango no es un valor extremo: es un error de
# registro o de unidad, y se trata como ausente, no como grave.
RANGOS_PLAUSIBLES: dict[str, tuple[float, float]] = {
    "frecuencia_respiratoria": (0, 80),
    "spo2": (50, 100),
    "temperatura": (25, 45),
    "presion_sistolica": (30, 300),
    "frecuencia_cardiaca": (0, 300),
}
