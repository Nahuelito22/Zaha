-- =============================================================================
-- vital_records_desglose — de dónde sale el número (SCRUM-40)
--
-- El enfermero ve "NEWS2 17 / Alto" pero no qué parámetro aportó cuánto. Sin
-- eso el score es un oráculo: no se puede discutir, no se puede detectar una
-- carga mal tipeada, y no se puede enseñar. Un CDSS cuyo output no se puede
-- cuestionar produce o bien obediencia ciega o bien desconfianza total; las dos
-- terminan en el mismo lugar que la fatiga de alarma.
--
-- POR QUÉ UNA VISTA Y NO COLUMNAS:
-- El trigger `calculate_news2_score` ya calcula los 7 subpuntajes en un array
-- (v_scores) pero solo persiste la SUMA. Persistir además las 7 columnas sería
-- desnormalizar un dato 100% derivable y abrir la puerta a que la suma y sus
-- partes se contradigan tras un cambio del motor. La vista los recalcula con
-- LAS MISMAS funciones que usa el trigger, así que no puede divergir: si el
-- motor cambia, cambian los dos a la vez.
--
-- POR QUÉ NO SE CALCULA EN EL CLIENTE:
-- Es la misma regla que ya rige la carga de vitales. Dos implementaciones de
-- NEWS2 que pueden divergir es peor que una, y la que vale legalmente es la de
-- la base.
--
-- LA ESCALA:
-- Usa `spo2_scale_used` —la escala vigente cuando se tomó el signo— y NO la
-- prescripción actual del episodio. Es lo mismo que hace el trigger. Si mañana
-- medicina cambia la escala de un paciente, el desglose de una toma vieja tiene
-- que seguir explicando el score que esa toma realmente tuvo; si no, la
-- pantalla mostraría un desglose que no suma su propio total.
--
-- ALCANCE: la vista NO filtra por `superseded_by`, a diferencia de
-- `vital_records_vigentes`. La pantalla de detalle necesita el historial
-- completo, enmendadas incluidas: ver el dato erróneo junto al corregido es
-- justamente lo que el diseño append-only existe para permitir.
--
-- security_invoker: se evalúa con los permisos de quien consulta. La vista no
-- es una puerta trasera al RLS.
-- =============================================================================
CREATE VIEW public.vital_records_desglose
  WITH (security_invoker = on) AS
  SELECT
    v.*,
    public.news2_score_respiratory_rate(v.respiratory_rate)
      AS sc_respiratory_rate,
    public.news2_score_spo2(v.oxygen_saturation, v.spo2_scale_used, v.supplemental_oxygen)
      AS sc_oxygen_saturation,
    public.news2_score_supplemental_oxygen(v.supplemental_oxygen)
      AS sc_supplemental_oxygen,
    public.news2_score_temperature(v.temperature)
      AS sc_temperature,
    public.news2_score_systolic_bp(v.systolic_bp)
      AS sc_systolic_bp,
    public.news2_score_heart_rate(v.heart_rate)
      AS sc_heart_rate,
    public.news2_score_consciousness(v.consciousness_level)
      AS sc_consciousness
  FROM public.vital_records v;

COMMENT ON VIEW public.vital_records_desglose IS
  'Cada observación con el aporte de sus 7 parámetros al NEWS2, calculado con las mismas funciones que el trigger y con la escala de SpO2 que regía al momento de la toma. Incluye las versiones enmendadas: es la fuente de la pantalla de detalle e historial.';

-- Mismo criterio que el resto del esquema: RLS filtra filas, pero primero hace
-- falta el GRANT, y anon no toca nada.
GRANT SELECT ON public.vital_records_desglose TO authenticated;
REVOKE ALL  ON public.vital_records_desglose FROM anon;
