-- =============================================================================
-- SCRUM-72 — Log de auditoría inalterable de cada alerta y cada acuse
--
-- Es la contracara de la decisión append-only de la Épica 2: vital_records no
-- se pisa nunca, pero alerts SÍ se actualiza (status, acknowledged_by,
-- acknowledged_at, acknowledgement_note). O sea que hoy la tabla guarda el
-- ESTADO FINAL de cada alerta, no su historia. Tres agujeros concretos:
--
--   1. Si una alerta se reconoce, la fila queda con quién y cuándo, pero no
--      queda rastro de que antes estuvo pendiente ni de cuánto tardó en
--      atenderse. El tiempo de respuesta es justamente lo que una auditoría
--      clínica va a querer medir.
--   2. guard_alert_acknowledgement() arranca con
--         IF (SELECT auth.uid()) IS NULL THEN RETURN NEW; END IF;
--      así que TODA la protección se saltea cuando no hay usuario autenticado:
--      con la service_role key se puede reescribir cualquier alerta en
--      silencio, y la fila resultante es indistinguible de una legítima.
--   3. Nada permite detectar que una fila fue alterada por fuera de la app.
--
-- Este log ataca los tres. La estrategia es de dos capas, porque en una base
-- de datos la prevención absoluta no existe: quien tiene privilegios de dueño
-- puede desactivar un trigger. Entonces:
--
--   PREVENCIÓN  — append-only real: sin GRANT de UPDATE/DELETE, sin políticas
--                 RLS de escritura, y un trigger que rechaza UPDATE y DELETE
--                 SIN la puerta de atrás de auth.uid(). El log lo escribe el
--                 sistema, jamás la aplicación.
--   DETECCIÓN   — cadena de hashes: cada fila sella el hash de la anterior, así
--                 que borrar, insertar en el medio o modificar una fila rompe
--                 la cadena de ahí en adelante y verificar_cadena_auditoria()
--                 lo señala. No impide la manipulación: la vuelve evidente,
--                 que es lo que un registro con valor probatorio necesita.
--
-- Conecta con la Ley 25.326 (Sprint 6): el art. 9 exige medidas contra la
-- adulteración de datos personales de salud, y "es inalterable porque la app
-- no ofrece un botón para alterarlo" no es una medida.
-- =============================================================================

CREATE TABLE public.alert_audit_log (
  -- La cadena de hashes depende del orden total, así que el orden es la clave
  -- primaria y lo asigna la base. GENERATED ALWAYS: ni el sistema puede elegirlo.
  seq              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  alert_id         UUID NOT NULL REFERENCES public.alerts(id) ON DELETE RESTRICT,

  evento           TEXT NOT NULL
                   CHECK (evento IN ('emitida', 'reconocida', 'descartada')),
  estado_previo    TEXT,
  estado_nuevo     TEXT NOT NULL,

  -- Quién. NULL + actor_es_sistema = lo hizo un trigger, no una persona.
  -- Se guardan los dos por separado a propósito: "no sé quién fue" y "fue el
  -- sistema" son cosas distintas y una auditoría no puede confundirlas.
  actor_id         UUID REFERENCES public.profiles(id) ON DELETE RESTRICT,
  actor_es_sistema BOOLEAN NOT NULL,
  nota             TEXT,

  -- Copia congelada de la alerta al momento del evento. Si alguien después
  -- edita alerts por fuera, esta copia sigue diciendo qué se alertó de verdad.
  contenido        JSONB NOT NULL,

  -- Cuándo lo registró el LOG. Los instantes clínicos reales (triggered_at,
  -- acknowledged_at) viven dentro de contenido: no son lo mismo y mezclarlos
  -- haría que una fila de backfill mienta sobre cuándo se observó el hecho.
  registrado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Una fila de backfill documenta algo que pasó ANTES de que existiera el log.
  -- Marcarlas es obligatorio: afirmar que se observó lo que no se observó es
  -- exactamente el tipo de cosa que invalida un registro de auditoría.
  origen_backfill  BOOLEAN NOT NULL DEFAULT FALSE,

  hash_previo      TEXT,
  hash             TEXT NOT NULL,

  CONSTRAINT actor_coherente CHECK (
    (actor_es_sistema AND actor_id IS NULL) OR
    (NOT actor_es_sistema AND actor_id IS NOT NULL)
  )
);

COMMENT ON TABLE public.alert_audit_log IS
  'Log append-only y encadenado por hash de cada alerta emitida y cada acuse. '
  'No se actualiza ni se borra. Verificar integridad con verificar_cadena_auditoria().';

CREATE INDEX alert_audit_log_por_alerta ON public.alert_audit_log (alert_id, seq);

-- -----------------------------------------------------------------------------
-- Sello de la cadena.
--
-- hash = sha256(hash_previo || carga_canonica). Cualquier cambio en una fila,
-- o su desaparición, deja el hash_previo de la siguiente sin corresponder.
--
-- El lock de transacción serializa los append concurrentes: sin él, dos
-- inserciones simultáneas leen el mismo "último hash" y las dos se encadenan
-- al mismo eslabón, con lo que la cadena se bifurca y la verificación falla
-- sobre datos que en realidad son legítimos. Es un lock por evento de alerta,
-- no por toma de vitales: el volumen no lo justifica como problema.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.sellar_evento_auditoria()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $fn$
DECLARE
  ultimo   TEXT;
  canonica TEXT;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtext('alert_audit_log_cadena'));

  SELECT l.hash INTO ultimo
    FROM public.alert_audit_log l
   ORDER BY l.seq DESC
   LIMIT 1;

  NEW.hash_previo := ultimo;  -- NULL solo en el génesis

  -- jsonb ordena sus claves de forma determinística, así que ::text es estable.
  canonica := concat_ws('|',
    COALESCE(ultimo, ''),
    NEW.seq::TEXT,
    NEW.alert_id::TEXT,
    NEW.evento,
    COALESCE(NEW.estado_previo, ''),
    NEW.estado_nuevo,
    COALESCE(NEW.actor_id::TEXT, ''),
    NEW.actor_es_sistema::TEXT,
    COALESCE(NEW.nota, ''),
    NEW.contenido::TEXT,
    NEW.registrado_en::TEXT,
    NEW.origen_backfill::TEXT
  );

  NEW.hash := encode(sha256(convert_to(canonica, 'UTF8')), 'hex');
  RETURN NEW;
END;
$fn$;

CREATE TRIGGER alert_audit_log_sellar
  BEFORE INSERT ON public.alert_audit_log
  FOR EACH ROW EXECUTE FUNCTION public.sellar_evento_auditoria();

-- -----------------------------------------------------------------------------
-- Append-only, sin excepciones.
--
-- A diferencia de guard_alert_acknowledgement(), acá NO hay salida temprana
-- por auth.uid() IS NULL. Esa puerta es precisamente lo que este ticket viene
-- a cerrar: un log que la service_role key puede reescribir no es un log.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.guard_alert_audit_log()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $fn$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION
      'alert_audit_log es append-only: un evento de auditoría no se borra (seq %)',
      OLD.seq;
  END IF;
  RAISE EXCEPTION
    'alert_audit_log es append-only: un evento de auditoría no se modifica (seq %)',
    OLD.seq;
END;
$fn$;

CREATE TRIGGER alert_audit_log_guard
  BEFORE UPDATE OR DELETE ON public.alert_audit_log
  FOR EACH ROW EXECUTE FUNCTION public.guard_alert_audit_log();

-- -----------------------------------------------------------------------------
-- Escritura del log desde alerts. La aplicación no participa: si el evento
-- dependiera de que el cliente se acuerde de registrarlo, el log valdría lo
-- que vale la buena fe del cliente.
-- -----------------------------------------------------------------------------
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
    v_evento := NEW.status;   -- 'reconocida' | 'descartada'
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
      'acknowledged_at', NEW.acknowledged_at
    )
  );

  RETURN NULL;
END;
$fn$;

CREATE TRIGGER alerts_registrar_auditoria
  AFTER INSERT OR UPDATE ON public.alerts
  FOR EACH ROW EXECUTE FUNCTION public.registrar_evento_alerta();

-- -----------------------------------------------------------------------------
-- Verificación de la cadena.
--
-- Recalcula cada eslabón y devuelve el primero que no cierra. Es la función
-- que se corre delante de un auditor: si devuelve intacta = TRUE, ninguna fila
-- fue modificada ni eliminada desde que se escribió.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.verificar_cadena_auditoria()
RETURNS TABLE (intacta BOOLEAN, eventos BIGINT, primer_seq_roto BIGINT, detalle TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
DECLARE
  f          RECORD;
  esperado   TEXT;
  anterior   TEXT := NULL;
  n          BIGINT := 0;
BEGIN
  FOR f IN
    SELECT * FROM public.alert_audit_log ORDER BY seq
  LOOP
    n := n + 1;

    IF f.hash_previo IS DISTINCT FROM anterior THEN
      RETURN QUERY SELECT FALSE, n, f.seq,
        format('El eslabón %s no engancha con el anterior: se esperaba %s y dice %s. '
               'Indica una fila borrada o insertada fuera de orden.',
               f.seq, COALESCE(anterior, '(génesis)'), COALESCE(f.hash_previo, '(génesis)'));
      RETURN;
    END IF;

    esperado := encode(sha256(convert_to(concat_ws('|',
      COALESCE(f.hash_previo, ''),
      f.seq::TEXT,
      f.alert_id::TEXT,
      f.evento,
      COALESCE(f.estado_previo, ''),
      f.estado_nuevo,
      COALESCE(f.actor_id::TEXT, ''),
      f.actor_es_sistema::TEXT,
      COALESCE(f.nota, ''),
      f.contenido::TEXT,
      f.registrado_en::TEXT,
      f.origen_backfill::TEXT
    ), 'UTF8')), 'hex');

    IF esperado IS DISTINCT FROM f.hash THEN
      RETURN QUERY SELECT FALSE, n, f.seq,
        format('El contenido del evento %s no coincide con su hash: la fila fue modificada.',
               f.seq);
      RETURN;
    END IF;

    anterior := f.hash;
  END LOOP;

  RETURN QUERY SELECT TRUE, n, NULL::BIGINT,
    format('Cadena íntegra: %s evento(s) verificados.', n);
END;
$fn$;

-- -----------------------------------------------------------------------------
-- RLS y privilegios.
--
-- Solo SELECT. No hay política de INSERT porque el log lo escribe el trigger
-- SECURITY DEFINER: si authenticated pudiera insertar, podría fabricar eventos.
-- Sin UPDATE ni DELETE ni a nivel política ni a nivel GRANT: append-only en las
-- dos capas, igual que vital_records.
-- -----------------------------------------------------------------------------
ALTER TABLE public.alert_audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY alert_audit_log_select ON public.alert_audit_log
  FOR SELECT TO authenticated
  USING (public.is_active_staff());

GRANT SELECT ON public.alert_audit_log TO authenticated;
GRANT EXECUTE ON FUNCTION public.verificar_cadena_auditoria() TO authenticated;

-- -----------------------------------------------------------------------------
-- Backfill de las alertas que ya existían.
--
-- Sin esto la cadena arranca vacía y las alertas previas quedan fuera de la
-- auditoría para siempre. Van marcadas con origen_backfill = TRUE: se reconstruye
-- lo que puede reconstruirse desde alerts, y queda dicho que el log no estaba
-- presente cuando el hecho ocurrió. Una alerta ya resuelta genera sus DOS
-- eventos (emisión y resolución), porque las dos cosas pasaron.
-- -----------------------------------------------------------------------------
DO $backfill$
DECLARE
  a RECORD;
BEGIN
  FOR a IN
    SELECT * FROM public.alerts ORDER BY triggered_at, id
  LOOP
    INSERT INTO public.alert_audit_log (
      alert_id, evento, estado_previo, estado_nuevo,
      actor_id, actor_es_sistema, nota, contenido, origen_backfill
    ) VALUES (
      a.id, 'emitida', NULL, 'pendiente', NULL, TRUE, NULL,
      jsonb_build_object(
        'patient_id',      a.patient_id,
        'encounter_id',    a.encounter_id,
        'vital_record_id', a.vital_record_id,
        'source',          a.source,
        'risk_level',      a.risk_level,
        'news2_score',     a.news2_score,
        'ml_probability',  a.ml_probability,
        'model_version',   a.model_version,
        'message',         a.message,
        'triggered_at',    a.triggered_at,
        'acknowledged_at', NULL
      ),
      TRUE
    );

    IF a.status <> 'pendiente' THEN
      INSERT INTO public.alert_audit_log (
        alert_id, evento, estado_previo, estado_nuevo,
        actor_id, actor_es_sistema, nota, contenido, origen_backfill
      ) VALUES (
        a.id, a.status, 'pendiente', a.status,
        a.acknowledged_by, a.acknowledged_by IS NULL, a.acknowledgement_note,
        jsonb_build_object(
          'patient_id',      a.patient_id,
          'encounter_id',    a.encounter_id,
          'vital_record_id', a.vital_record_id,
          'source',          a.source,
          'risk_level',      a.risk_level,
          'news2_score',     a.news2_score,
          'ml_probability',  a.ml_probability,
          'model_version',   a.model_version,
          'message',         a.message,
          'triggered_at',    a.triggered_at,
          'acknowledged_at', a.acknowledged_at
        ),
        TRUE
      );
    END IF;
  END LOOP;
END;
$backfill$;
