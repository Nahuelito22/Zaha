# ml_engine — tubería de datos, modelado e inferencia

## Entorno: usar el venv, no el Python global

El proyecto tiene su propio entorno virtual. **No instales nada con el Python del sistema.**

```bash
cd ml_engine
python -m venv .venv                          # solo la primera vez
.venv/Scripts/python -m pip install -r requirements-dev.txt    # Windows
# .venv/bin/python  -m pip install -r requirements-dev.txt     # Linux/macOS
```

Después, todo se corre con ese intérprete:

```bash
.venv/Scripts/python -m src.data.mimic_ed
.venv/Scripts/python tests/test_news2.py
```

**Por qué importa, con un ejemplo real.** El 30/09/2026 un `pip install skl2onnx` en el
Python global subió `numpy`, `scipy` y `protobuf` de golpe y dejó incompatibles a
`mediapipe`, `opencv-python` y cuatro paquetes de Google de otros proyectos. El venv existe
para que eso no vuelva a pasar.

`requirements.lock.txt` es el `pip freeze` del entorno real y **está versionado**: es lo que
permite reinstalar exactamente el mismo entorno. Regenerarlo después de agregar una
dependencia:

```bash
.venv/Scripts/python -m pip freeze > requirements.lock.txt
```

> **Ojo con las versiones.** `requirements-dev.txt` declara `pandas~=3.0.5`, y en pandas 3
> las cadenas dejan de ser `object` y pasan a dtype `str`. Los esquemas de `validation/`
> declaran `str` justamente para funcionar en las dos versiones. Si agregás una columna de
> texto a un esquema, declarala `str`, nunca `object`.

## Qué hay acá

| Módulo | Qué hace | Issue |
|---|---|---|
| `src/data/news2.py` | Motor NEWS2 determinístico | SCRUM-22 |
| `src/data/mimic_ed.py` | Ingesta de MIMIC-IV-ED al esquema del proyecto | SCRUM-50 |
| `src/data/triage.py` | Ingesta de la cohorte TRIAGE (2ª cohorte, ADR-009) | SCRUM-82 |
| `src/data/etiquetas.py` | Etiqueta v2, ventana `(t+1h, t+24h]` | SCRUM-53 |
| `src/data/particiones.py` | Partición por paciente y control de fuga temporal | SCRUM-54 |
| `src/data/alertas.py` | Regla de alerta y curvas de operación | SCRUM-80 / 58 |
| `src/models/baseline.py` | Baseline sobre snapshot, con CV anidada | SCRUM-56 |
| `src/models/exportar.py` | Exportación a ONNX con verificación de paridad | SCRUM-59 |
| `src/validation/esquemas.py` | Contratos de datos (Pandera + Pydantic) | SCRUM-52 |
| `src/viz/estilo.py` | Estilo único de las figuras de la tesis | — |

## Cómo se corre la cadena completa

```bash
cd ml_engine
.venv/Scripts/python -m src.data.mimic_ed        # CSV crudos -> parquet
.venv/Scripts/python -m src.data.etiquetas       # + etiqueta v2
.venv/Scripts/python -m src.data.particiones     # + particion por paciente
.venv/Scripts/python -m src.data.triage          # la 2a cohorte (independiente)
.venv/Scripts/python -m src.data.alertas         # tasa de alertas de referencia
.venv/Scripts/python -m src.models.baseline      # baseline vs NEWS2
.venv/Scripts/python -m src.models.exportar      # -> models/zaha_baseline.onnx
```

## Pruebas

125 pruebas. Corren con y sin pytest:

```bash
for t in tests/*.py; do .venv/Scripts/python "$t"; done
```

## El modelo exportado

`models/zaha_baseline.onnx` (864 bytes) más `models/zaha_baseline.metadata.json`. Son los
**dos únicos artefactos de modelo versionados**, por una excepción explícita en el
`.gitignore`: están entrenados sobre la cohorte TRIAGE, que es CC0.

**Un modelo entrenado sobre MIMIC-IV-ED NO se puede versionar**: ese dataset está bajo un
DUA de PhysioNet que prohíbe redistribuirlo, y el modelo hereda la restricción.

El sidecar publica el orden de las features —ONNX recibe un tensor, así que las columnas
viajan por posición y mandarlas cambiadas no da error, da un número— y la curva de umbrales
con su **tasa de alertas esperada fuera de fold**. No usar la tasa in-sample para dimensionar
la carga: es optimista en 4 a 5 puntos.

## Datos

Todo vive en `data/`, que está **entero en `.gitignore`**. MIMIC-IV-ED está bajo DUA y este
repositorio es público. Ver los README de cada carpeta en `data/raw/`.
