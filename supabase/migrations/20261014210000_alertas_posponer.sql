-- =============================================================================
-- SCRUM-68 — Posponer una alerta, con su acuse registrado
--
-- POR QUE HACE FALTA UN ESTADO NUEVO Y NO ALCANZA CON LOS DOS QUE HABIA
-- La tabla modelaba 'reconocida' y 'descartada'. HU-04 pide "validar o
-- posponer", y posponer no es ninguna de las dos:
--
--   reconocida  — la vi, la atiendo, queda resuelta.
--   descartada  — la vi, es una falsa alarma, no corresponde actuar.
--   pospuesta   — la vi, NO es falsa, pero ahora no. Volvela a mostrar.
--
-- Mapear "posponer" a 'descartada' habria sido registrar una falsa alarma cada
-- vez que una enfermera esta ocupada, y eso contamina exactamente la metrica
-- que el proyecto quiere medir: cuantas alertas son ruido. La tesis entera es
-- sobre fatiga de alertas; confundir "no ahora" con "no sirve" seria borrar la
-- diferencia que justifica el trabajo.
--
-- COMO VUELVE A PENDIENTE: NO VUELVE. SE DERIVA.
-- No hay trabajo programado ni un UPDATE que "despierte" la alerta al vencer el
-- plazo. La fila conserva 'pospuesta' con su `postponed_until`, que es lo que
-- de verdad paso, y la COLA DE TRABAJO se define como una vista:
--
--     pendiente  OR  (pospuesta AND el plazo ya vencio)
--
-- Dos razones. Primera, un UPDATE automatico generaria un evento de auditoria
-- que ninguna persona ejecuto, y el log quedaria lleno de actos del sistema que
-- no son actos. Segunda, la fila tiene que seguir diciendo quien pospuso y
-- hasta cuando: si se la reescribiera a 'pendiente', esa firma se perderia y el
-- acuse --que es la mitad del titulo del issue-- dejaria de existir.
--
-- QUE NO CAMBIA
-- El trigger `registrar_evento_alerta` arma el evento con `NEW.status`, asi que
-- el estado nuevo entra solo en el log. `guard_alert_acknowledgement` no lista
-- `postponed_until` entre los campos inmutables, asi que ya lo permite.
-- La cadena de hashes no se toca: esto es aditivo.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. El estado nuevo y su plazo
-- -----------------------------------------------------------------------------
ALTER TABLE public.alerts DROP CONSTRAINT alerts_status_check;
ALTER TABLE public.alerts ADD CONSTRAINT alerts_status_check
  CHECK (status IN ('pendiente', 'reconocida', 'descartada', 'pospuesta'));

ALTER TABLE public.alerts
  ADD COLUMN postponed_until TIMESTAMPTZ;

COMMENT ON COLUMN public.alerts.postponed_until IS
  'Hasta cuando se pospuso. Solo tiene sentido mientras status = ''pospuesta''; '
  'la alerta no se reescribe al vencer, la cola la deriva (ver alertas_en_cola).';

-- Una alerta pospuesta SIN plazo seria una alerta desaparecida: nunca volveria
-- a la cola y nadie se enteraria.
ALTER TABLE public.alerts ADD CONSTRAINT alerta_pospuesta_tiene_plazo
  CHECK (status <> 'pospuesta' OR postponed_until IS NOT NULL);

-- El plazo tiene que ser futuro al momento de posponer. Sin esto, un plazo en
-- el pasado deja la alerta en la cola igual, pero marcada como atendida: el
-- peor de los dos mundos, porque parece gestionada y no lo esta.
ALTER TABLE public.alerts ADD CONSTRAINT alerta_pospuesta_plazo_posterior
  CHECK (postponed_until IS NULL OR postponed_until > triggered_at);

-- `alerta_resuelta_tiene_firma` ya cubre el caso nuevo sin tocarla: exige firma
-- para todo lo que no sea 'pendiente', y una alerta pospuesta esta firmada por
-- quien la pospuso. Es justamente lo que queremos.

-- -----------------------------------------------------------------------------
-- 2. El log de auditoria acepta el evento nuevo
-- -----------------------------------------------------------------------------
ALTER TABLE public.alert_audit_log DROP CONSTRAINT alert_audit_log_evento_check;
ALTER TABLE public.alert_audit_log ADD CONSTRAINT alert_audit_log_evento_check
  CHECK (evento IN ('emitida', 'reconocida', 'descartada', 'pospuesta'));

-- -----------------------------------------------------------------------------
-- 3. Posponer DOS VECES tambien es un acto, y antes no quedaba registrado
-- -----------------------------------------------------------------------------
-- El trigger solo emitia un evento cuando cambiaba `status`. Una segunda
-- postergacion deja el estado en 'pospuesta' y mueve unicamente el plazo, asi
-- que pasaba en silencio. Y posponer tres veces la misma alerta es exactamente
-- el patron que una auditoria de fatiga de alertas necesita poder ver.
CREATE OR REPLACE FUNCTION public.registrar_evento_alerta()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
DECLARE
  v_evento TEXT;
  v_actor  UUID;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_evento := 'emitida';
  ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
    v_evento := NEW.status;   -- 'reconocida' | 'descartada' | 'pospuesta'
  ELSIF NEW.status = 'pospuesta'
        AND NEW.postponed_until IS DISTINCT FROM OLD.postponed_until THEN
    -- Repostergacion: el estado no cambia pero el acto si existe.
    v_evento := 'pospuesta';
  ELSE
    RETURN NULL;              -- un UPDATE que no cambia el estado no es un evento
  END IF;

  -- acknowledged_by es la firma que ya dejó guard_alert_acknowledgement().
  -- Si no hay ninguna, el acto fue del sistema (enmienda, cierre automático).
  v_actor := CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE NEW.acknowledged_by END;

  INSERT INTO public.alert_audit_log (
    alert_id, evento, estado_previo, estado_nuevo,
    actor_id, actor_es_sistema, nota, contenido
  ) VALUES (
    NEW.id,
    v_evento,
    CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END,
    NEW.status,
    v_actor,
    v_actor IS NULL,
    CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE NEW.acknowledgement_note END,
    jsonb_build_object(
      'patient_id',      NEW.patient_id,
      'encounter_id',    NEW.encounter_id,
      'vital_record_id', NEW.vital_record_id,
      'source',          NEW.source,
      'risk_level',      NEW.risk_level,
      'news2_score',     NEW.news2_score,
      'ml_probability',  NEW.ml_probability,
      'model_version',   NEW.model_version,
      'message',         NEW.message,
      'triggered_at',    NEW.triggered_at,
      'acknowledged_at', NEW.acknowledged_at,
      -- Hasta cuando se pospuso, congelado en el evento: si despues se vuelve a
      -- posponer, cada fila del log conserva SU plazo y la secuencia se lee.
      'postponed_until', NEW.postponed_until
    )
  );

  RETURN NULL;
END;
$fn$;

-- El REVOKE del 20260910193000 se aplicó a la función anterior; CREATE OR
-- REPLACE conserva los privilegios del objeto, pero se repite por si esta
-- migración corre sobre una base donde aquella no pasó.
REVOKE ALL ON FUNCTION public.registrar_evento_alerta() FROM PUBLIC, anon, authenticated;

-- -----------------------------------------------------------------------------
-- 4. La cola de trabajo: lo que de verdad hay que mirar ahora
-- -----------------------------------------------------------------------------
-- Una vista y no una consulta repetida en la app: si cada pantalla escribe su
-- propio "qué cuenta como pendiente", tarde o temprano dos pantallas difieren y
-- la que muestra de menos esconde una alerta real.
--
-- security_invoker: la vista se evalúa con los permisos de quien consulta, así
-- que RLS de `alerts` sigue aplicando. Sin esto la vista correría con los del
-- dueño y seria un rodeo para leer alertas de cualquier paciente.
CREATE VIEW public.alertas_en_cola
WITH (security_invoker = true) AS
SELECT a.*,
       (a.status = 'pospuesta') AS fue_pospuesta
FROM public.alerts a
WHERE a.status = 'pendiente'
   OR (a.status = 'pospuesta' AND a.postponed_until <= NOW());

COMMENT ON VIEW public.alertas_en_cola IS
  'Alertas que requieren atención AHORA: pendientes, más las pospuestas cuyo '
  'plazo ya venció. `fue_pospuesta` permite distinguirlas en la interfaz: una '
  'alerta que vuelve no es lo mismo que una que nunca se miró.';

GRANT SELECT ON public.alertas_en_cola TO authenticated;
