# Plan — decisiones y planificación de Zaha

Documentación de **proceso**, no de uso. Si buscás cómo correr el proyecto, el `README.md`
de la raíz y los de `app/`, `ml_engine/` y `design_system/` son los que sirven.

Esta carpeta estuvo gitignoreada hasta el **2026-09-30**. Se versionó porque los ADR y los
documentos de épica no tenían respaldo: si la carpeta se borraba había que rehacerlos. Es el
mismo problema que tenían los generadores de figuras en `ayudas_y_recursos/`, y por el que
se movieron a `scripts/`.

## Qué hay

| Archivo | Qué es |
|---|---|
| `00_CARTA_MAGNA.md` | El encuadre del proyecto: qué es Zaha y qué no es |
| `02_DECISIONES_TECNICAS.md` | **Los 9 ADR.** Lo más importante de la carpeta |
| `03_BACKLOG_JIRA.md` | El backlog en prosa, del que salen los CSV |
| `04_SPRINTS.md` | Planificación por sprint. ⚠️ Usa la numeración vieja de 8 sprints; Jira usa la compactada a 6 |
| `05_PREPARACION.md` | Método de trabajo: notebooks, entorno, local vs nube |
| `epica_02_backend_news2/` | Esquema de base y motor NEWS2 |
| `epica_04_motor_ia/` | Definición de la etiqueta y el caveat de NEWS2 en urgencias |
| `jira_export.py` + `jira_*.csv` | Genera los CSV importables a Jira desde el backlog |

## Los ADR, de un vistazo

| | Decisión |
|---|---|
| **ADR-001** | React SPA (PWA) + Astro para la landing; NEWS2 lo calcula la base |
| **ADR-002** | MIMIC-IV-ED como fuente principal — ⚠️ **desactualizado**, ver ADR-009 |
| **ADR-003** | Progresión baseline → GBM → LSTM → ensemble |
| **ADR-004** | Inferencia PyTorch → ONNX en Hugging Face, con degradación elegante |
| **ADR-005** | **Reencuadre: reducir tasa de alertas, no maximizar AUROC** |
| **ADR-006** | Caveat: NEWS2 fue diseñado para sala general, no para guardia |
| **ADR-007** | ACVPU y oxígeno suplementario no existen en MIMIC-IV-ED: se imputan |
| **ADR-009** | Segunda cohorte (TRIAGE) junto a MIMIC-IV-ED |

> **ADR-008 no existe todavía.** Le corresponde el diseño en dos capas del log de auditoría
> —prevención por privilegios más detección por cadena de hashes— implementado en
> `SCRUM-72`. Está pendiente de escribir.

## Lo que NO vive acá

**Ningún dato clínico.** Los datasets viven en `ml_engine/data/`, que sigue gitignoreada.
MIMIC-IV-ED está bajo un DUA de PhysioNet que prohíbe redistribuirlo, y este repositorio es
público. Ver `ml_engine/data/raw/*/README.md`.

Tampoco hay credenciales: antes de versionar esta carpeta se escaneó en busca de tokens,
claves y datos personales, y no hay ninguno.
