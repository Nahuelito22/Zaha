# Mapeo del esquema propio a HL7 FHIR R4

`SCRUM-71` (cierra la historia `SCRUM-70`, HU-05) · Épica 6 · 19/10/2026

> **Qué es este documento.** Cómo se traduce cada dato que guarda Zaha a un recurso de
> HL7 FHIR R4, con qué código y de dónde salió ese código. El mapeo está implementado en
> `ml_engine/src/interoperabilidad/fhir.py`, y sus pruebas validan el resultado contra el
> **esquema JSON oficial de FHIR R4** publicado por HL7. Hay un Bundle de ejemplo, ya
> validado, en `ejemplo_bundle_fhir.json` (paciente ficticio de la cama CM-07).
>
> **Qué no es.** No es una conexión al Bus de Interoperabilidad provincial: el perfil
> concreto que exija ese bus (perfiles locales, identificadores, terminología) no se pudo
> consultar, y no se completa con lo que suena razonable. Lo que este trabajo garantiza es
> que los datos de Zaha **ya están en FHIR R4 válido**, que es el punto de partida de
> cualquier integración.

---

## Qué recurso es cada cosa

| Dato de Zaha | Tabla | Recurso FHIR R4 |
|---|---|---|
| El paciente | `patients` | `Patient` |
| Cada signo vital de una toma | `vital_records` | una `Observation` por parámetro |
| El puntaje NEWS2 | `vital_records.news2_score` | `Observation` (derivada de las anteriores) |
| El nivel de riesgo NEWS2 | `vital_records.risk_level` | `RiskAssessment`, estado `final` |
| La estimación del modelo | respuesta de la API | `RiskAssessment`, estado `preliminary` |

Todo viaja en un `Bundle` de tipo `collection`. Los identificadores se derivan de la toma
(UUID v5), así que reenviar la misma toma no la duplica en el sistema que la recibe.

## Paciente

| Columna | Campo FHIR |
|---|---|
| `id` | `Patient.id` |
| `mrn` (historia clínica) | `Patient.identifier` (sistema propio de Zaha) |
| `first_name`, `last_name` | `Patient.name.given`, `Patient.name.family` |
| `date_of_birth` | `Patient.birthDate` |
| `gender` | `Patient.gender` — el esquema propio usa los mismos cuatro valores que FHIR |
| `active` | `Patient.active` |

## Signos vitales

Todas llevan `status`, el paciente, `effectiveDateTime` (= `recorded_at`, el momento de la
**observación**, no de la carga) e `issued` (= `created_at`, cuándo se registró).

| Columna | LOINC | Unidad UCUM | Perfil FHIR R4 | Fuente del código |
|---|---|---|---|---|
| `respiratory_rate` | 9279-1 Respiratory rate | `/min` | `resprate` | Perfil Vital Signs (1) |
| `heart_rate` | 8867-4 Heart rate | `/min` | `heartrate` | Perfil Vital Signs (1) |
| `oxygen_saturation` | 2708-6 Oxygen saturation in Arterial blood | `%` | `oxygensat` | Perfil Vital Signs (1) |
| `temperature` | 8310-5 Body temperature | `Cel` | `bodytemp` | Perfil Vital Signs (1) |
| `systolic_bp` | panel 85354-9, componente 8480-6 Systolic blood pressure | `mm[Hg]` | `bp` | Perfil Vital Signs (1) |
| `supplemental_oxygen` | 88658-0 Use of supplemental oxygen | — (sí/no) | — | Servidor de terminología (2) |
| `consciousness_level` | 67775-7 Level of responsiveness | — (codificado) | — | Servidor de terminología (2) |

(1) https://hl7.org/fhir/R4/observation-vitalsigns.html — leído el 19/10/2026.
(2) `tx.fhir.org`, LOINC versión 2.82, consultado el 19/10/2026. La búsqueda en loinc.org no
se pudo hacer de forma automatizada (el sitio rechaza esas consultas).

**La presión diastólica.** El perfil de presión exige las dos componentes. Zaha no registra
la diastólica porque NEWS2 no la usa, así que va con `dataAbsentReason = not-performed` en
vez de omitirse o inventarse.

## Lo que no tiene código estándar, dicho como tal

**El puntaje NEWS2 no tiene código LOINC.** Se buscó por "NEWS2" y por "National Early
Warning Score" y no aparece. Va con un código del sistema propio de Zaha (`news2-score`),
con `derivedFrom` apuntando a las siete observaciones de las que sale. Si en el futuro LOINC
lo incorpora, se cambia una línea.

**La "C" de ACVPU no existe en AVPU.** LOINC codifica el nivel de respuesta con la escala
AVPU (alerta, voz, dolor, sin respuesta). NEWS2 agrega la C, *confusión nueva*, que puntúa
3 como V, P y U. Exportarla como "alerta" sería un error clínico grave: el paciente
confundido aparecería como sano. Por eso el **código** de la observación es el LOINC
(67775-7) y el **valor** va en un sistema propio de ACVPU, con su texto legible
("Confusión nueva").

Inventar códigos que parezcan estándar habría sido peor que admitir que no existen: un
sistema receptor los aceptaría sin saber que no significan nada.

## La escala y el modelo, separados también acá

| | NEWS2 | Estimación del modelo |
|---|---|---|
| Recurso | `RiskAssessment` | `RiskAssessment` |
| `status` | `final`: es determinístico | `preliminary`: es una estimación |
| `method` | NEWS2, calculado por la base de datos | "Estimación del modelo de Zaha (no es NEWS2)" |
| `prediction` | nivel de riesgo (Bajo … Alto); si hay rojo aislado, lo dice en `rationale` | probabilidad, alerta o no, y el umbral con su sensibilidad objetivo |
| `note` | — | la advertencia de que la reducción de alertas no está demostrada |

Es la misma regla que en la pantalla, donde la estimación va en violeta y dice "no es
NEWS2": quien reciba estos datos tiene que poder distinguir lo que calculó la escala de lo
que estimó un modelo.

## Enmiendas

`vital_records` no admite borrado: una toma se corrige insertando otra que la enmienda. Se
exporta **el valor vigente**. Si ese valor es una enmienda, sus observaciones salen con
`status = corrected` y el motivo en `note`. Intentar exportar una versión ya reemplazada da
error a propósito. El historial completo de versiones (`Provenance`) queda fuera de este
alcance.

## Lo que queda fuera, y cómo se haría

| Dato | Recurso FHIR que correspondería |
|---|---|
| La internación (`encounters`) | `Encounter` |
| Quién cargó la toma (`profiles`) | `Practitioner` / `PractitionerRole` |
| Las alertas y su acuse (`alerts`) | `Flag` o `DetectedIssue`, más `Task` para el acuse |
| La bitácora de auditoría encadenada | `AuditEvent` y `Provenance` |

## Cómo se verifica

```bash
cd ml_engine && .venv/Scripts/python tests/test_fhir.py
```

Once pruebas. La central valida el Bundle contra el esquema JSON oficial de FHIR R4
(`hl7.org/fhir/R4/fhir.schema.json.zip`, guardado junto al código para no depender de la
red). Otra rompe un recurso a propósito —un `status` inexistente, un género fuera del value
set— y exige que el validador lo rechace: sin esa prueba, la validación podría estar
aceptando cualquier cosa sin que nadie lo note.
