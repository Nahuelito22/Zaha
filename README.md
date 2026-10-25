<div align="center">

<img src="app/landing/public/marca/zaha-z.png" alt="La Z de Zaha" width="120" />

# Zaha

**Soporte a la decisión clínica para enfermería de sala de internación.**
NEWS2 automático, alertas tempranas de deterioro y una estimación de riesgo por IA que
se presenta aparte de la escala, nunca en su lugar.

[**zahasalud.com.ar**](https://zahasalud.com.ar) · [Aplicación](https://zahasalud.com.ar/app) · [Manual de uso](https://zahasalud.com.ar/manual) · [API del motor](https://zaha-cdss-inferencia.hf.space/api/docs)

</div>

> [!WARNING]
> **Zaha es un prototipo académico. No es un dispositivo médico**: no está autorizado por
> ANMAT ni por ninguna autoridad regulatoria, y no debe usarse para tomar decisiones sobre
> pacientes reales. Todos los pacientes de la base son ficticios.

---

## Qué es

En una sala de internación, el personal de enfermería toma los signos vitales de cada
paciente varias veces por turno y tiene que darse cuenta, a mano y cansado, de cuál se
está deteriorando. Zaha hace tres cosas:

1. **Calcula NEWS2 en el momento** en que se cargan los siete parámetros, y lo calcula la
   base de datos, no la pantalla: hay una sola fuente para el número.
2. **Ordena la sala por riesgo y alerta** cuando un paciente lo necesita. Cada alerta se
   valida o se pospone con un toque, y queda registrada en una bitácora que no se puede
   alterar.
3. **Suma la estimación de un modelo de IA**, en violeta y con borde punteado para que
   nadie la confunda con la escala. Si el motor no responde, NEWS2 sigue funcionando igual.

### El objetivo no es predecir mejor, sino alertar menos

La revisión de literatura cambió la meta del proyecto (ADR-005). Los mejores modelos le
ganan a NEWS2 por menos de 2 puntos de AUROC, y el problema real de las salas no es la
falta de alertas sino el exceso: con NEWS2 ≥ 5 un hospital inglés generaba **37,6 alertas
cada 100 pacientes por día** detectando menos de la mitad de los desenlaces (Pankhurst et
al., *BMJ Open* 2022). Por eso el criterio de éxito es **reducir la tasa de alertas con la
misma sensibilidad que NEWS2**.

**Resultado honesto:** con la cohorte disponible (1.300 pacientes, 54 muertes) esa
reducción **todavía no está demostrada**. La estimación es del 29,8 %, pero el intervalo de
confianza del 95 % va de −8,5 % a +44,7 % e incluye el cero. La aplicación lo dice en cada
estimación.

---

## Cómo está armado

```
                         zahasalud.com.ar  (Vercel)
               ┌──────────────────┴──────────────────┐
         Landing (Astro)                 Aplicación clínica (React PWA)
          /  /manual                              /app
               │                                     │
               │ /api/motor/*                         │ supabase-js (JWT del usuario)
               ▼                                     ▼
     Motor de IA (Hugging Face)  ◄──────  Supabase: Postgres + Auth + RLS
     FastAPI + ONNX Runtime        Edge     · NEWS2 en funciones SQL y triggers
     regresión logística          Function  · tomas append-only, con enmiendas
                                 prediccion · bitácora de alertas con cadena de hashes
```

| Pieza | Tecnología | Dónde vive |
|---|---|---|
| Landing y manual | Astro 6, Tailwind 4 | `app/landing` → `zahasalud.com.ar` |
| Aplicación clínica | React 19, Vite, TypeScript, PWA con cola offline (Dexie) | `app/clinical` → `zahasalud.com.ar/app` |
| Base de datos y autenticación | Supabase (PostgreSQL), Row Level Security | `supabase/migrations` |
| Puente al motor | Supabase Edge Function (Deno) | `supabase/functions/prediccion` |
| Motor de IA | scikit-learn → ONNX, servido con FastAPI dentro de un Space de Gradio | `ml_engine`, `deploy/hf_space` |
| Sistema de diseño | Dos capas de tokens: marca (tierra) y clínica (neutra) | `design_system` |

### Decisiones que conviene conocer

- **NEWS2 lo calcula la base.** Funciones `IMMUTABLE` y un trigger: la pantalla nunca
  puntúa, ni siquiera sin conexión. Una toma cargada offline queda "sin puntaje" hasta que
  la recibe el servidor, en lugar de mostrar un número aproximado.
- **Nada se borra.** Las tomas son *append-only*: un dato mal cargado se corrige con una
  **enmienda** que lo reemplaza y dice por qué, y las dos quedan en el historial. Un trigger
  lo impide incluso con la clave de servicio.
- **La bitácora se puede auditar.** Cada evento de cada alerta (emitida, validada,
  pospuesta, descartada) queda en `alert_audit_log`, encadenado con SHA-256.
  `verificar_cadena_auditoria()` detecta si alguien alteró una fila (ADR-008).
- **El modelo es una regresión logística**, no una LSTM: con 54 eventos, la validación
  cruzada anidada la eligió en los cinco pliegues por encima de XGBoost (ADR-010). Se
  exporta a ONNX con su imputación y escalado, y viaja con un archivo de metadatos que
  publica el orden de las variables y la curva de umbrales.
- **La IA nunca es la alerta.** Las alertas que se atienden salen de NEWS2. La estimación
  del modelo se muestra con su explicación, separada y en otro color.

Las 10 decisiones de arquitectura están en [`Plan/02_DECISIONES_TECNICAS.md`](Plan/02_DECISIONES_TECNICAS.md).

---

## Estructura del repositorio

| Carpeta | Qué hay |
|---|---|
| [`app/landing`](app/landing) | Sitio público: landing con la intro animada, demo del motor y manual de uso |
| [`app/clinical`](app/clinical) | La aplicación de enfermería (PWA). Su manual en texto: [`MANUAL_ENFERMERIA.md`](app/clinical/MANUAL_ENFERMERIA.md) |
| [`supabase`](supabase) | 8 migraciones (esquema, motor NEWS2, RLS, bitácora), la Edge Function y los casos de prueba SQL |
| [`ml_engine`](ml_engine) | Tubería de datos, modelado, exportación a ONNX, API de inferencia y exportador FHIR |
| [`deploy/hf_space`](deploy/hf_space) | El Space de Hugging Face que sirve el motor |
| [`design_system`](design_system) | Tokens de color y tipografía, y la auditoría de contraste WCAG |
| [`Plan`](Plan) | ADR, documentos de cada épica (incluido el encuadre regulatorio) y entregas |
| [`scripts`](scripts) | Generadores de las figuras de la documentación académica |

---

## Correrlo en local

**Requisitos:** Node 22.12 o superior (las pruebas de TypeScript usan Node 24) y Python 3.12.

### Aplicación clínica

```bash
cd app/clinical
cp .env.example .env.local      # URL del proyecto de Supabase y clave publicable
npm ci
npm run dev                     # http://localhost:5173/app/
```

La clave publicable **no es un secreto**: el control de acceso vive en las políticas RLS.
La clave de servicio no va nunca en el cliente. Las cuentas no se crean desde la app (el
registro está cerrado): las da de alta el administrador.

### Landing

```bash
cd app/landing
npm ci
npm run dev                     # http://localhost:4321
```

En desarrollo, `/api/motor` se redirige al Space de Hugging Face (ver `astro.config.mjs`).
Dos parámetros útiles para presentar: `?animar` fuerza la intro aunque el sistema pida
reducir el movimiento, y `?pasos` la maneja con un botón en lugar del scroll.

### Motor de IA

```bash
cd ml_engine
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt     # Windows
# .venv/bin/python  -m pip install -r requirements-dev.txt      # Linux/macOS
```

Usar siempre el `.venv`, nunca el Python global. La cadena completa y el detalle de cada
módulo están en [`ml_engine/README.md`](ml_engine/README.md).

---

## Pruebas

| Qué | Cuántas | Cómo |
|---|---|---|
| Motor de IA, NEWS2 de referencia, API, exportación ONNX, FHIR | 177 | `cd ml_engine && for t in tests/*.py; do .venv/Scripts/python "$t"; done` |
| Lógica de la app (cola offline, alertas, enmiendas, predicción) | 38 | `node --test app/clinical/src/lib/*.test.ts` |
| Traducción de la Edge Function al vocabulario del modelo | 18 | `node --test supabase/functions/prediccion/mapeo.test.ts` |
| NEWS2 y enmiendas en la base | casos SQL | `psql "$DATABASE_URL" -f supabase/tests/news2_cases.sql` |

Las pruebas de TypeScript usan `node:test`, no Vitest: se corren con `node --test`. Dos
verificaciones que no son pruebas unitarias pero importan:

- **NEWS2 de producción contra la implementación de investigación**: coinciden en los
  1.300 pacientes de la cohorte (`ml_engine/src/evaluacion/tasa_produccion.py`).
- **El Bundle FHIR valida contra el esquema JSON oficial de FHIR R4**, y la prueba rompe
  un recurso a propósito para comprobar que el validador lo rechaza.

---

## Despliegue

- **Sitio y aplicación:** Vercel construye las dos apps desde `main` con `vercel.json`. La
  landing queda en la raíz, la app en `/app`, y `/api/motor/*` se reescribe hacia el Space.
  Se despliega solo desde git, nunca desde una carpeta local.
- **Base de datos:** migraciones en `supabase/migrations`.
- **Motor:** `deploy/hf_space/publicar.py` sube el Space. Corre en ZeroGPU (el plan gratuito
  de Hugging Face), aunque el modelo use solo CPU; si estuvo inactivo, tarda en despertar y
  la app muestra "sin estimación" mientras tanto.

---

## Datos

| Cohorte | Para qué | Licencia |
|---|---|---|
| **TRIAGE** (Eckart et al., Dryad 2018): 1.303 pacientes de guardia de tres centros | Entrenar y evaluar el modelo en producción | CC0 |
| **MIMIC-IV-ED Demo** (Johnson et al., PhysioNet 2023) | Tubería de datos y tasa de alertas de referencia | ODbL |

`ml_engine/data/` está entera en `.gitignore`. El único modelo versionado es
`models/zaha_baseline.onnx`, porque está entrenado sobre TRIAGE (CC0); un modelo entrenado
sobre MIMIC no podría publicarse, porque hereda la restricción de su licencia.

---

## Regulación y seguridad

Documentos en [`Plan/epica_06_regulatorio`](Plan/epica_06_regulatorio):

- **Encuadre como software médico** (ANMAT) y por qué este prototipo no lo es.
- **Seguridad de la base**, verificada desde afuera: registro cerrado, funciones sin acceso
  anónimo, RLS en todas las tablas.
- **Interoperabilidad**: exportador a **FHIR R4** con códigos LOINC verificados en la
  fuente.
- **Gestión de riesgos**: 16 riesgos con su control.
- **Leyes 25.326 y 27.706**, artículo por artículo, con seis brechas declaradas.
- **Referencias de la literatura**, verificadas contra el texto original:
  [`Plan/epica_04_motor_ia/05_referencias.md`](Plan/epica_04_motor_ia/05_referencias.md).

---

## Equipo

Proyecto de **Práctica Profesionalizante III** y **Gestión de Proyectos** de la Tecnicatura
Superior en Desarrollo de Software, IES 9-023 (Mendoza, Argentina), 2026. Desarrollado por
**Nahuel Ghilardi** y **Gustavo Garcia**. Docentes: Prof. Romina Abel y Prof. Andrea
Cattaneo. Gestión del proyecto en Jira, en 6 sprints de dos semanas.

## Licencia

[Apache 2.0](LICENSE).
