-- =============================================================================
-- Zaha CDSS — Políticas RLS y control de acceso por rol
-- Épica 2 · Paso 3
--
-- Principio: negar por defecto. Toda tabla tiene RLS habilitado desde la
-- migración inicial; acá se abren los caminos mínimos que cada rol necesita.
--
-- Roles: enfermero · medico · jefe
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Helper de rol.
--
-- SECURITY DEFINER a propósito: si leyera profiles con los permisos del
-- usuario, la política de profiles se llamaría a sí misma (recursión infinita).
-- STABLE para que Postgres la evalúe una vez por consulta y no por fila.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.current_profile_role()
RETURNS TEXT
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $fn$
  SELECT p.role
    FROM public.profiles p
   WHERE p.id = (SELECT auth.uid())
     AND p.active;
$fn$;

COMMENT ON FUNCTION public.current_profile_role() IS
  'Rol del usuario autenticado, o NULL si no tiene perfil o está inactivo.';

-- Personal habilitado: cualquier profesional con perfil activo.
CREATE OR REPLACE FUNCTION public.is_active_staff()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SET search_path = ''
AS $fn$
  SELECT public.current_profile_role() IS NOT NULL;
$fn$;

-- -----------------------------------------------------------------------------
-- Alta automática de perfil al registrarse.
-- Sin esto nadie tendría perfil nunca, y por lo tanto nadie pasaría el RLS.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
BEGIN
  INSERT INTO public.profiles (id, full_name, role)
  VALUES (
    NEW.id,
    COALESCE(NULLIF(trim(NEW.raw_user_meta_data ->> 'full_name'), ''), NEW.email),
    'enfermero'   -- rol mínimo; elevarlo es un acto administrativo explícito
  );
  RETURN NEW;
END;
$fn$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- -----------------------------------------------------------------------------
-- profiles
-- -----------------------------------------------------------------------------

-- Todo el personal ve a sus colegas: la app muestra quién tomó cada registro.
CREATE POLICY profiles_select ON public.profiles
  FOR SELECT TO authenticated
  USING (public.is_active_staff());

-- Cada uno edita solo su propio perfil.
CREATE POLICY profiles_update_own ON public.profiles
  FOR UPDATE TO authenticated
  USING (id = (SELECT auth.uid()))
  WITH CHECK (id = (SELECT auth.uid()));

-- Guarda contra escalada de privilegios: RLS no filtra por columna, así que sin
-- esto un enfermero podría hacerse 'jefe' editando su propio perfil.
CREATE OR REPLACE FUNCTION public.guard_profile_privileges()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $fn$
BEGIN
  IF (SELECT auth.uid()) IS NULL THEN
    RETURN NEW;   -- operación de servicio (service_role o migración)
  END IF;

  IF NEW.role <> OLD.role AND public.current_profile_role() <> 'jefe' THEN
    RAISE EXCEPTION 'Solo un jefe puede cambiar el rol de un perfil';
  END IF;

  IF NEW.active <> OLD.active AND public.current_profile_role() <> 'jefe' THEN
    RAISE EXCEPTION 'Solo un jefe puede activar o desactivar un perfil';
  END IF;

  RETURN NEW;
END;
$fn$;

CREATE TRIGGER profiles_guard_privileges
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.guard_profile_privileges();

-- El jefe administra roles y altas/bajas del personal.
CREATE POLICY profiles_update_jefe ON public.profiles
  FOR UPDATE TO authenticated
  USING (public.current_profile_role() = 'jefe')
  WITH CHECK (public.current_profile_role() = 'jefe');

-- -----------------------------------------------------------------------------
-- patients
-- -----------------------------------------------------------------------------
CREATE POLICY patients_select ON public.patients
  FOR SELECT TO authenticated
  USING (public.is_active_staff());

CREATE POLICY patients_insert ON public.patients
  FOR INSERT TO authenticated
  WITH CHECK (public.is_active_staff());

CREATE POLICY patients_update ON public.patients
  FOR UPDATE TO authenticated
  USING (public.is_active_staff())
  WITH CHECK (public.is_active_staff());

-- Sin política de DELETE: los pacientes se dan de baja lógica (active = FALSE).

-- -----------------------------------------------------------------------------
-- encounters
-- -----------------------------------------------------------------------------
CREATE POLICY encounters_select ON public.encounters
  FOR SELECT TO authenticated
  USING (public.is_active_staff());

CREATE POLICY encounters_insert ON public.encounters
  FOR INSERT TO authenticated
  WITH CHECK (public.is_active_staff());

CREATE POLICY encounters_update ON public.encounters
  FOR UPDATE TO authenticated
  USING (public.is_active_staff())
  WITH CHECK (public.is_active_staff());

-- Dos campos del episodio son actos médicos, no administrativos:
--   spo2_scale -> es una prescripción (objetivo de saturación).
--   el egreso  -> es un alta.
-- Enfermería puede corregir sala y cama, pero no estas dos cosas.
CREATE OR REPLACE FUNCTION public.guard_encounter_medical_fields()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $fn$
BEGIN
  IF (SELECT auth.uid()) IS NULL THEN
    RETURN NEW;
  END IF;

  IF NEW.spo2_scale <> OLD.spo2_scale
     AND public.current_profile_role() NOT IN ('medico', 'jefe') THEN
    RAISE EXCEPTION 'La escala de SpO2 es una prescripción: solo médico o jefe puede cambiarla';
  END IF;

  IF NEW.status <> OLD.status
     AND public.current_profile_role() NOT IN ('medico', 'jefe') THEN
    RAISE EXCEPTION 'El egreso del episodio solo puede registrarlo un médico o jefe';
  END IF;

  RETURN NEW;
END;
$fn$;

CREATE TRIGGER encounters_guard_medical_fields
  BEFORE UPDATE ON public.encounters
  FOR EACH ROW EXECUTE FUNCTION public.guard_encounter_medical_fields();

-- -----------------------------------------------------------------------------
-- vital_records
-- -----------------------------------------------------------------------------
CREATE POLICY vital_records_select ON public.vital_records
  FOR SELECT TO authenticated
  USING (public.is_active_staff());

-- Se carga siempre a nombre propio: la firma del registro no se delega.
CREATE POLICY vital_records_insert ON public.vital_records
  FOR INSERT TO authenticated
  WITH CHECK (
    public.is_active_staff()
    AND recorded_by = (SELECT auth.uid())
  );

-- Corrección solo de los registros propios.
-- NOTA: esto sobrescribe el valor anterior. Ver la nota de inmutabilidad al pie.
CREATE POLICY vital_records_update_own ON public.vital_records
  FOR UPDATE TO authenticated
  USING (recorded_by = (SELECT auth.uid()))
  WITH CHECK (recorded_by = (SELECT auth.uid()));

-- Sin política de DELETE: un registro clínico no se borra.

-- -----------------------------------------------------------------------------
-- alerts
-- -----------------------------------------------------------------------------
CREATE POLICY alerts_select ON public.alerts
  FOR SELECT TO authenticated
  USING (public.is_active_staff());

-- Sin política de INSERT: las alertas las emite el sistema (trigger
-- SECURITY DEFINER), nunca una persona. Que un usuario pudiera crear alertas
-- a mano rompería el valor probatorio de la tabla.

-- Reconocer o descartar una alerta.
CREATE POLICY alerts_update ON public.alerts
  FOR UPDATE TO authenticated
  USING (public.is_active_staff())
  WITH CHECK (public.is_active_staff());

-- El reconocimiento solo puede tocar los campos del reconocimiento, y se firma
-- con la identidad de quien lo hace.
CREATE OR REPLACE FUNCTION public.guard_alert_acknowledgement()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $fn$
BEGIN
  IF (SELECT auth.uid()) IS NULL THEN
    RETURN NEW;
  END IF;

  IF NEW.patient_id      IS DISTINCT FROM OLD.patient_id
  OR NEW.encounter_id    IS DISTINCT FROM OLD.encounter_id
  OR NEW.vital_record_id IS DISTINCT FROM OLD.vital_record_id
  OR NEW.source          IS DISTINCT FROM OLD.source
  OR NEW.risk_level      IS DISTINCT FROM OLD.risk_level
  OR NEW.news2_score     IS DISTINCT FROM OLD.news2_score
  OR NEW.ml_probability  IS DISTINCT FROM OLD.ml_probability
  OR NEW.model_version   IS DISTINCT FROM OLD.model_version
  OR NEW.message         IS DISTINCT FROM OLD.message
  OR NEW.triggered_at    IS DISTINCT FROM OLD.triggered_at THEN
    RAISE EXCEPTION 'El contenido de una alerta es inmutable; solo puede reconocerse';
  END IF;

  IF OLD.status <> 'pendiente' THEN
    RAISE EXCEPTION 'La alerta ya fue resuelta por otro profesional';
  END IF;

  IF NEW.status <> 'pendiente' THEN
    NEW.acknowledged_by := (SELECT auth.uid());
    NEW.acknowledged_at := NOW();
  END IF;

  RETURN NEW;
END;
$fn$;

CREATE TRIGGER alerts_guard_acknowledgement
  BEFORE UPDATE ON public.alerts
  FOR EACH ROW EXECUTE FUNCTION public.guard_alert_acknowledgement();

-- -----------------------------------------------------------------------------
-- Privilegios de tabla.
-- RLS filtra filas, pero primero hay que tener el GRANT. anon no toca nada.
-- -----------------------------------------------------------------------------
GRANT SELECT, UPDATE                 ON public.profiles      TO authenticated;
GRANT SELECT, INSERT, UPDATE         ON public.patients      TO authenticated;
GRANT SELECT, INSERT, UPDATE         ON public.encounters    TO authenticated;
GRANT SELECT, INSERT, UPDATE         ON public.vital_records TO authenticated;
GRANT SELECT, UPDATE                 ON public.alerts        TO authenticated;

REVOKE ALL ON public.profiles      FROM anon;
REVOKE ALL ON public.patients      FROM anon;
REVOKE ALL ON public.encounters    FROM anon;
REVOKE ALL ON public.vital_records FROM anon;
REVOKE ALL ON public.alerts        FROM anon;

-- -----------------------------------------------------------------------------
-- NOTA PENDIENTE — inmutabilidad de vital_records
--
-- Hoy una toma propia se puede editar y el valor anterior se pierde. Para un
-- registro clínico con valor legal lo correcto es append-only: la corrección
-- se guarda como un registro nuevo que apunta al que enmienda, y el original
-- queda marcado como enmendado pero visible.
--
-- No se implementa acá porque cambia el modelo de datos que consume el
-- frontend. Queda como decisión a tomar antes de cualquier uso real.
-- -----------------------------------------------------------------------------
