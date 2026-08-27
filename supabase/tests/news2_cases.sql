-- =============================================================================
-- Zaha CDSS — Casos clínicos de validación del motor NEWS2
--
-- No es una migración. Se corre a mano contra la base para verificar que el
-- motor puntúa como manda el estándar RCP 2017.
--
-- Ataca las funciones puras, no el trigger: no necesita pacientes cargados y
-- por lo tanto no ensucia la base.
--
--   Uso:  psql "$DATABASE_URL" -f supabase/tests/news2_cases.sql
--   Éxito = la consulta final devuelve cero filas.
-- =============================================================================

WITH casos (nombre, rr, spo2, escala, o2, temp, tas, fc, acvpu,
            score_esperado, riesgo_esperado) AS (
  VALUES
  -- ---------------------------------------------------------------------
  -- Línea de base
  -- ---------------------------------------------------------------------
  ('Adulto sano, todo en rango',
   16, 98, 1::SMALLINT, FALSE, 36.5, 120, 72, 'A',   0, 'Bajo'),

  -- ---------------------------------------------------------------------
  -- Regresión: score 4 con un parámetro en rojo.
  -- El SQL planificado lo clasificaba 'Alto' porque la rama no matcheaba
  -- ninguna condición y caía en el ELSE. Sobre-escalaba al paciente.
  -- ---------------------------------------------------------------------
  ('Score 4 con rojo aislado -> Medio Bajo, no Alto',
    8, 94, 1::SMALLINT, FALSE, 36.5, 120, 72, 'A',   4, 'Medio Bajo'),

  ('Score 3 con rojo aislado -> Medio Bajo',
    8, 98, 1::SMALLINT, FALSE, 36.5, 120, 72, 'A',   3, 'Medio Bajo'),

  ('Score 4 sin ningún rojo -> Bajo',
   10, 94, 1::SMALLINT, FALSE, 35.8, 105, 72, 'A',   4, 'Bajo'),

  -- ---------------------------------------------------------------------
  -- Regresión: la escala de SpO2 es una prescripción, no se infiere del
  -- oxígeno suplementario. Estos dos casos son los que más cambian.
  -- ---------------------------------------------------------------------
  ('EPOC (escala 2) respirando aire, SpO2 90 -> en objetivo, 0 puntos',
   16, 90, 2::SMALLINT, FALSE, 36.5, 120, 72, 'A',   0, 'Bajo'),

  ('Escala 1 con oxígeno, SpO2 90 -> hipoxemia real, 3 + 2 puntos',
   16, 90, 1::SMALLINT, TRUE,  36.5, 120, 72, 'A',   5, 'Medio'),

  ('EPOC (escala 2) con oxígeno, SpO2 98 -> hiperoxia, 3 + 2 puntos',
   16, 98, 2::SMALLINT, TRUE,  36.5, 120, 72, 'A',   5, 'Medio'),

  ('EPOC (escala 2) con oxígeno, SpO2 90 -> en objetivo, solo suma el O2',
   16, 90, 2::SMALLINT, TRUE,  36.5, 120, 72, 'A',   2, 'Bajo'),

  -- ---------------------------------------------------------------------
  -- Regresión: la C de ACVPU (confusión nueva) puntúa 3.
  -- El CHECK anterior ni siquiera aceptaba el valor.
  -- ---------------------------------------------------------------------
  ('Confusión nueva (C) -> 3 puntos, rojo aislado',
   16, 98, 1::SMALLINT, FALSE, 36.5, 120, 72, 'C',   3, 'Medio Bajo'),

  ('Responde a la voz (V) -> 3 puntos',
   16, 98, 1::SMALLINT, FALSE, 36.5, 120, 72, 'V',   3, 'Medio Bajo'),

  -- ---------------------------------------------------------------------
  -- Bordes de cada parámetro
  -- ---------------------------------------------------------------------
  ('FR 20 y 21: borde entre 0 y 2',
   21, 98, 1::SMALLINT, FALSE, 36.5, 120, 72, 'A',   2, 'Bajo'),

  ('Temperatura 39.1 -> 2 puntos (nunca 3)',
   16, 98, 1::SMALLINT, FALSE, 39.1, 120, 72, 'A',   2, 'Bajo'),

  ('Temperatura 35.0 -> 3 puntos',
   16, 98, 1::SMALLINT, FALSE, 35.0, 120, 72, 'A',   3, 'Medio Bajo'),

  ('Hipertensión 220 -> 3 puntos, no 0',
   16, 98, 1::SMALLINT, FALSE, 36.5, 220, 72, 'A',   3, 'Medio Bajo'),

  ('TAS 111 y 219 son ambos 0',
   16, 98, 1::SMALLINT, FALSE, 36.5, 219, 72, 'A',   0, 'Bajo'),

  ('Bradicardia 40 -> 3 puntos',
   16, 98, 1::SMALLINT, FALSE, 36.5, 120, 40, 'A',   3, 'Medio Bajo'),

  ('Taquicardia 131 -> 3 puntos',
   16, 98, 1::SMALLINT, FALSE, 36.5, 120, 131, 'A',  3, 'Medio Bajo'),

  -- ---------------------------------------------------------------------
  -- Umbrales de clasificación
  -- ---------------------------------------------------------------------
  ('Score 5 -> Medio',
   21, 94, 1::SMALLINT, FALSE, 35.8, 105, 72, 'A',   5, 'Medio'),

  ('Score 6 -> Medio',
   22, 94, 1::SMALLINT, FALSE, 35.5, 105, 95, 'A',   6, 'Medio'),

  -- ---------------------------------------------------------------------
  -- Deterioro compuesto: el caso que usa el mockup de riesgo alto
  -- ---------------------------------------------------------------------
  ('Sepsis probable: deterioro en todos los ejes -> Alto',
   26, 90, 1::SMALLINT, TRUE,  38.4,  98, 122, 'V', 16, 'Alto'),

  ('Score máximo teórico',
   30, 80, 1::SMALLINT, TRUE,  34.0,  85, 140, 'U', 20, 'Alto')
),

resultados AS (
  SELECT
    c.nombre,
    c.score_esperado,
    c.riesgo_esperado,
    (
      public.news2_score_respiratory_rate(c.rr)
      + public.news2_score_spo2(c.spo2, c.escala, c.o2)
      + public.news2_score_supplemental_oxygen(c.o2)
      + public.news2_score_temperature(c.temp)
      + public.news2_score_systolic_bp(c.tas)
      + public.news2_score_heart_rate(c.fc)
      + public.news2_score_consciousness(c.acvpu)
    ) AS score_obtenido,
    GREATEST(
      public.news2_score_respiratory_rate(c.rr),
      public.news2_score_spo2(c.spo2, c.escala, c.o2),
      public.news2_score_temperature(c.temp),
      public.news2_score_systolic_bp(c.tas),
      public.news2_score_heart_rate(c.fc),
      public.news2_score_consciousness(c.acvpu)
    ) = 3 AS rojo_aislado
  FROM casos c
)

SELECT
  nombre,
  score_esperado,
  score_obtenido,
  riesgo_esperado,
  public.news2_risk_level(score_obtenido, rojo_aislado) AS riesgo_obtenido
FROM resultados
WHERE score_obtenido <> score_esperado
   OR public.news2_risk_level(score_obtenido, rojo_aislado) <> riesgo_esperado;

-- Cero filas = los 21 casos pasan.
