# 🧰 Preparación del terreno — antes de escribir código

**2026-08-27.** Análisis pedido antes de arrancar el desarrollo del Sprint 3.
Responde a cuatro preguntas: por dónde empezar, cómo trabajar con notebooks, dónde entrenar,
y qué falta instalar o configurar.

---

## 🚨 Hallazgo bloqueante: el repositorio es PÚBLICO

`github.com/Nahuelito22/Zaha` tiene `"visibility": "public"`. Y el `.gitignore` protege
`ml_engine/data/*`, pero **no protege las salidas de los notebooks**: solo ignora
`.ipynb_checkpoints`.

En Nimbus-AI los notebooks se commitearon con todas sus salidas — `05_analisis_exploratorio`
pesa 66 MB, y hay un `.nc` de 23 MB versionado dentro de `notebooks/`. Es una práctica normal
en un proyecto propio. **Acá no lo es.**

Si un notebook con MIMIC-IV-ED se commitea con sus salidas, un `df.head()` o un gráfico con
detalle por paciente queda publicado en un repositorio abierto. Eso es:

1. Una **violación del DUA** de PhysioNet, que prohíbe redistribuir los datos.
2. Motivo de **revocación de la credencial** — la misma que estamos esperando (`SCRUM-48`) y
   que bloquea las Épicas 4 y 5 enteras.
3. Una contradicción demoledora en la defensa: el proyecto entero se presenta bajo encuadre
   SaMD, Ley 25.326 de datos personales y trazabilidad legal.

### Qué hay que hacer, antes de tocar un solo dato real

- **Decidir si el repo pasa a privado.** Recomendación: sí, al menos hasta la entrega. Un repo
  público no aporta nada a la nota y concentra todo el riesgo. Si se quiere público por
  portfolio, se puede abrir *después* de la defensa, con el historial limpio.
- **Instalar `nbstripout`** en el repo como filtro de git. Limpia las salidas al commitear,
  automáticamente, sin depender de que alguien se acuerde.
- **Extender el `.gitignore`** para que los notebooks con datos reales no entren por accidente.
- **Regla explícita:** los notebooks que tocan MIMIC se commitean **sin salidas**. Los que solo
  usan datos sintéticos pueden conservarlas, y son los que sirven para mostrar en la defensa.

> El historial de git es append-only, igual que `vital_records`. Un dato restringido que entra
> en un commit no se va con un `rm` después: hay que reescribir el historial. Por eso esto se
> resuelve **antes** de que llegue la credencial, no después.

---

## 1 · ¿Por dónde empezar: landing o app?

**Por la app clínica (`/app`). La landing va última.**

| | Landing | App clínica |
|---|---|---|
| Qué valida | Nada técnico | El esquema, RLS, el flujo de carga, el offline |
| Qué bloquea | Nada | Épicas 3, 5 y 6 |
| Si sale mal | Se rehace en una tarde | Se rehace el modelo de datos |
| Riesgo real | Bajo | Alto — es donde están las incógnitas |

La landing es una página estática de presentación: no prueba ninguna hipótesis y no desbloquea
a nadie. La app es donde puede aparecer que el esquema no expresa algo que la enfermera
necesita cargar, y eso conviene descubrirlo ahora que la base tiene cero filas.

Además el objetivo del Sprint 3 ya lo dice: *entrar a `/app` con un usuario real y cargar una
toma que quede guardada con su score*.

### Decisión previa: cómo conviven Astro y React

Hoy `app/` es un proyecto Astro 6 pelado (un `index.astro`, Tailwind 4, sin React ni Vite SPA
ni service worker). ADR-001 pide Astro **solo** para la landing y una SPA React + Vite + TS
para la app. Son dos runtimes y dos builds.

**Recomendación: dos proyectos separados dentro del monorepo.**

```
app/
├── landing/     Astro + Tailwind  → el index.astro actual se muda acá
└── clinical/    Vite + React + TS → PWA, Dexie, Supabase, service worker
```

**Por qué no islas de React dentro de Astro:** una PWA offline-first necesita control del
service worker, del ciclo de vida de la caché y de una sesión de Supabase que sobreviva a la
navegación. Dentro de Astro eso es pelearse con el framework. Separarlos cuesta una carpeta
más y evita el problema entero.

**Queda abierto:** dónde se despliega cada uno (dos sitios, o uno con reescritura de rutas).
No bloquea el scaffold; se puede decidir en el Sprint 4.

---

## 2 · Notebooks y método científico

Sí, y acá no es una preferencia de estilo: es un requisito. Una tesis que afirma *"igualo la
sensibilidad de NEWS2 reduciendo la tasa de alertas"* tiene que poder mostrar cómo se llegó a
ese número. El notebook **es** la evidencia.

### Convención (misma que usás en Nimbus-AI)

Numerados, snake_case en español, en `ml_engine/notebooks/`. Secuencia propuesta, mapeada
contra los issues que ya existen:

| Notebook | Issue |
|---|---|
| `01_exploracion_mimic_ed.ipynb` | `SCRUM-51` |
| `02_construccion_cohorte_y_episodios.ipynb` | `SCRUM-51` |
| `03_definicion_etiqueta_v2.ipynb` | `SCRUM-53` |
| `04_split_por_paciente_y_fuga.ipynb` | `SCRUM-54` |
| `05_eda_y_prevalencia.ipynb` | `SCRUM-55` |
| `06_baseline_news2.ipynb` | **falta en el backlog** |
| `07_baseline_xgboost.ipynb` | `SCRUM-56` |
| `08_lstm_hipotesis.ipynb` | `SCRUM-57` |
| `09_tasa_alertas_sensibilidad_igualada.ipynb` | `SCRUM-58` |
| `10_export_onnx_y_validacion.ipynb` | `SCRUM-59` |

> **El notebook 06 no tiene issue y es imprescindible.** Antes de comparar contra NEWS2 hay que
> *reproducir* NEWS2 sobre MIMIC-IV-ED y medir su tasa de alertas en esta cohorte. El 37,6 por
> 100 pacientes-día viene de la literatura, sobre otra población. Comparar el modelo propio
> contra un número ajeno es indefendible: la referencia tiene que salir de los mismos datos.
> Ventaja: el motor NEWS2 ya está escrito y testeado en SQL, así que el notebook lo replica y
> de paso **valida la implementación** contra los 21 casos clínicos.

### Dos reglas que evitan el problema clásico

1. **El notebook explora; `ml_engine/src/` ejecuta.** Toda función que se use más de una vez se
   muda a `src/` y el notebook la importa. Sin copiar y pegar. Si no, el modelo servido y el
   modelo del notebook divergen y ninguno de los dos es reproducible.
2. **Semilla fija y versión de datos anotada** en la primera celda de cada notebook. Un
   resultado que no se puede volver a obtener no sirve para una tesis.

### Skill propuesta

Crear una skill de proyecto en `.claude/skills/` que codifique todo esto —convención de
nombres, regla de `src/`, prohibición de commitear salidas con datos reales, formato de la
celda de cabecera—. Así cualquier sesión futura la sigue sin que haya que repetirlo.

La skill **`dataviz`** ya está disponible y es la correcta para los gráficos: cubre paletas
accesibles, elección de tipo de gráfico y consistencia entre figuras. Conviene usarla desde el
notebook 01 para que todas las figuras de la tesis se vean como un sistema.

---

## 3 · Local vs. nube

**Regla práctica: tratá el equipo local como CPU-only.**

PyTorch con aceleración AMD es ROCm, que en la práctica es Linux. En Windows existe
`torch-directml`, pero tiene cobertura parcial de operadores y da problemas justamente con
capas recurrentes. No vale la pena pelear con eso para una tesis con fecha.

La buena noticia es que **casi todo este proyecto es CPU**:

| Etapa | Dónde | Por qué |
|---|---|---|
| ETL de MIMIC-IV-ED | Local | Es tabular. Pandas o Polars lo manejan. |
| EDA y gráficos | Local | — |
| Reproducción de NEWS2 | Local | Aritmética. |
| **Baseline XGBoost** | Local | CPU es su terreno natural; minutos, no horas. Y es el modelo **principal** según ADR-005. |
| Comparativa de tasa de alertas | Local | Es cálculo sobre predicciones ya hechas. |
| Export a ONNX + validación | Local | — |
| **LSTM sobre ventanas de 48 h** | **Colab** | Único punto realmente hambriento de GPU. |

O sea: **una sola etapa va a Colab**, y es precisamente la que ADR-005 marcó como *hipótesis
bajo prueba*. Si no aporta, se reporta que no aporta y listo.

### ⚠️ Antes de subir nada a Colab

Colab significa Google Drive, y Drive significa sacar datos de PhysioNet de tu máquina.
El DUA que vas a firmar en `SCRUM-49` regula esto y hay que leer **el texto exacto** antes de
subir nada — no me confío de memoria en los detalles.

Lo que sí es criterio sólido, firmes lo que firmes:

- **Nunca subas el dataset crudo.** Subí únicamente la **matriz de features derivada** que la
  LSTM necesita: tensores numéricos por ventana y su etiqueta. Sin texto libre, sin
  identificadores, sin columnas que no entren al modelo.
- **Drive privado**, nunca una carpeta compartida ni un enlace "cualquiera con el link".
- **Borrá los datos de Drive** cuando termines el experimento.
- Anotá en el notebook 08 qué se subió y por qué. Esa nota es parte del documento de gestión
  de riesgos (`SCRUM-75`).

---

## 4 · Inventario: qué hay, qué falta

### Skills

| | Estado |
|---|---|
| `supabase`, `supabase-postgres-best-practices` | ✅ instaladas en `.agents/skills/` |
| `dataviz` | ✅ disponible — usarla para todas las figuras |
| `artifact-design`, `artifact-diagramming` | ✅ disponibles — para entregables visuales |
| `code-review`, `security-review` | ✅ disponibles — correr `security-review` antes de la entrega |
| Skill de notebooks de Zaha | ❌ **a crear** (ver sección 2) |

### MCP

Todo lo necesario está conectado: **Supabase**, **GitHub**, **Atlassian**, **Hugging Face**
(para el deploy en Spaces), **Chrome**, **Drive/Gmail/Calendar**.

- ❌ **`plugin:firebase:firebase` falla por timeout en cada sesión** (30 segundos perdidos) y es
  de otro proyecto. Conviene quitarlo de la configuración.
- No falta ningún MCP para lo que viene. Colab se maneja por navegador, y para eso ya está
  Chrome.

### Dependencias

`ml_engine/requirements.txt` tiene solo `fastapi`, `uvicorn`, `pydantic`, `pandas`,
`scikit-learn`. Faltan y hay que **fijar versiones** — una tesis sin versiones fijadas no es
reproducible:

```
xgboost · torch · onnx · onnxruntime · pandera · matplotlib
jupyter · pyarrow · nbstripout
```

Conviene además separar `requirements.txt` (lo que necesita la API en producción) de
`requirements-dev.txt` (notebooks y entrenamiento). El contenedor de Hugging Face Spaces no
tiene por qué cargar con `torch` y `jupyter` si sirve ONNX.

### Backlog: dos issues que faltan

1. **Reproducir NEWS2 sobre MIMIC-IV-ED y medir su tasa de alertas real** (Épica 4). Es la
   referencia contra la que se compara todo. Sin esto, `SCRUM-58` no tiene contra qué medir.
2. **Seed de datos de desarrollo** (Épica 3). La base está vacía; la PWA no tiene qué mostrar.
   Los datos ficticios ya están acordados: Clínica Médica, camas `CM-01` a `CM-24`, nombres
   mendocinos, Lic. Vanina Soledad Agüero.

### Detalle menor

La descripción del repositorio en GitHub todavía dice *"predicción de series temporales
(LSTM)"*, que contradice el reencuadre de ADR-005. Si el repo queda público, es lo primero que
lee un jurado.

---

## Orden propuesto para arrancar

1. **Repo a privado** + `nbstripout` + `.gitignore` extendido. *(bloqueante, antes de datos reales)*
2. **Mandar el credentialing de PhysioNet** (`SCRUM-48`). No es código y tarda semanas.
3. Crear los **dos issues faltantes** y la **skill de notebooks**.
4. Fijar **dependencias** y separar dev de producción.
5. **Seed de desarrollo** en Supabase.
6. **Scaffold** `app/clinical` (Vite + React + TS) y mudar el Astro actual a `app/landing`.
7. Recién ahí: auth, formulario de carga, tablero.

Los pasos 1 a 5 no dependen de ninguna decisión abierta y se pueden hacer hoy.
