-- =============================================================================
-- Zaha CDSS — Motor determinístico NEWS2
-- Épica 2 · Paso 2
--
-- Referencia: Royal College of Physicians, "National Early Warning Score
-- (NEWS) 2", 2017. Tabla de puntuación y umbrales de riesgo.
--
-- Este motor es la base clínica del sistema y NO depende del motor de IA.
-- Si el servicio de inferencia se cae, esto sigue funcionando.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Puntaje por parámetro. Funciones puras: fáciles de testear una por una.
-- -----------------------------------------------------------------------------

-- Frecuencia respiratoria (rpm)
CREATE OR REPLACE FUNCTION public.news2_score_respiratory_rate(p_rr INT)
RETURNS INT LANGUAGE sql IMMUTABLE SET search_path = '' AS $fn$
  SELECT CASE
    WHEN p_rr <= 8              THEN 3
    WHEN p_rr BETWEEN 9  AND 11 THEN 1
    WHEN p_rr BETWEEN 12 AND 20 THEN 0
    WHEN p_rr BETWEEN 21 AND 24 THEN 2
    ELSE 3                                  -- >= 25
  END;
$fn$;

-- Saturación de oxígeno (%).
--
-- Escala 1: paciente sin objetivo de saturación reducido.
-- Escala 2: paciente con insuficiencia respiratoria hipercápnica (objetivo
--           prescrito 88-92%). En esta escala el oxígeno suplementario SOLO
--           discrimina el tramo alto: un paciente de escala 2 respirando aire
--           ambiente puntúa 0 con SpO2 >= 93, mientras que el mismo valor con
--           oxígeno puesto puntúa 1, 2 o 3 según cuán por encima del objetivo
--           esté (hiperoxia iatrogénica).
CREATE OR REPLACE FUNCTION public.news2_score_spo2(
  p_spo2   INT,
  p_scale  SMALLINT,
  p_on_o2  BOOLEAN
)
RETURNS INT LANGUAGE sql IMMUTABLE SET search_path = '' AS $fn$
  SELECT CASE
    WHEN p_scale = 1 THEN
      CASE
        WHEN p_spo2 <= 91              THEN 3
        WHEN p_spo2 BETWEEN 92 AND 93  THEN 2
        WHEN p_spo2 BETWEEN 94 AND 95  THEN 1
        ELSE 0                                    -- >= 96
      END
    ELSE  -- escala 2
      CASE
        WHEN p_spo2 <= 83              THEN 3
        WHEN p_spo2 BETWEEN 84 AND 85  THEN 2
        WHEN p_spo2 BETWEEN 86 AND 87  THEN 1
        WHEN p_spo2 BETWEEN 88 AND 92  THEN 0
        WHEN NOT p_on_o2               THEN 0     -- >= 93 respirando aire
        WHEN p_spo2 BETWEEN 93 AND 94  THEN 1
        WHEN p_spo2 BETWEEN 95 AND 96  THEN 2
        ELSE 3                                    -- >= 97 con oxígeno
      END
  END;
$fn$;

-- Oxígeno suplementario
CREATE OR REPLACE FUNCTION public.news2_score_supplemental_oxygen(p_on_o2 BOOLEAN)
RETURNS INT LANGUAGE sql IMMUTABLE SET search_path = '' AS $fn$
  SELECT CASE WHEN p_on_o2 THEN 2 ELSE 0 END;
$fn$;

-- Temperatura (°C)
CREATE OR REPLACE FUNCTION public.news2_score_temperature(p_temp NUMERIC)
RETURNS INT LANGUAGE sql IMMUTABLE SET search_path = '' AS $fn$
  SELECT CASE
    WHEN p_temp <= 35.0                 THEN 3
    WHEN p_temp <= 36.0                 THEN 1   -- 35.1 - 36.0
    WHEN p_temp <= 38.0                 THEN 0   -- 36.1 - 38.0
    WHEN p_temp <= 39.0                 THEN 1   -- 38.1 - 39.0
    ELSE 2                                       -- >= 39.1
  END;
$fn$;

-- Presión arterial sistólica (mmHg)
CREATE OR REPLACE FUNCTION public.news2_score_systolic_bp(p_sbp INT)
RETURNS INT LANGUAGE sql IMMUTABLE SET search_path = '' AS $fn$
  SELECT CASE
    WHEN p_sbp <= 90                 THEN 3
    WHEN p_sbp BETWEEN 91  AND 100   THEN 2
    WHEN p_sbp BETWEEN 101 AND 110   THEN 1
    WHEN p_sbp BETWEEN 111 AND 219   THEN 0
    ELSE 3                                       -- >= 220
  END;
$fn$;

-- Frecuencia cardíaca (lpm)
CREATE OR REPLACE FUNCTION public.news2_score_heart_rate(p_hr INT)
RETURNS INT LANGUAGE sql IMMUTABLE SET search_path = '' AS $fn$
  SELECT CASE
    WHEN p_hr <= 40                  THEN 3
    WHEN p_hr BETWEEN 41  AND 50     THEN 1
    WHEN p_hr BETWEEN 51  AND 90     THEN 0
    WHEN p_hr BETWEEN 91  AND 110    THEN 1
    WHEN p_hr BETWEEN 111 AND 130    THEN 2
    ELSE 3                                       -- >= 131
  END;
$fn$;

-- Nivel de consciencia ACVPU.
-- A = Alerta (0). C = New Confusion, V = Voz, P = Dolor, U = Inconsciente (3).
CREATE OR REPLACE FUNCTION public.news2_score_consciousness(p_acvpu TEXT)
RETURNS INT LANGUAGE sql IMMUTABLE SET search_path = '' AS $fn$
  SELECT CASE WHEN p_acvpu = 'A' THEN 0 ELSE 3 END;
$fn$;

-- -----------------------------------------------------------------------------
-- Clasificación de riesgo.
--
-- Umbrales RCP 2017:
--   >= 7                                  -> Alto
--   5 - 6                                 -> Medio
--   cualquier parámetro individual en 3   -> Medio Bajo  (score total 0-4)
--   0 - 4 sin parámetro en 3              -> Bajo
--
-- El orden de evaluación importa: un score >= 5 ya es Medio o Alto aunque
-- tenga un parámetro en rojo, así que el rojo aislado se evalúa último.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.news2_risk_level(p_score INT, p_single_red BOOLEAN)
RETURNS TEXT LANGUAGE sql IMMUTABLE SET search_path = '' AS $fn$
  SELECT CASE
    WHEN p_score >= 7             THEN 'Alto'
    WHEN p_score BETWEEN 5 AND 6  THEN 'Medio'
    WHEN p_single_red             THEN 'Medio Bajo'
    ELSE 'Bajo'
  END;
$fn$;

-- -----------------------------------------------------------------------------
-- Trigger: calcula score, nivel de riesgo y bandera de rojo aislado.
-- BEFORE INSERT OR UPDATE, para que los campos calculados nunca puedan
-- escribirse a mano desde el cliente.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.calculate_news2_score()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $fn$
DECLARE
  v_scale      SMALLINT;
  v_scores     INT[];
  v_encounter  RECORD;
  v_amended    RECORD;
BEGIN
  SELECT e.patient_id, e.spo2_scale, e.status
    INTO v_encounter
    FROM public.encounters e
   WHERE e.id = NEW.encounter_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'El episodio % no existe', NEW.encounter_id;
  END IF;

  -- El paciente del registro debe ser el del episodio. Evita que una toma
  -- quede colgada del paciente equivocado por un error del cliente.
  IF NEW.patient_id IS DISTINCT FROM v_encounter.patient_id THEN
    RAISE EXCEPTION 'El paciente % no corresponde al episodio %',
      NEW.patient_id, NEW.encounter_id;
  END IF;

  -- Una observación NUEVA exige episodio abierto. Una ENMIENDA no: corregir un
  -- error de carga descubierto después del alta es justamente el caso que
  -- justifica que esta tabla sea append-only.
  IF v_encounter.status <> 'activo' AND NEW.amends_id IS NULL THEN
    RAISE EXCEPTION 'No se pueden cargar signos vitales en un episodio finalizado';
  END IF;

  -- --- Cadena de enmiendas ---------------------------------------------------
  -- El sellado lo pone el sistema (trigger AFTER), nunca el cliente.
  NEW.superseded_by := NULL;
  NEW.superseded_at := NULL;

  IF NEW.amends_id IS NULL THEN
    NEW.original_id := NEW.id;          -- esta fila es la raíz de su cadena
    v_scale         := v_encounter.spo2_scale;
  ELSE
    SELECT v.encounter_id, v.patient_id, v.original_id, v.superseded_by,
           v.spo2_scale_used
      INTO v_amended
      FROM public.vital_records v
     WHERE v.id = NEW.amends_id
     FOR UPDATE;                        -- serializa dos enmiendas simultáneas

    IF NOT FOUND THEN
      RAISE EXCEPTION 'El registro a enmendar % no existe', NEW.amends_id;
    END IF;

    IF v_amended.superseded_by IS NOT NULL THEN
      RAISE EXCEPTION 'El registro % ya fue enmendado por %: corregí la versión vigente',
        NEW.amends_id, v_amended.superseded_by;
    END IF;

    -- Una enmienda corrige valores, no reasigna el registro a otra persona.
    IF NEW.encounter_id IS DISTINCT FROM v_amended.encounter_id
    OR NEW.patient_id   IS DISTINCT FROM v_amended.patient_id THEN
      RAISE EXCEPTION 'Una enmienda no puede mover el registro a otro paciente o episodio';
    END IF;

    NEW.original_id := v_amended.original_id;

    -- Una enmienda se puntúa con la escala que regía cuando se tomó el signo,
    -- no con la prescripción de hoy: corregir un valor mal tipeado no debe
    -- cambiar de paso la regla clínica que se le aplicó. Para eso existe
    -- spo2_scale_used.
    v_scale := COALESCE(v_amended.spo2_scale_used, v_encounter.spo2_scale);
  END IF;

  v_scores := ARRAY[
    public.news2_score_respiratory_rate(NEW.respiratory_rate),
    public.news2_score_spo2(NEW.oxygen_saturation, v_scale, NEW.supplemental_oxygen),
    public.news2_score_supplemental_oxygen(NEW.supplemental_oxygen),
    public.news2_score_temperature(NEW.temperature),
    public.news2_score_systolic_bp(NEW.systolic_bp),
    public.news2_score_heart_rate(NEW.heart_rate),
    public.news2_score_consciousness(NEW.consciousness_level)
  ];

  NEW.spo2_scale_used := v_scale;
  NEW.news2_score     := (SELECT SUM(s) FROM unnest(v_scores) AS s);
  NEW.single_red_flag := (SELECT bool_or(s = 3) FROM unnest(v_scores) AS s);
  NEW.risk_level      := public.news2_risk_level(NEW.news2_score, NEW.single_red_flag);

  RETURN NEW;
END;
$fn$;

-- Solo BEFORE INSERT. La tabla es append-only: el único UPDATE que existe es el
-- sellado de superseded_by, que no debe recalcular nada.
CREATE TRIGGER trigger_calculate_news2
  BEFORE INSERT ON public.vital_records
  FOR EACH ROW EXECUTE FUNCTION public.calculate_news2_score();

-- -----------------------------------------------------------------------------
-- Generación automática de alertas.
--
-- SECURITY DEFINER porque el enfermero que carga la toma no tiene permiso de
-- INSERT directo sobre alerts: las alertas las emite el sistema, no la persona.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.emit_news2_alert()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
BEGIN
  IF NEW.risk_level IN ('Medio Bajo', 'Medio', 'Alto') THEN
    INSERT INTO public.alerts (
      patient_id, encounter_id, vital_record_id,
      source, risk_level, news2_score, message, triggered_at
    ) VALUES (
      NEW.patient_id, NEW.encounter_id, NEW.id,
      'news2', NEW.risk_level, NEW.news2_score,
      format('NEWS2 %s - riesgo %s%s', NEW.news2_score, NEW.risk_level,
             CASE WHEN NEW.amends_id IS NOT NULL
                  THEN ' (recalculado sobre un registro enmendado)'
                  ELSE '' END),
      NEW.recorded_at
    );
  END IF;

  RETURN NULL;  -- AFTER trigger: el valor de retorno se ignora
END;
$fn$;

CREATE TRIGGER trigger_emit_news2_alert
  AFTER INSERT ON public.vital_records
  FOR EACH ROW EXECUTE FUNCTION public.emit_news2_alert();

-- -----------------------------------------------------------------------------
-- Aplicación de una enmienda.
--
-- Corre DESPUÉS del insert de la enmienda y hace las dos cosas que la enmienda
-- provoca del lado del registro viejo. Ninguna toca un valor clínico.
--
-- SECURITY DEFINER: sella filas y cierra alertas, dos cosas que el usuario
-- autenticado no puede hacer por su cuenta (y no debe poder).
--
-- Se llama trigger_apply_amendment y no trigger_emit_*: los AFTER triggers de
-- una misma tabla corren en orden alfabético, así que 'apply' cierra la alerta
-- vieja antes de que 'emit' abra la nueva.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.apply_amendment()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
BEGIN
  IF NEW.amends_id IS NULL THEN
    RETURN NULL;
  END IF;

  -- Único UPDATE que existe sobre vital_records en todo el sistema.
  UPDATE public.vital_records
     SET superseded_by = NEW.id,
         superseded_at = NOW()
   WHERE id = NEW.amends_id;

  -- La alerta que disparó el dato erróneo NO se borra: pasó, y la traza legal
  -- tiene que mostrar que pasó. Pero deja de estar pendiente, porque la versión
  -- vigente ya emitió la suya. Queda firmada por quien enmendó y con el motivo.
  UPDATE public.alerts
     SET status               = 'descartada',
         acknowledged_by      = NEW.recorded_by,
         acknowledged_at      = NOW(),
         acknowledgement_note = format(
           'Cerrada al enmendarse el registro de origen (enmienda %s). Motivo: %s',
           NEW.id, NEW.amendment_reason)
   WHERE vital_record_id = NEW.amends_id
     AND status = 'pendiente';

  RETURN NULL;
END;
$fn$;

CREATE TRIGGER trigger_apply_amendment
  AFTER INSERT ON public.vital_records
  FOR EACH ROW EXECUTE FUNCTION public.apply_amendment();
