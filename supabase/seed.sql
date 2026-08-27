-- =============================================================================
-- Zaha CDSS — Seed de desarrollo (SCRUM-81)
--
-- Llena la base con un turno de guardia FICTICIO para poder desarrollar y
-- demostrar la PWA. Sector Clínica Médica, camas CM-01 a CM-24.
--
-- NUNCA correr esto contra una base con datos reales de pacientes.
-- Todos los nombres, documentos y valores son inventados.
--
-- Es IDEMPOTENTE: si ya se sembró, no hace nada.
--
-- Diseñado para que los scores los calcule EL MOTOR, no el seed: acá solo se
-- insertan los 7 parámetros crudos. Si el seed escribiera news2_score a mano,
-- estaríamos probando el seed en vez del motor.
-- =============================================================================

DO $seed$
DECLARE
  v_enf   UUID := '11111111-1111-4111-8111-111111111111';
  v_med   UUID := '22222222-2222-4222-8222-222222222222';
  v_jefe  UUID := '33333333-3333-4333-8333-333333333333';
  r       RECORD;
  v_enc   UUID;
  v_pac   UUID;
  v_orig  UUID;
BEGIN
  IF EXISTS (SELECT 1 FROM public.patients WHERE mrn LIKE 'HC%') THEN
    RAISE NOTICE 'El seed ya fue aplicado. No se hace nada.';
    RETURN;
  END IF;

  -- ---------------------------------------------------------------------------
  -- 1. Personal. La contraseña de los tres es 'zaha1234' — SOLO DESARROLLO.
  --    El trigger handle_new_user() crea el profile automáticamente con rol
  --    'enfermero'; después se eleva el de los otros dos.
  -- ---------------------------------------------------------------------------
  INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password,
                          email_confirmed_at, created_at, updated_at,
                          raw_app_meta_data, raw_user_meta_data)
  VALUES
    (v_enf,  '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
     'vanina.aguero@zaha.dev', extensions.crypt('zaha1234', extensions.gen_salt('bf')), NOW(), NOW(), NOW(),
     '{"provider":"email","providers":["email"]}'::jsonb,
     '{"full_name":"Lic. Vanina Soledad Agüero"}'::jsonb),
    (v_med,  '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
     'ricardo.olguin@zaha.dev', extensions.crypt('zaha1234', extensions.gen_salt('bf')), NOW(), NOW(), NOW(),
     '{"provider":"email","providers":["email"]}'::jsonb,
     '{"full_name":"Dr. Ricardo Olguín"}'::jsonb),
    (v_jefe, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
     'silvia.paredes@zaha.dev', extensions.crypt('zaha1234', extensions.gen_salt('bf')), NOW(), NOW(), NOW(),
     '{"provider":"email","providers":["email"]}'::jsonb,
     '{"full_name":"Lic. Silvia Paredes"}'::jsonb);

  UPDATE public.profiles SET role = 'medico', license_id = 'MP 14582' WHERE id = v_med;
  UPDATE public.profiles SET role = 'jefe',   license_id = 'MP 09317' WHERE id = v_jefe;
  UPDATE public.profiles SET license_id = 'ME 22140' WHERE id = v_enf;

  -- ---------------------------------------------------------------------------
  -- 2. Pacientes y episodios. escala_spo2 = 2 solo para el paciente con EPOC.
  -- ---------------------------------------------------------------------------
  FOR r IN
    SELECT * FROM (VALUES
      ('HC10024788','Rosa Beatriz','Quiroga',   '1948-03-14'::date,'female','CM-01',1::smallint),
      ('HC10031952','Héctor Alfredo','Funes',   '1955-11-02'::date,'male',  'CM-03',1::smallint),
      ('HC10047163','Nélida Carmen','Ojeda',    '1941-07-25'::date,'female','CM-05',1::smallint),
      ('HC10052840','Ramón Osvaldo','Páez',     '1937-01-09'::date,'male',  'CM-07',1::smallint),
      ('HC10066215','Marta Susana','Vergara',   '1962-09-30'::date,'female','CM-09',1::smallint),
      ('HC10073491','Julio César','Bustos',     '1950-05-18'::date,'male',  'CM-11',2::smallint),
      ('HC10088307','Elba Noemí','Sosa',        '1944-12-06'::date,'female','CM-12',1::smallint),
      ('HC10094572','Aldo Rubén','Miranda',     '1958-08-21'::date,'male',  'CM-14',1::smallint)
    ) AS t(mrn, nom, ape, nac, gen, cama, escala)
  LOOP
    INSERT INTO public.patients (mrn, first_name, last_name, date_of_birth, gender)
    VALUES (r.mrn, r.nom, r.ape, r.nac, r.gen)
    RETURNING id INTO v_pac;

    INSERT INTO public.encounters (patient_id, ward, bed, admitted_at, spo2_scale)
    VALUES (v_pac, 'Clínica Médica', r.cama,
            NOW() - (random() * INTERVAL '5 days') - INTERVAL '1 day', r.escala);
  END LOOP;

  -- ---------------------------------------------------------------------------
  -- 3. Tomas de signos vitales.
  --    Cada paciente tiene 3 tomas en las últimas 12 h para que el detalle
  --    muestre una serie, y el conjunto cubre los 4 niveles NEWS2.
  -- ---------------------------------------------------------------------------
  FOR r IN
    SELECT * FROM (VALUES
      -- mrn,          h,  fr, spo2, o2,   temp, tas, fc,  acvpu   -> nivel esperado
      ('HC10024788', 10, 16, 98, false, 36.5, 128,  74, 'A'),   -- Bajo
      ('HC10024788',  6, 17, 97, false, 36.7, 124,  78, 'A'),
      ('HC10024788',  2, 16, 98, false, 36.6, 126,  76, 'A'),

      ('HC10031952', 10, 18, 96, false, 37.0, 118,  82, 'A'),   -- Medio Bajo (rojo aislado)
      ('HC10031952',  6, 19, 95, false, 37.2, 115,  88, 'A'),
      ('HC10031952',  2, 20, 97, false, 36.9, 112,  38, 'A'),   -- FC 38 -> 3

      ('HC10047163', 10, 19, 95, false, 37.4, 108,  92, 'A'),   -- Medio
      ('HC10047163',  6, 21, 94, false, 37.8, 104,  98, 'A'),
      ('HC10047163',  2, 22, 94, false, 38.3, 102, 105, 'A'),

      ('HC10052840', 10, 22, 93, true,  38.0,  98, 112, 'A'),   -- Alto
      ('HC10052840',  6, 25, 91, true,  38.6,  92, 124, 'V'),
      ('HC10052840',  2, 27, 89, true,  38.9,  88, 131, 'V'),

      ('HC10066215', 10, 15, 99, false, 36.4, 132,  68, 'A'),   -- Bajo
      ('HC10066215',  6, 16, 98, false, 36.5, 130,  70, 'A'),
      ('HC10066215',  2, 16, 99, false, 36.3, 129,  72, 'A'),

      ('HC10073491', 10, 18, 90, false, 36.8, 126,  84, 'A'),   -- EPOC escala 2: en objetivo
      ('HC10073491',  6, 20, 89, true,  37.1, 122,  92, 'A'),
      ('HC10073491',  2, 21, 91, true,  37.3, 118,  96, 'A'),

      ('HC10088307', 10, 20, 94, false, 37.6, 106,  94, 'A'),   -- Alto, y con enmienda
      ('HC10088307',  6, 23, 92, true,  38.2,  99, 108, 'A'),
      ('HC10088307',  2, 26, 90, true,  38.7,  94, 118, 'C'),   -- C = confusión nueva

      ('HC10094572', 10, 17, 97, false, 36.9, 121,  80, 'A'),   -- Bajo
      ('HC10094572',  6, 16, 98, false, 36.7, 123,  76, 'A'),
      ('HC10094572',  2, 17, 97, false, 36.8, 122,  78, 'A')
    ) AS t(mrn, h, fr, spo2, o2, temp, tas, fc, acvpu)
  LOOP
    SELECT e.id, e.patient_id INTO v_enc, v_pac
      FROM public.encounters e
      JOIN public.patients p ON p.id = e.patient_id
     WHERE p.mrn = r.mrn AND e.status = 'activo';

    INSERT INTO public.vital_records (
      encounter_id, patient_id, recorded_by, recorded_at,
      respiratory_rate, oxygen_saturation, supplemental_oxygen,
      temperature, systolic_bp, heart_rate, consciousness_level)
    VALUES (v_enc, v_pac, v_enf, NOW() - (r.h || ' hours')::interval,
            r.fr, r.spo2, r.o2, r.temp, r.tas, r.fc, r.acvpu);
  END LOOP;

  -- ---------------------------------------------------------------------------
  -- 4. Una enmienda, para que se vea el historial de versiones y el cierre
  --    automático de la alerta del dato erróneo.
  --    Elba Sosa: la FC de la última toma se cargó como 118 y era 98.
  -- ---------------------------------------------------------------------------
  SELECT v.id, v.encounter_id, v.patient_id INTO v_orig, v_enc, v_pac
    FROM public.vital_records v
    JOIN public.patients p ON p.id = v.patient_id
   WHERE p.mrn = 'HC10088307'
   ORDER BY v.recorded_at DESC
   LIMIT 1;

  INSERT INTO public.vital_records (
    encounter_id, patient_id, recorded_by, recorded_at,
    respiratory_rate, oxygen_saturation, supplemental_oxygen,
    temperature, systolic_bp, heart_rate, consciousness_level,
    amends_id, amendment_reason)
  SELECT v.encounter_id, v.patient_id, v.recorded_by, v.recorded_at,
         v.respiratory_rate, v.oxygen_saturation, v.supplemental_oxygen,
         v.temperature, v.systolic_bp, 98, v.consciousness_level,
         v.id, 'Error de tipeo en la frecuencia cardíaca: se cargó 118 y el monitor marcaba 98. Se corrige contra el registro en papel.'
    FROM public.vital_records v WHERE v.id = v_orig;

  RAISE NOTICE 'Seed aplicado: 3 profesionales, 8 pacientes, 25 registros vitales.';
END;
$seed$;
