#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera los CSV importables a Jira desde el backlog de 03_BACKLOG_JIRA.md.

Uso:  python jira_export.py
Salida: jira_1_epicas.csv  y  jira_2_issues.csv  en este mismo directorio.

Los tipos de issue usan los nombres en español del proyecto ("Historia", "Tarea",
"Epic"), que es como los tiene configurados el sitio zahacdss.atlassian.net.

Asignaciones: no van por email (todavía no los tengo). Va una etiqueta
owner-nahuel / owner-gustavo / owner-tercero por issue, y después se asignan en
bloque desde el board filtrando por esa etiqueta: 3 operaciones en vez de 55.
"""

import csv
import os

N, G, T = "owner-nahuel", "owner-gustavo", "owner-tercero"

EPICAS = [
    ("Épica 1 — Infraestructura y Setup Base",
     "Establecer el monorepo, repositorios, reglas de rama y entornos de desarrollo.\n\n"
     "Entregable: estructura de carpetas compilando sin errores.",
     "iteracion-1 infra", N),
    ("Épica 2 — Backend y Motor Determinístico NEWS2",
     "Construir la base de datos inspirada en FHIR y la lógica matemática en la nube.\n\n"
     "Entregable: base capaz de recibir datos crudos y devolver niveles de riesgo "
     "instantáneamente.",
     "iteracion-1 backend", N),
    ("Épica 3 — Frontend PWA y Landing Page",
     "Desarrollar la interfaz pública y el sistema clínico de bolsillo.\n\n"
     "Entregable: PWA instalable en iOS/Android consumiendo la base de datos real.",
     "iteracion-1 frontend", N),
    ("Épica 4 — Data Engineering y Motor de IA",
     "Procesamiento de series temporales médicas y entrenamiento del modelo predictivo.\n\n"
     "Métrica principal: tasa de alertas a sensibilidad igualada a NEWS2 (referencia a "
     "batir: 37,6 alertas por 100 pacientes-día). No AUROC, no accuracy.\n\n"
     "Entregable: modelo entrenado y exportado a ONNX.",
     "iteracion-2 ml", N),
    ("Épica 5 — API de Inferencia e Integración",
     "Conectar el modelo predictivo con la aplicación clínica.\n\n"
     "Entregable: sistema completo funcionando de extremo a extremo.",
     "iteracion-2 backend ml", N),
    ("Épica 6 — Marco Regulatorio, Auditoría y Entregables Académicos",
     "Encuadre regulatorio del producto como SaMD, trazabilidad legal, y los entregables "
     "de la cátedra.\n\n"
     "Entregable: documentación de cumplimiento y presentación final de Prácticas "
     "Profesionales 3.",
     "iteracion-3 regulatorio academico", T),
]

# (epica, tipo, summary, description, priority, labels_extra, points, owner)
ISSUES = [
    # ── ÉPICA 1 ───────────────────────────────────────────────────────────────
    (1, "Tarea", "Inicializar repositorio Nahuelito22/Zaha con protección de rama main",
     "Repositorio público. Rama principal `main` protegida.", "High", "infra", "", N),
    (1, "Tarea", "Configurar monorepo (/app, /supabase, /ml_engine)",
     "Estructura de carpetas del monorepo compilando sin errores.", "High", "infra", "", N),
    (1, "Tarea", "Aislar credenciales en la cuenta dedicada zaha.cdss@gmail.com",
     "Supabase, Jira y Hugging Face van con la cuenta dedicada. GitHub va con la cuenta "
     "personal. Autenticar con la equivocada rompe el acceso sin dar un error claro.",
     "High", "infra", "", N),
    (1, "Tarea", "Configurar integraciones base (Astro + Tailwind) para la landing",
     "Setup de la landing pública.", "Medium", "infra frontend", "", N),
    (1, "Tarea", "Activar el ruleset Don't-Merge-Before-Pr en GitHub",
     "El ruleset existe pero está en `enforcement: disabled`. Sin activarlo, la protección "
     "de `main` es nominal: nada impide un push directo.", "Medium", "infra", "", N),
    (1, "Tarea", "Documentar el flujo git: Nahuel_Develop -> PR -> main",
     "Todo el trabajo va sobre `Nahuel_Develop`. Nunca push directo a `main`. Deja rastro "
     "revisable de cada cambio, que además sirve como evidencia académica.",
     "Medium", "infra", "", N),
    (1, "Tarea", "Sumar a Gustavo y al tercer integrante como colaboradores del repo",
     "Acceso de lectura al repositorio para el trabajo académico.", "Low", "infra", "", N),

    # ── ÉPICA 2 ───────────────────────────────────────────────────────────────
    (2, "Historia", "HU-02 — Motor Determinístico de Cálculo NEWS2",
     "Como enfermero/a de sala, quiero un sistema que devuelva el puntaje exacto de riesgo "
     "instantáneamente, para conocer la gravedad del paciente y evitar el cálculo mental "
     "manual.\n\n"
     "Prioridad de negocio: Alta | Riesgo en desarrollo: Medio | Puntos: 5 | Iteración: 1\n"
     "Programador responsable: Nahuel Ghilardi\n\n"
     "Validación:\n"
     "* El sistema automatiza el cálculo de la escala validada internacionalmente NEWS2.\n"
     "* El algoritmo categoriza el riesgo de inmediato, reduciendo la fatiga mental y la "
     "carga cognitiva del profesional.\n"
     "* El cálculo es reproducible: mismo input, mismo score, siempre.",
     "High", "backend", "5", N),
    (2, "Tarea", "Migración de esquema: profiles, patients, encounters, vital_records, alerts",
     "Escrita, sin aplicar.", "High", "backend", "", N),
    (2, "Tarea", "CHECKs de rango fisiológico plausible en vital_records",
     "Escrita, sin aplicar.", "Medium", "backend", "", N),
    (2, "Tarea", "7 funciones puras news2_score_* + news2_risk_level",
     "Escrita, sin aplicar. Funciones puras para que sean testeables de forma aislada.",
     "High", "backend", "", N),
    (2, "Tarea", "Trigger de cálculo automático y emisión de alertas",
     "Escrita, sin aplicar.", "High", "backend", "", N),
    (2, "Tarea", "Desacoplar la escala de SpO2 del oxígeno suplementario",
     "La escala 2 de SpO2 es una prescripción médica, no un derivado de si el paciente "
     "tiene O2 puesto. Vive en `encounters.spo2_scale`.\n\n"
     "Escrita, sin aplicar.", "High", "backend", "", N),
    (2, "Tarea", "Denormalizar spo2_scale_used para reproducibilidad histórica del score",
     "Si mañana cambia la prescripción, el score de ayer tiene que seguir siendo "
     "reproducible con la escala que se usó entonces.\n\n"
     "Escrita, sin aplicar.", "Medium", "backend", "", N),
    (2, "Tarea", "Separar recorded_at de created_at",
     "El momento en que se tomó el signo vital no es el momento en que se cargó al sistema. "
     "Confundirlos rompe cualquier análisis temporal.\n\n"
     "Escrita, sin aplicar.", "Medium", "backend", "", N),
    (2, "Tarea", "RLS: helper current_profile_role() + políticas por rol",
     "`SECURITY DEFINER` para evitar recursión en las políticas.\n\n"
     "Escrita, sin aplicar.", "High", "backend", "", N),
    (2, "Tarea", "Guardas anti-escalada de privilegios en las políticas de profiles",
     "Un usuario no puede cambiarse el rol a sí mismo.\n\n"
     "Escrita, sin aplicar.", "High", "backend", "", N),
    (2, "Tarea", "Suite de 21 casos clínicos contra las funciones puras",
     "Éxito = cero filas devueltas.\n\nEscrita, sin correr.", "Medium", "backend qa", "", G),
    (2, "Tarea", "Aplicar migraciones al proyecto remoto y correr los tests",
     "Supabase remoto está vacío: cero migraciones, cero tablas.", "High", "backend", "", N),
    (2, "Tarea", "DECISIÓN: definir si vital_records pasa a append-only con enmiendas versionadas",
     "Hoy `vital_records` es editable y sobrescribe. Para valor legal debería ser "
     "append-only: un registro clínico no se pisa, se enmienda dejando el original visible.\n\n"
     "*Bloquea la Épica 3*: cambia el modelo que consume el frontend, así que hay que "
     "resolverlo ANTES de escribir la PWA, no después.",
     "Highest", "backend decision", "", N),

    # ── ÉPICA 3 ───────────────────────────────────────────────────────────────
    (3, "Historia", "HU-01 — Módulo de Carga Rápida de Signos Vitales",
     "Como enfermero/a de sala, quiero cargar signos vitales desde la tablet, para "
     "registrar el estado del paciente de forma instantánea en el punto de cuidado sin "
     "requerir papel.\n\n"
     "Prioridad de negocio: Alta | Riesgo en desarrollo: Bajo | Puntos: 3 | Iteración: 1\n"
     "Programador responsable: Gustavo Garcia\n\n"
     "Validación:\n"
     "* La interfaz permite ingresar rápidamente los 7 parámetros vitales rutinarios.\n"
     "* Diseño adaptado a pantallas táctiles, targets de 44 px mínimo (se carga con guantes, "
     "de pie, en una tablet).\n"
     "* Un vital sin cargar se marca explícitamente: un NEWS2 sobre datos incompletos no es "
     "un NEWS2 válido y la interfaz tiene que decirlo.",
     "High", "frontend", "3", G),
    (3, "Historia", "HU-06 — Dashboard de Triage Dinámico",
     "Como jefe/a de enfermería, quiero visualizar un panel de control con el nivel de "
     "riesgo de todos los pacientes internados, para delegar la vigilancia cruzada de "
     "parámetros vitales y distribuir la carga laboral equitativamente.\n\n"
     "Prioridad de negocio: Media | Riesgo en desarrollo: Medio | Puntos: 5 | Iteración: 3\n"
     "Programador responsable: Gustavo Garcia\n\n"
     "Validación:\n"
     "* La interfaz lista a los pacientes dinámicamente según las alertas activas y el "
     "puntaje de riesgo NEWS2.\n"
     "* Consume los datos del backend en tiempo real.",
     "Medium", "frontend", "5", G),
    (3, "Tarea", "Scaffold SPA React + Vite + TS para /app",
     "ADR-001. Se descartó app nativa/APK.", "High", "frontend", "", N),
    (3, "Tarea", "Landing en Astro: producto, tecnología y créditos de datos",
     "ADR-001: Astro sólo para la landing.", "Medium", "frontend", "", N),
    (3, "Tarea", "Aplicar la capa de marca (design_system/brand.css) a landing y login",
     "Paleta tierra completa: terracota, salvia, Caprasimo + Figtree.",
     "Medium", "frontend design", "", N),
    (3, "Tarea", "Aplicar la capa clínica (design_system/clinical.css) a /app",
     "Neutros de alto contraste. Rojo, ámbar, naranja y verde quedan reservados en "
     "exclusiva para los 4 niveles de riesgo NEWS2. Codificación redundante siempre: "
     "color + texto + forma, nunca sólo color.",
     "High", "frontend design", "", N),
    (3, "Tarea", "Autenticación Supabase Auth + selección de rol",
     "Roles: Enfermero de Sala, Médico, Jefe de Enfermería.", "High", "frontend", "", N),
    (3, "Tarea", "Formulario one-click de carga de los 7 parámetros vitales",
     "Optimizado para tablets y móviles.", "High", "frontend", "", N),
    (3, "Tarea", "Vista de detalle de paciente con desglose del score por parámetro",
     "El enfermero tiene que poder ver de dónde sale el número, no sólo el total.",
     "Medium", "frontend", "", N),
    (3, "Tarea", "Indicador de antigüedad de la medición",
     "Un NEWS2 de hace 6 h no vale lo mismo que uno de hace 10 min, y la interfaz no puede "
     "presentarlos igual.", "Medium", "frontend", "", N),
    (3, "Tarea", "Dashboard clínico con orden dinámico por riesgo",
     "", "Medium", "frontend", "", N),
    (3, "Tarea", "PWA: manifiesto + service worker con vite-plugin-pwa",
     "ADR-001.", "Medium", "frontend", "", N),
    (3, "Tarea", "Cola offline con Dexie y reconciliación al reconectar",
     "ADR-001. En una sala sin señal la carga no se puede perder.",
     "Medium", "frontend", "", N),
    (3, "Tarea", "Auditoría de accesibilidad: contraste y codificación redundante",
     "Verificar que ningún nivel de riesgo se comunique sólo por color.",
     "Medium", "frontend qa", "", G),
    (3, "Tarea", "Validación clínica de los mockups con datos ficticios",
     "Sector Clínica Médica, 24 camas CM-01..CM-24, HC de 8 dígitos, nombres verosímiles "
     "de Mendoza.", "Low", "frontend qa", "", G),

    # ── ÉPICA 4 ───────────────────────────────────────────────────────────────
    (4, "Historia", "HU-03 — Motor de Inteligencia Artificial y Alertas Predictivas",
     "Como médico/a de guardia, quiero recibir alertas predictivas de deterioro (como shock "
     "séptico o paro cardiorrespiratorio) horas antes de la descompensación, para aplicar "
     "intervenciones tempranas y preventivas.\n\n"
     "Prioridad de negocio: Media | Riesgo en desarrollo: Alto | Puntos: 8 | Iteración: 2\n"
     "Programador responsable: Nahuel Ghilardi\n\n"
     "Validación:\n"
     "* El modelo analiza la tendencia en el tiempo de los 7 parámetros vitales.\n"
     "* La IA funciona como copiloto y NUNCA toma decisiones finales.\n"
     "* Métrica principal: tasa de alertas a sensibilidad igualada a NEWS2 (referencia a "
     "batir: 37,6 alertas por 100 pacientes-día). No AUROC, no accuracy.",
     "Medium", "ml", "8", N),
    (4, "Tarea", "BLOQUEANTE: completar el credentialing de PhysioNet",
     "El curso CITI ya está aprobado (Active). Falta la solicitud de credencial: "
     "verificación de identidad revisada por humanos + un referente que responda un mail.\n\n"
     "Va con el instituto real, job title `Student`, país Argentina, y la profesora de "
     "Prácticas 3 como referente (avisándole antes). Declarar 'MIT' se rechaza, y un "
     "rechazo complica reaplicar.\n\n"
     "*Riesgo #1 del cronograma*: la revisión tarda de días a semanas y la entrega es en "
     "noviembre de 2026.",
     "Highest", "ml bloqueante", "", N),
    (4, "Tarea", "Firmar el DUA específico de MIMIC-IV-ED",
     "Bloqueada por el credentialing.", "High", "ml", "", N),
    (4, "Tarea", "Pipeline de ingesta con datos sintéticos",
     "Permite desarrollar toda la tubería sin esperar la credencial de PhysioNet, que es "
     "el bloqueante largo.", "High", "ml", "", N),
    (4, "Tarea", "Descarga y limpieza de MIMIC-IV-ED",
     "ADR-002/006: MIMIC-IV-ED, no MIMIC-IV completo.", "High", "ml", "", N),
    (4, "Tarea", "Esquemas de validación estricta con Pydantic / Pandera",
     "", "Medium", "ml", "", N),
    (4, "Tarea", "Implementar la definición de etiqueta v2",
     "y=1 si {UCI o muerte} ocurre en (t+1h, t+24h]. Lookback de 24 h, ventana ciega de 1 h.\n\n"
     "NUNCA usar 'NEWS2 >= 7' como etiqueta: sería circular.",
     "Highest", "ml", "", N),
    (4, "Tarea", "Split por paciente (nunca por fila) y control de fuga temporal",
     "Partir por fila mete al mismo paciente en train y test, e infla todas las métricas.",
     "High", "ml", "", N),
    (4, "Tarea", "Análisis exploratorio de datos (EDA) en notebooks",
     "", "Medium", "ml", "", N),
    (4, "Tarea", "Baseline XGBoost sobre el snapshot actual",
     "La literatura muestra que XGBoost sobre el snapshot iguala a LSTM/Transformers sobre "
     "series de 48 h. Es el baseline a batir.", "High", "ml", "", N),
    (4, "Tarea", "LSTM sobre series de 48 h — hipótesis bajo prueba",
     "ADR-005: la LSTM pasó de protagonista a hipótesis bajo prueba. Si no aporta sobre el "
     "baseline, eso también es un hallazgo válido y reportable en la tesis.",
     "Medium", "ml", "", N),
    (4, "Tarea", "Comparativa de tasa de alertas a sensibilidad igualada",
     "Baseline vs XGBoost vs LSTM. Nunca reportar accuracy: la prevalencia es 0,22-5%.",
     "Highest", "ml", "", N),
    (4, "Tarea", "Exportar el modelo elegido a ONNX",
     "ADR-004. TensorFlow descartado: import lento y contenedor de ~2 GB.",
     "Medium", "ml", "", N),
    (4, "Tarea", "Documentar el caveat de rendimiento de NEWS2 en urgencias",
     "NEWS2 rinde peor en urgencias: sepsis AUROC 0,66, COVID 0,59. Va declarado en la "
     "tesis, no escondido.", "Medium", "ml academico", "", T),

    # ── ÉPICA 5 ───────────────────────────────────────────────────────────────
    (5, "Historia", "HU-04 — Interfaz de Alertas Explicables y Flujo One-Click",
     "Como profesional receptor de alertas, quiero recibir notificaciones tempranas que no "
     "sean una 'caja negra', para tomar decisiones clínicas fundamentadas de manera ágil.\n\n"
     "Prioridad de negocio: Alta | Riesgo en desarrollo: Medio | Puntos: 5 | Iteración: 2\n"
     "Programador responsable: Gustavo Garcia\n\n"
     "Validación:\n"
     "* El sistema explica POR QUÉ alerta.\n"
     "* Flujo 'One-Click' implementado: validar o posponer.\n"
     "* El diseño mitiga la fatiga de alertas integrándose directamente en el flujo de "
     "trabajo.",
     "High", "frontend ml", "5", G),
    (5, "Tarea", "API REST con FastAPI sirviendo el modelo con onnxruntime",
     "ADR-004.", "High", "backend ml", "", N),
    (5, "Tarea", "Desplegar la API en Hugging Face Spaces",
     "Cuenta Zaha-CDSS.", "High", "backend ml", "", N),
    (5, "Tarea", "Edge Function de Supabase que envía el historial del paciente a la API",
     "", "Medium", "backend", "", N),
    (5, "Tarea", "Degradación elegante: si el Space duerme, NEWS2 sigue funcionando",
     "ADR-004: el NEWS2 determinístico NUNCA depende de la API de IA. Si el Space está "
     "dormido, la app sigue funcionando degradada, no rota.",
     "Highest", "backend frontend", "", N),
    (5, "Tarea", "Explicabilidad de la predicción: contribución por parámetro",
     "Sin esto la alerta es una caja negra y HU-04 no se cumple.",
     "High", "ml", "", N),
    (5, "Tarea", "Mostrar la predicción en /app separada visualmente del score determinístico",
     "El usuario tiene que poder distinguir 'esto lo calculó la escala' de 'esto lo estimó "
     "un modelo'. Va en violeta punteado, fuera de la escala de colores NEWS2.",
     "High", "frontend design", "", N),
    (5, "Tarea", "Flujo One-Click: validar / posponer alerta con registro del acuse",
     "", "High", "frontend", "", N),
    (5, "Tarea", "Medir la tasa de alertas real de la app y compararla con la referencia",
     "Cierra el círculo con el objetivo del proyecto: si la app genera más alertas que "
     "NEWS2 solo, contradice su propia tesis.", "High", "qa ml", "", G),

    # ── ÉPICA 6 ───────────────────────────────────────────────────────────────
    (6, "Historia", "HU-05 — Estructura de Datos FHIR y Trazabilidad Legal",
     "Como administrador del sistema, quiero asegurar la interoperabilidad provincial y el "
     "registro inalterable de cada alerta emitida, para protección legal del enfermero e "
     "institución.\n\n"
     "Prioridad de negocio: Alta | Riesgo en desarrollo: Alto | Puntos: 8 | Iteración: 3\n"
     "Programador responsable: Nahuel Ghilardi\n\n"
     "Validación:\n"
     "* El sistema se estructura bajo el estándar HL7 FHIR para conectarse al Bus de "
     "Interoperabilidad provincial.\n"
     "* Utiliza recursos FHIR específicos: Observation, Patient (identidad) y RiskAssessment.",
     "High", "regulatorio backend", "8", N),
    (6, "Tarea", "Mapear el esquema propio a recursos FHIR",
     "Observation, Patient, RiskAssessment.", "High", "regulatorio backend", "", N),
    (6, "Tarea", "Log de auditoría inalterable de cada alerta y cada acuse",
     "Es la contracara de la decisión append-only de la Épica 2.",
     "High", "regulatorio backend", "", N),
    (6, "Tarea", "Encuadre SaMD y disposición ANMAT 9688/19",
     "", "Medium", "regulatorio academico", "", T),
    (6, "Tarea", "Cumplimiento Ley 25.326 (datos personales) y Ley 27.706",
     "", "Medium", "regulatorio academico", "", T),
    (6, "Tarea", "Documento de gestión de riesgos del dispositivo",
     "", "Medium", "regulatorio academico", "", T),
    (6, "Tarea", "Redacción del marco teórico de la tesis",
     "", "Medium", "academico", "", G),
    (6, "Tarea", "Actualizar el TP con las decisiones nuevas",
     "Reencuadre del ADR-005 (de precisión a tasa de alertas), MIMIC-IV-ED en vez de "
     "MIMIC-IV, ONNX en vez de .keras, y el producto pasa a llamarse Zaha.",
     "Medium", "academico", "", G),
    (6, "Tarea", "Manual de usuario para personal de enfermería",
     "", "Low", "academico", "", T),
    (6, "Tarea", "Presentación final de Prácticas Profesionales 3",
     "Los tres integrantes.", "High", "academico", "", T),
]

HERE = os.path.dirname(os.path.abspath(__file__))


def write(path, header, rows):
    # utf-8-sig: Jira Cloud lee bien el BOM y así no se rompen los acentos.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("%-22s %2d filas" % (os.path.basename(path), len(rows)))


def main():
    write(
        os.path.join(HERE, "jira_1_epicas.csv"),
        ["Issue Type", "Summary", "Description", "Labels"],
        [["Epic", s, d, "%s %s" % (lab, own)] for s, d, lab, own in EPICAS],
    )

    rows = []
    for ep, tipo, summ, desc, prio, labs, pts, own in ISSUES:
        rows.append([
            tipo, summ, desc, prio,
            "epica-%d %s %s" % (ep, labs, own),
            pts, "",  # Parent vacío: se completa después de importar las épicas
        ])
    write(
        os.path.join(HERE, "jira_2_issues.csv"),
        ["Issue Type", "Summary", "Description", "Priority", "Labels",
         "Story point estimate", "Parent"],
        rows,
    )


if __name__ == "__main__":
    main()
