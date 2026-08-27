-- =============================================================================
-- Zaha CDSS — Esquema clínico inicial
-- Épica 2 · Paso 1
--
-- Modelo inspirado en HL7 FHIR:
--   profiles       -> Practitioner
--   patients       -> Patient
--   encounters     -> Encounter
--   vital_records  -> Observation
--   alerts         -> DetectedIssue / Flag
--
-- El cálculo NEWS2 y las políticas RLS viven en migraciones posteriores.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- profiles — profesional de salud autenticado
-- -----------------------------------------------------------------------------
CREATE TABLE public.profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role        TEXT NOT NULL DEFAULT 'enfermero'
              CHECK (role IN ('enfermero', 'medico', 'jefe')),
  full_name   TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
  license_id  TEXT,                       -- matrícula profesional
  active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.profiles IS 'Profesional de salud. 1:1 con auth.users.';
COMMENT ON COLUMN public.profiles.active IS 'Baja lógica: un profesional inactivo pierde acceso pero sus registros persisten.';

-- -----------------------------------------------------------------------------
-- patients — identidad del paciente (datos que no cambian entre internaciones)
-- -----------------------------------------------------------------------------
CREATE TABLE public.patients (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mrn            TEXT NOT NULL UNIQUE,    -- Medical Record Number
  first_name     TEXT NOT NULL CHECK (length(trim(first_name)) > 0),
  last_name      TEXT NOT NULL CHECK (length(trim(last_name)) > 0),
  date_of_birth  DATE NOT NULL CHECK (date_of_birth <= CURRENT_DATE),
  gender         TEXT NOT NULL DEFAULT 'unknown'
                 CHECK (gender IN ('male', 'female', 'other', 'unknown')),
  active         BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.patients IS 'Identidad del paciente. Lo que varía por internación vive en encounters.';

-- -----------------------------------------------------------------------------
-- encounters — episodio de internación
--
-- Necesario para: (a) el dashboard de triage por sector, (b) delimitar las
-- ventanas temporales del modelo predictivo por episodio y no por paciente,
-- (c) registrar la escala de SpO2 prescrita, que es una decisión clínica
-- por internación.
-- -----------------------------------------------------------------------------
CREATE TABLE public.encounters (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id             UUID NOT NULL REFERENCES public.patients(id) ON DELETE RESTRICT,
  ward                   TEXT NOT NULL,          -- sector / servicio
  bed                    TEXT,
  admitted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  discharged_at          TIMESTAMPTZ,
  status                 TEXT NOT NULL DEFAULT 'activo'
                         CHECK (status IN ('activo', 'finalizado')),
  discharge_disposition  TEXT
                         CHECK (discharge_disposition IN
                                ('domicilio', 'uci', 'derivacion', 'fallecido', 'otro')),

  -- Escala de SpO2 según NEWS2.
  --   1 = escala estándar (default, la gran mayoría de los pacientes)
  --   2 = pacientes con insuficiencia respiratoria hipercápnica (típicamente
  --       EPOC) con objetivo de saturación prescrito de 88-92%.
  -- Es una PRESCRIPCIÓN MÉDICA explícita. Nunca se infiere de si el paciente
  -- tiene oxígeno suplementario puesto.
  spo2_scale             SMALLINT NOT NULL DEFAULT 1 CHECK (spo2_scale IN (1, 2)),

  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT encounter_dates_coherent
    CHECK (discharged_at IS NULL OR discharged_at >= admitted_at),
  CONSTRAINT encounter_finalizado_tiene_egreso
    CHECK (status = 'activo' OR (discharged_at IS NOT NULL AND discharge_disposition IS NOT NULL))
);

COMMENT ON COLUMN public.encounters.spo2_scale IS
  'Escala NEWS2 de SpO2 prescrita (1 estándar / 2 hipercapnia). NO se deriva del oxígeno suplementario.';
COMMENT ON COLUMN public.encounters.discharge_disposition IS
  'Destino al egreso. ''uci'' y ''fallecido'' son los eventos de la etiqueta del modelo predictivo (Épica 4).';

-- Un paciente no puede tener dos internaciones activas al mismo tiempo.
CREATE UNIQUE INDEX encounters_un_activo_por_paciente
  ON public.encounters (patient_id)
  WHERE status = 'activo';

-- -----------------------------------------------------------------------------
-- vital_records — toma de signos vitales con score NEWS2 calculado
-- -----------------------------------------------------------------------------
CREATE TABLE public.vital_records (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  encounter_id         UUID NOT NULL REFERENCES public.encounters(id) ON DELETE RESTRICT,
  patient_id           UUID NOT NULL REFERENCES public.patients(id) ON DELETE RESTRICT,
  recorded_by          UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,

  -- Momento de la OBSERVACIÓN clínica, distinto del momento de carga en el
  -- sistema. La diferencia importa para las ventanas temporales del modelo.
  recorded_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Los 7 parámetros NEWS2. Los CHECK son rangos de plausibilidad fisiológica:
  -- atajan errores de tipeo antes de que produzcan un score falso.
  respiratory_rate     INT         NOT NULL CHECK (respiratory_rate  BETWEEN 0  AND 80),
  oxygen_saturation    INT         NOT NULL CHECK (oxygen_saturation BETWEEN 50 AND 100),
  supplemental_oxygen  BOOLEAN     NOT NULL,
  temperature          NUMERIC(4,1) NOT NULL CHECK (temperature      BETWEEN 25.0 AND 45.0),
  systolic_bp          INT         NOT NULL CHECK (systolic_bp       BETWEEN 30 AND 300),
  heart_rate           INT         NOT NULL CHECK (heart_rate        BETWEEN 0  AND 300),

  -- ACVPU. La C es "new confusion / delirium" y puntúa 3, igual que V, P y U.
  -- Omitirla haría que un paciente confuso puntuara como alerta (0).
  consciousness_level  TEXT NOT NULL DEFAULT 'A'
                       CHECK (consciousness_level IN ('A', 'C', 'V', 'P', 'U')),

  -- Calculados por el trigger. Nunca escribir a mano.
  news2_score          INT  CHECK (news2_score BETWEEN 0 AND 20),
  risk_level           TEXT CHECK (risk_level IN ('Bajo', 'Medio Bajo', 'Medio', 'Alto')),
  single_red_flag      BOOLEAN,

  -- Escala efectivamente usada, copiada del encounter al momento del cálculo.
  -- Si mañana cambia la prescripción, este score sigue siendo reproducible.
  spo2_scale_used      SMALLINT CHECK (spo2_scale_used IN (1, 2)),

  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT recorded_at_no_futuro
    CHECK (recorded_at <= NOW() + INTERVAL '5 minutes')
);

COMMENT ON COLUMN public.vital_records.recorded_at IS
  'Momento de la observación clínica (no de la carga). Clave para las ventanas del modelo.';
COMMENT ON COLUMN public.vital_records.spo2_scale_used IS
  'Escala aplicada al calcular este score. Denormalizada a propósito: garantiza reproducibilidad histórica.';

-- Query central del sistema: "últimas tomas de este paciente, más recientes primero".
CREATE INDEX vital_records_paciente_tiempo
  ON public.vital_records (patient_id, recorded_at DESC);

-- Serie temporal por episodio (dashboard de detalle y armado del dataset).
CREATE INDEX vital_records_episodio_tiempo
  ON public.vital_records (encounter_id, recorded_at DESC);

-- -----------------------------------------------------------------------------
-- alerts — traza de toda alerta emitida y de su reconocimiento
--
-- Es el registro legal: qué se alertó, cuándo, a partir de qué dato, quién lo
-- vio y qué hizo. Sin esto no hay auditoría posible (HU N°4 y N°5).
-- -----------------------------------------------------------------------------
CREATE TABLE public.alerts (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id           UUID NOT NULL REFERENCES public.patients(id) ON DELETE RESTRICT,
  encounter_id         UUID NOT NULL REFERENCES public.encounters(id) ON DELETE RESTRICT,
  vital_record_id      UUID REFERENCES public.vital_records(id) ON DELETE RESTRICT,

  source               TEXT NOT NULL CHECK (source IN ('news2', 'ml')),
  risk_level           TEXT NOT NULL CHECK (risk_level IN ('Medio Bajo', 'Medio', 'Alto')),
  news2_score          INT,
  ml_probability       NUMERIC(5,4) CHECK (ml_probability BETWEEN 0 AND 1),
  model_version        TEXT,             -- trazabilidad del modelo que alertó
  message              TEXT NOT NULL,

  triggered_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  status               TEXT NOT NULL DEFAULT 'pendiente'
                       CHECK (status IN ('pendiente', 'reconocida', 'descartada')),
  acknowledged_by      UUID REFERENCES public.profiles(id) ON DELETE RESTRICT,
  acknowledged_at      TIMESTAMPTZ,
  acknowledgement_note TEXT,

  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT alerta_news2_tiene_origen
    CHECK (source <> 'news2' OR (vital_record_id IS NOT NULL AND news2_score IS NOT NULL)),
  CONSTRAINT alerta_ml_tiene_modelo
    CHECK (source <> 'ml' OR (ml_probability IS NOT NULL AND model_version IS NOT NULL)),
  CONSTRAINT alerta_resuelta_tiene_firma
    CHECK (status = 'pendiente' OR (acknowledged_by IS NOT NULL AND acknowledged_at IS NOT NULL))
);

COMMENT ON TABLE public.alerts IS
  'Traza legal de alertas. Una fila por alerta emitida, con su reconocimiento firmado.';

-- Cola de trabajo del dashboard: alertas pendientes, más urgentes primero.
CREATE INDEX alerts_pendientes
  ON public.alerts (triggered_at DESC)
  WHERE status = 'pendiente';

CREATE INDEX alerts_por_episodio
  ON public.alerts (encounter_id, triggered_at DESC);

-- -----------------------------------------------------------------------------
-- updated_at automático
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER profiles_set_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER patients_set_updated_at
  BEFORE UPDATE ON public.patients
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER encounters_set_updated_at
  BEFORE UPDATE ON public.encounters
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- RLS: se habilita acá, las políticas llegan en 20260521000200.
-- Hasta entonces todo queda denegado, que es el default seguro.
-- -----------------------------------------------------------------------------
ALTER TABLE public.profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patients      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.encounters    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vital_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts        ENABLE ROW LEVEL SECURITY;
