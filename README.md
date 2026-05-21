# Zaha CDSS 🫀
**Sistema de Soporte a la Decisión Clínica (CDSS) para la Detección Temprana de Deterioro.**

Zaha es una plataforma Mobile-First diseñada para reemplazar el registro en papel de signos vitales en entornos clínicos. Utiliza un motor determinístico basado en la escala matemática **NEWS2** y un motor predictivo de Inteligencia Artificial (**LSTM**) para analizar series temporales y alertar sobre el deterioro del paciente antes de que ocurra.

## Arquitectura y Stack Tecnológico

El sistema está construido bajo una arquitectura de microservicios y despliegue Serverless, preparado para interoperabilidad futura con estándares HL7 FHIR.

- **Frontend / PWA:** Astro + Tailwind CSS (Optimizado para tablets/móviles offline).
- **Base de Datos & Auth:** Supabase (PostgreSQL) con Row Level Security (RLS).
- **Motor de Inteligencia Artificial:** Python (TensorFlow/Keras, Scikit-learn).
- **Inferencia:** API RESTful (FastAPI) desplegada en Hugging Face / Render.

## Estructura del Monorepo

Este repositorio contiene tanto la aplicación cliente como el motor predictivo de IA:

| Directorio | Descripción |
| :--- | :--- |
| `/app` | Frontend y PWA construida con Astro. Lógica UI/UX "One-Click". |
| `/ml_engine` | Motor predictivo. Pipelines de datos, experimentación (Notebooks), y API de inferencia. |
| `/supabase` | Migraciones SQL, políticas de seguridad (RLS) y seeds de la base de datos. |

## Roadmap de Desarrollo

- [ ] **Iteración 1 (MVP):** Estructura base en Supabase, Autenticación y cálculo determinístico en tiempo real del score NEWS2.
- [ ] **Iteración 2 (IA & Alertas):** Integración del modelo LSTM entrenado con series temporales para predicción secuencial.
- [ ] **Iteración 3 (Gestión):** Dashboard de Triage en vivo y trazabilidad legal de acciones médicas.

## Seguridad y Datos Clínicos
Este proyecto cumple estrictos estándares de separación de datos. Ningún dato clínico de entrenamiento (`/data`) ni archivo de pesos del modelo se versiona en este repositorio público para garantizar la privacidad y seguridad.

---
*Desarrollado para la optimización de procesos clínicos y la reducción de tiempos de respuesta en urgencias hospitalarias.*
