-- =============================================================================
-- Zaha CDSS — Casos de enmienda de vital_records (append-only)
--
-- A diferencia de news2_cases.sql, esto SÍ necesita datos: prueba triggers,
-- constraints y la vista, no funciones puras. Por eso corre entero dentro de un
-- bloque que termina abortando a propósito: no deja nada en la base.
--
--   Uso:  psql "$DATABASE_URL" -f supabase/tests/amendment_cases.sql
--   Éxito = termina con el error 'TESTS OK'. Cualquier otro error es un fallo.
--
-- OJO: corre como owner, así que RLS no se evalúa. Acá se verifica el motor
-- (triggers y constraints), que es la capa que ni service_role puede saltear.
-- El RLS por rol se prueba aparte, con sesiones autenticadas de verdad.
-- =============================================================================

DO $test$
DECLARE
  v_user       UUID := gen_random_uuid();
  v_patient    UUID;
  v_otro_pac   UUID;
  v_encounter  UUID;
  v_otro_enc   UUID;
  v1           UUID;
  v2           UUID;
  v_n          INT;
  v_txt        TEXT;
  v_id         UUID;
  v_fallo      BOOLEAN;
BEGIN
  -- --- Preparación -----------------------------------------------------------
  INSERT INTO auth.users (id, email) VALUES (v_user, 'test.enmiendas@zaha.local');
  -- handle_new_user() crea el profile solo.

  INSERT INTO public.patients (mrn, first_name, last_name, date_of_birth)
  VALUES ('TEST-ENM-1', 'Paciente', 'De Prueba', '1960-01-01')
  RETURNING id INTO v_patient;

  INSERT INTO public.patients (mrn, first_name, last_name, date_of_birth)
  VALUES ('TEST-ENM-2', 'Otro', 'Paciente', '1970-01-01')
  RETURNING id INTO v_otro_pac;

  INSERT INTO public.encounters (patient_id, ward, bed)
  VALUES (v_patient, 'Clinica Medica', '101') RETURNING id INTO v_encounter;

  INSERT INTO public.encounters (patient_id, ward, bed)
  VALUES (v_otro_pac, 'Clinica Medica', '102') RETURNING id INTO v_otro_enc;

  -- --- 1. Toma original con un valor mal tipeado -----------------------------
  -- FR 30 (3) + SpO2 80 (3) + O2 suplementario (2) = 8 -> Alto.
  -- Es el error de carga que después se corrige.
  INSERT INTO public.vital_records (
    encounter_id, patient_id, recorded_by,
    respiratory_rate, oxygen_saturation, supplemental_oxygen,
    temperature, systolic_bp, heart_rate, consciousness_level)
  VALUES (v_encounter, v_patient, v_user, 30, 80, TRUE, 36.5, 120, 72, 'A')
  RETURNING id INTO v1;

  SELECT risk_level INTO v_txt FROM public.vital_records WHERE id = v1;
  IF v_txt <> 'Alto' THEN
    RAISE EXCEPTION 'FALLO 1: la toma original debia dar Alto, dio %', v_txt;
  END IF;

  SELECT original_id INTO v_id FROM public.vital_records WHERE id = v1;
  IF v_id IS DISTINCT FROM v1 THEN
    RAISE EXCEPTION 'FALLO 2: una observacion original debe ser raiz de su cadena';
  END IF;

  SELECT count(*) INTO v_n FROM public.alerts
   WHERE vital_record_id = v1 AND status = 'pendiente';
  IF v_n <> 1 THEN
    RAISE EXCEPTION 'FALLO 3: esperaba 1 alerta pendiente, hay %', v_n;
  END IF;

  -- --- 2. La enmienda --------------------------------------------------------
  INSERT INTO public.vital_records (
    encounter_id, patient_id, recorded_by,
    respiratory_rate, oxygen_saturation, supplemental_oxygen,
    temperature, systolic_bp, heart_rate, consciousness_level,
    amends_id, amendment_reason)
  VALUES (v_encounter, v_patient, v_user, 16, 98, FALSE, 36.5, 120, 72, 'A',
          v1, 'Error de tipeo al cargar FR y SpO2; se corrige contra la planilla en papel.')
  RETURNING id INTO v2;

  IF NOT EXISTS (SELECT 1 FROM public.vital_records
                  WHERE id = v1 AND superseded_by = v2 AND superseded_at IS NOT NULL) THEN
    RAISE EXCEPTION 'FALLO 4: la fila enmendada no quedo sellada';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM public.vital_records
                  WHERE id = v2 AND original_id = v1 AND superseded_by IS NULL) THEN
    RAISE EXCEPTION 'FALLO 5: la enmienda no heredo original_id o quedo sellada';
  END IF;

  -- El dato erróneo NO desaparece: sigue en la tabla, con su score.
  SELECT count(*) INTO v_n FROM public.vital_records WHERE original_id = v1;
  IF v_n <> 2 THEN
    RAISE EXCEPTION 'FALLO 6: la cadena debia tener 2 versiones, tiene %', v_n;
  END IF;

  -- Pero la vista muestra una sola: la vigente.
  SELECT count(*) INTO v_n FROM public.vital_records_vigentes
   WHERE encounter_id = v_encounter;
  IF v_n <> 1 THEN
    RAISE EXCEPTION 'FALLO 7: vigentes debia devolver 1 fila, devolvio %', v_n;
  END IF;

  -- --- 3. La alerta huérfana -------------------------------------------------
  SELECT count(*) INTO v_n FROM public.alerts
   WHERE vital_record_id = v1 AND status = 'descartada'
     AND acknowledged_by = v_user AND acknowledgement_note LIKE 'Cerrada al enmendarse%';
  IF v_n <> 1 THEN
    RAISE EXCEPTION 'FALLO 8: la alerta del dato erroneo no se cerro correctamente';
  END IF;

  -- Sigue existiendo: es traza legal, no se borra. Y la enmienda da Bajo, así
  -- que no emite una nueva: queda 1 alerta histórica y cero pendientes.
  SELECT count(*) INTO v_n FROM public.alerts WHERE encounter_id = v_encounter;
  IF v_n <> 1 THEN
    RAISE EXCEPTION 'FALLO 9: esperaba 1 alerta historica, hay %', v_n;
  END IF;

  -- --- 4. Inmutabilidad ------------------------------------------------------
  v_fallo := FALSE;
  BEGIN
    UPDATE public.vital_records SET heart_rate = 99 WHERE id = v2;
    v_fallo := TRUE;
  EXCEPTION WHEN others THEN NULL;
  END;
  IF v_fallo THEN RAISE EXCEPTION 'FALLO 10: se pudo editar un valor clinico'; END IF;

  v_fallo := FALSE;
  BEGIN
    DELETE FROM public.vital_records WHERE id = v2;
    v_fallo := TRUE;
  EXCEPTION WHEN others THEN NULL;
  END;
  IF v_fallo THEN RAISE EXCEPTION 'FALLO 11: se pudo borrar un registro clinico'; END IF;

  -- --- 5. Reglas de la cadena ------------------------------------------------
  -- No se enmienda dos veces la misma fila: hay que corregir la vigente.
  v_fallo := FALSE;
  BEGIN
    INSERT INTO public.vital_records (
      encounter_id, patient_id, recorded_by,
      respiratory_rate, oxygen_saturation, supplemental_oxygen,
      temperature, systolic_bp, heart_rate, consciousness_level,
      amends_id, amendment_reason)
    VALUES (v_encounter, v_patient, v_user, 18, 97, FALSE, 36.5, 120, 72, 'A',
            v1, 'Segunda correccion sobre una version ya enmendada.');
    v_fallo := TRUE;
  EXCEPTION WHEN others THEN NULL;
  END;
  IF v_fallo THEN RAISE EXCEPTION 'FALLO 12: se enmendo dos veces la misma version'; END IF;

  -- Toda enmienda lleva motivo escrito.
  v_fallo := FALSE;
  BEGIN
    INSERT INTO public.vital_records (
      encounter_id, patient_id, recorded_by,
      respiratory_rate, oxygen_saturation, supplemental_oxygen,
      temperature, systolic_bp, heart_rate, consciousness_level, amends_id)
    VALUES (v_encounter, v_patient, v_user, 18, 97, FALSE, 36.5, 120, 72, 'A', v2);
    v_fallo := TRUE;
  EXCEPTION WHEN others THEN NULL;
  END;
  IF v_fallo THEN RAISE EXCEPTION 'FALLO 13: se acepto una enmienda sin motivo'; END IF;

  -- Regresión: este caso destapó que el CHECK evaluaba a NULL con motivo NULL,
  -- y un CHECK que da NULL no se considera violado. Se agregó el COALESCE.
  -- Este cubre el otro lado: un motivo que existe pero no dice nada.
  v_fallo := FALSE;
  BEGIN
    INSERT INTO public.vital_records (
      encounter_id, patient_id, recorded_by,
      respiratory_rate, oxygen_saturation, supplemental_oxygen,
      temperature, systolic_bp, heart_rate, consciousness_level,
      amends_id, amendment_reason)
    VALUES (v_encounter, v_patient, v_user, 18, 97, FALSE, 36.5, 120, 72, 'A',
            v2, 'corto');
    v_fallo := TRUE;
  EXCEPTION WHEN others THEN NULL;
  END;
  IF v_fallo THEN RAISE EXCEPTION 'FALLO 13b: se acepto un motivo de una palabra'; END IF;

  -- Una enmienda corrige valores, no reasigna el registro a otro paciente.
  v_fallo := FALSE;
  BEGIN
    INSERT INTO public.vital_records (
      encounter_id, patient_id, recorded_by,
      respiratory_rate, oxygen_saturation, supplemental_oxygen,
      temperature, systolic_bp, heart_rate, consciousness_level,
      amends_id, amendment_reason)
    VALUES (v_otro_enc, v_otro_pac, v_user, 18, 97, FALSE, 36.5, 120, 72, 'A',
            v2, 'Intento de mover la toma a otro paciente.');
    v_fallo := TRUE;
  EXCEPTION WHEN others THEN NULL;
  END;
  IF v_fallo THEN RAISE EXCEPTION 'FALLO 14: una enmienda cambio de paciente'; END IF;

  -- --- 6. Episodio finalizado ------------------------------------------------
  UPDATE public.encounters
     SET status = 'finalizado', discharged_at = NOW(), discharge_disposition = 'domicilio'
   WHERE id = v_encounter;

  -- Observación nueva sobre un episodio cerrado: no.
  v_fallo := FALSE;
  BEGIN
    INSERT INTO public.vital_records (
      encounter_id, patient_id, recorded_by,
      respiratory_rate, oxygen_saturation, supplemental_oxygen,
      temperature, systolic_bp, heart_rate, consciousness_level)
    VALUES (v_encounter, v_patient, v_user, 16, 98, FALSE, 36.5, 120, 72, 'A');
    v_fallo := TRUE;
  EXCEPTION WHEN others THEN NULL;
  END;
  IF v_fallo THEN
    RAISE EXCEPTION 'FALLO 15: se cargo una toma nueva en un episodio cerrado';
  END IF;

  -- Enmienda de una toma ya existente: sí. Es el caso que justifica todo esto.
  INSERT INTO public.vital_records (
    encounter_id, patient_id, recorded_by,
    respiratory_rate, oxygen_saturation, supplemental_oxygen,
    temperature, systolic_bp, heart_rate, consciousness_level,
    amends_id, amendment_reason)
  VALUES (v_encounter, v_patient, v_user, 17, 97, FALSE, 36.6, 120, 72, 'A',
          v2, 'Correccion posterior al alta detectada en la auditoria de la historia clinica.');

  SELECT count(*) INTO v_n FROM public.vital_records WHERE original_id = v1;
  IF v_n <> 3 THEN
    RAISE EXCEPTION 'FALLO 16: la cadena debia tener 3 versiones, tiene %', v_n;
  END IF;

  -- Todo pasó. Se aborta a propósito para no dejar datos de prueba en la base.
  RAISE EXCEPTION 'TESTS OK';
END;
$test$;
