---
title: Zaha — API de inferencia
emoji: 🩺
colorFrom: gray
colorTo: red
sdk: gradio
sdk_version: 6.30.0
# Fijada a proposito: es la version con la que se verifico el arranque del
# Space localmente, y la misma que usa el Dockerfile de respaldo.
python_version: '3.12'
app_file: app.py
pinned: false
license: apache-2.0
short_description: Estimacion de deterioro clinico. No calcula NEWS2.
---

# Zaha — API de inferencia

Servicio de inferencia del sistema de soporte a la decisión clínica **Zaha**, un proyecto
académico de la Tecnicatura Superior en Desarrollo de Software del IES 9-023 (Mendoza,
Argentina).

> **Esto no es un dispositivo médico.** Es un prototipo académico. No está autorizado por
> ANMAT ni por ninguna autoridad regulatoria, y no debe usarse para tomar decisiones
> clínicas sobre personas reales.

## Cómo está hosteado

El SDK es **Gradio**, no Docker: Hugging Face pasó Docker Spaces a plan pago. La pantalla
que se ve acá es una demostración, y **debajo corre la misma API de FastAPI** que consume
la aplicación clínica. La documentación interactiva está en `/docs`.

## Qué hace y qué no

Estima la probabilidad de deterioro clínico a partir de siete parámetros tomados al pie de
la cama, y devuelve **la descomposición exacta de esa estimación parámetro por parámetro**.

**No calcula NEWS2.** La escala es determinística y se calcula en la base de datos de la
aplicación. Este servicio es un complemento: si está caído o dormido, la aplicación pierde
la estimación y conserva la escala.

## Endpoints

| Método | Ruta | Devuelve |
|---|---|---|
| `GET` | `/salud` | Estado del servicio. Responde 200 incluso si el modelo no cargó, con `estado: degradado` y la causa. |
| `GET` | `/modelo` | Metadatos del modelo: features, cohorte de entrenamiento, curva de umbrales y limitaciones. |
| `POST` | `/prediccion` | Probabilidad, decisión de alerta, punto de operación y explicación. |
| `GET` | `/docs` | Documentación interactiva (OpenAPI). |

```bash
curl -X POST .../prediccion -H "Content-Type: application/json" -d '{
  "observacion": {
    "frecuencia_respiratoria": 26, "spo2": 91, "temperatura": 38.4,
    "presion_sistolica": 96, "frecuencia_cardiaca": 122,
    "confusion": 1, "edad": 81
  }
}'
```

El campo `sensibilidad_objetivo` es opcional y acepta `0.5`, `0.6`, `0.7` u `0.8`. Si se
omite se usa `0.7` y la respuesta lo declara como valor por defecto, porque **elegir el
punto de operación es una decisión clínica**: define cuántas alertas por turno recibe la
guardia.

## El modelo

Regresión logística sobre siete parámetros, exportada a ONNX. Entrenada sobre la cohorte
abierta del estudio TRIAGE (1.300 pacientes de guardia de tres centros, CC0,
[zenodo.org/records/4963759](https://zenodo.org/records/4963759)), con mortalidad a 30 días
como desenlace (54 eventos).

No es XGBoost: con 54 eventos, los cinco pliegues de la validación cruzada anidada
eligieron la regresión logística sin excepción.

## Limitaciones declaradas

- **La reducción de la tasa de alertas frente a NEWS2 no está demostrada.** La estimación
  es de cerca del 30 %, pero su intervalo de confianza del 95 % incluye el cero. El
  resultado es consistente con la hipótesis del proyecto y no alcanza para darla por
  probada.
- La cohorte de entrenamiento es de guardia, con el 72 % de un único hospital de Estados
  Unidos. Generalizar a otra población es una limitación, no un resultado.
- El modelo no vio datos de pacientes argentinos ni de sala de internación general, que es
  el ámbito de uso previsto del sistema.
- La edad es uno de los contribuyentes de mayor peso y no es accionable al pie de la cama.

## Reproducibilidad

Código, datos y procedimiento: [github.com/Nahuelito22/Zaha](https://github.com/Nahuelito22/Zaha)
