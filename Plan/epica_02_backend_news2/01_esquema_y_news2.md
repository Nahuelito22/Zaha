# 🗄️ Épica 2 - Paso 1: Setup de Base de Datos y Lógica NEWS2

## Objetivo

Definir las tablas clínicas (**Profiles**, **Patients**, **Vital Records**) inspiradas en FHIR y crear la **Database Function** en PostgreSQL para calcular el score NEWS2 en tiempo real mediante un **Trigger**.

---

## Contexto

Este documento forma parte de la planificación técnica del proyecto **Zaha CDSS** y está alineado con la visión definida en la [Carta Magna](../../../Plan/00_CARTA_MAGNA.md). El esquema de base de datos sigue los lineamientos del estándar HL7 FHIR para garantizar interoperabilidad futura con el Bus Provincial de Salud de Mendoza.

---

## SQL de Migración

> ⚠️ **IMPORTANTE:** No ejecutar este SQL directamente. Este documento es una referencia técnica para el equipo. La ejecución se realizará de forma controlada a través de las migraciones de Supabase.

```sql
-- 1. TABLAS BASE Y RLS
CREATE TABLE profiles (
id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
role TEXT CHECK (role IN ('enfermero', 'medico', 'jefe')) NOT NULL DEFAULT 'enfermero',
full_name TEXT NOT NULL,
created_at TIMESTAMPTZ DEFAULT NOW(),
updated_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE TABLE patients (
id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
mrn TEXT UNIQUE NOT NULL,
first_name TEXT NOT NULL,
last_name TEXT NOT NULL,
date_of_birth DATE NOT NULL,
gender TEXT CHECK (gender IN ('male', 'female', 'other', 'unknown')) DEFAULT 'unknown',
active BOOLEAN DEFAULT TRUE,
created_at TIMESTAMPTZ DEFAULT NOW(),
updated_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;

CREATE TABLE vital_records (
id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
patient_id UUID REFERENCES patients(id) ON DELETE CASCADE NOT NULL,
recorded_by UUID REFERENCES profiles(id) NOT NULL,
respiratory_rate INT NOT NULL,
oxygen_saturation INT NOT NULL,
supplemental_oxygen BOOLEAN NOT NULL,
temperature NUMERIC(4,1) NOT NULL,
systolic_bp INT NOT NULL,
heart_rate INT NOT NULL,
consciousness_level TEXT CHECK (consciousness_level IN ('A', 'V', 'P', 'U')) NOT NULL DEFAULT 'A',
news2_score INT,
risk_level TEXT,
created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE vital_records ENABLE ROW LEVEL SECURITY;

-- 2. FUNCIÓN DETERMINÍSTICA NEWS2
CREATE OR REPLACE FUNCTION calculate_news2_score()
RETURNS TRIGGER AS $$
DECLARE
  score INT := 0;
  param_score INT;
  single_red BOOLEAN := FALSE;
BEGIN
  -- Frecuencia Respiratoria
  IF NEW.respiratory_rate <= 8 THEN param_score := 3;
  ELSIF NEW.respiratory_rate BETWEEN 9 AND 11 THEN param_score := 1;
  ELSIF NEW.respiratory_rate BETWEEN 12 AND 20 THEN param_score := 0;
  ELSIF NEW.respiratory_rate BETWEEN 21 AND 24 THEN param_score := 2;
  ELSE param_score := 3; END IF;
  score := score + param_score;
  IF param_score = 3 THEN single_red := TRUE; END IF;

  -- SpO2 (Escala 1 - Sin O2 suplementario)
  IF NEW.supplemental_oxygen = FALSE THEN
    IF NEW.oxygen_saturation <= 91 THEN param_score := 3;
    ELSIF NEW.oxygen_saturation BETWEEN 92 AND 93 THEN param_score := 2;
    ELSIF NEW.oxygen_saturation BETWEEN 94 AND 95 THEN param_score := 1;
    ELSE param_score := 0; END IF;
  ELSE
    -- SpO2 (Escala 2 - Con O2 suplementario)
    IF NEW.oxygen_saturation <= 83 THEN param_score := 3;
    ELSIF NEW.oxygen_saturation BETWEEN 84 AND 85 THEN param_score := 2;
    ELSIF NEW.oxygen_saturation BETWEEN 86 AND 87 THEN param_score := 1;
    ELSIF NEW.oxygen_saturation BETWEEN 88 AND 92 THEN param_score := 0;
    ELSIF NEW.oxygen_saturation BETWEEN 93 AND 94 THEN param_score := 1;
    ELSIF NEW.oxygen_saturation BETWEEN 95 AND 96 THEN param_score := 2;
    ELSE param_score := 3; END IF;
  END IF;
  score := score + param_score;
  IF param_score = 3 THEN single_red := TRUE; END IF;

  -- Oxígeno suplementario
  IF NEW.supplemental_oxygen = TRUE THEN param_score := 2; ELSE param_score := 0; END IF;
  score := score + param_score;

  -- Temperatura
  IF NEW.temperature <= 35.0 THEN param_score := 3;
  ELSIF NEW.temperature BETWEEN 35.1 AND 36.0 THEN param_score := 1;
  ELSIF NEW.temperature BETWEEN 36.1 AND 38.0 THEN param_score := 0;
  ELSIF NEW.temperature BETWEEN 38.1 AND 39.0 THEN param_score := 1;
  ELSE param_score := 2; END IF;
  score := score + param_score;
  IF param_score = 3 THEN single_red := TRUE; END IF;

  -- Presión Arterial Sistólica
  IF NEW.systolic_bp <= 90 THEN param_score := 3;
  ELSIF NEW.systolic_bp BETWEEN 91 AND 100 THEN param_score := 2;
  ELSIF NEW.systolic_bp BETWEEN 101 AND 110 THEN param_score := 1;
  ELSIF NEW.systolic_bp BETWEEN 111 AND 219 THEN param_score := 0;
  ELSE param_score := 3; END IF;
  score := score + param_score;
  IF param_score = 3 THEN single_red := TRUE; END IF;

  -- Frecuencia Cardíaca
  IF NEW.heart_rate <= 40 THEN param_score := 3;
  ELSIF NEW.heart_rate BETWEEN 41 AND 50 THEN param_score := 1;
  ELSIF NEW.heart_rate BETWEEN 51 AND 90 THEN param_score := 0;
  ELSIF NEW.heart_rate BETWEEN 91 AND 110 THEN param_score := 1;
  ELSIF NEW.heart_rate BETWEEN 111 AND 130 THEN param_score := 2;
  ELSE param_score := 3; END IF;
  score := score + param_score;
  IF param_score = 3 THEN single_red := TRUE; END IF;

  -- AVPU
  IF NEW.consciousness_level = 'A' THEN param_score := 0; ELSE param_score := 3; END IF;
  score := score + param_score;
  IF param_score = 3 THEN single_red := TRUE; END IF;

  NEW.news2_score := score;

  IF score <= 4 AND single_red = FALSE THEN NEW.risk_level := 'Bajo';
  ELSIF score = 3 AND single_red = TRUE THEN NEW.risk_level := 'Medio Bajo';
  ELSIF score BETWEEN 5 AND 6 THEN NEW.risk_level := 'Medio';
  ELSE NEW.risk_level := 'Alto';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. TRIGGER
CREATE TRIGGER trigger_calculate_news2
BEFORE INSERT OR UPDATE ON vital_records
FOR EACH ROW
EXECUTE FUNCTION calculate_news2_score();
```

---

## Estructura de Tablas

| Tabla | Inspiración FHIR | Propósito |
|---|---|---|
| `profiles` | Practitioner | Almacena los datos del profesional de salud autenticado (enfermero, médico, jefe). |
| `patients` | Patient | Registro de pacientes con MRN (Medical Record Number) único. |
| `vital_records` | Observation | Cada registro de signos vitales con cálculo automático NEWS2. |

---

## Lógica del Trigger `calculate_news2_score()`

El trigger se ejecuta **BEFORE INSERT OR UPDATE** en `vital_records` y calcula automáticamente:

1. **`news2_score`**: Suma ponderada de los 7 parámetros vitales según la escala NEWS2 validada internacionalmente.
2. **`risk_level`**: Clasificación de riesgo clínico basada en el score total y la presencia de parámetros con puntaje extremo (3 = "single red flag").

### Clasificación de Riesgo

| Score | Condición | Nivel de Riesgo | Color Semáforo |
|---|---|---|---|
| 0–4 | Sin single red | 🟢 **Bajo** | Verde |
| 3 | Con single red | 🟡 **Medio Bajo** | Amarillo |
| 5–6 | Cualquiera | 🟠 **Medio** | Naranja |
| ≥7 | Cualquiera | 🔴 **Alto** | Rojo |

---

## Próximos Pasos

- [ ] Revisar el SQL con el equipo antes de ejecutar.
- [ ] Ejecutar la migración en Supabase (Sprint 1/Sprint 2).
- [ ] Configurar políticas RLS específicas para cada rol.
- [ ] Crear datos de prueba para validar el trigger.
